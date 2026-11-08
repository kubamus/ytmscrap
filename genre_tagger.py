#!/usr/bin/env python3
"""Fill Rekordbox genres using MusicBrainz and Deezer. No audio re-encoding."""
from __future__ import annotations
import argparse
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from mutagen.flac import FLAC
except ImportError:
    print("[BŁĄD] Brak Mutagen. Uruchom ponownie instalator.", file=sys.stderr)
    raise SystemExit(2)

try:
    import certifi
except ImportError:
    print("[BŁĄD] Brak certifi (certyfikaty HTTPS). Uruchom ponownie instalator ytmscrap.", file=sys.stderr)
    raise SystemExit(2)

AGENT = "ytmscrap/1.1 (https://github.com/kubamus/ytmscrap)"
CACHE = Path.home() / ".cache/ytmscrap/genres-v1.json"
INVALID = {"", "music", "other", "others", "unknown", "unclassified"}
EXTENSIONS = {".flac", ".wav"}

def norm(value):
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"\b(official|audio|music video|video|lyrics|lyric video|hd|4k)\b", " ", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))

def lead(value):
    return re.split(r"\s+(?:feat\.?|ft\.?|featuring|x|vs\.?|with|&)\s+|[,;]", value, maxsplit=1, flags=re.I)[0].strip()

def similarity(a, b):
    a, b = norm(a), norm(b)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0

def confidence(title, artist, found_title, found_artist):
    title_score = similarity(title, found_title)
    artist_score = max(similarity(artist, found_artist), similarity(lead(artist), lead(found_artist)))
    if title_score < .85 or artist_score < .78:
        return 0
    return .70 * title_score + .30 * artist_score

def genre_from(entries):
    genres = [(int(g.get("count", 1)), str(g.get("name", "")).strip()) for g in entries if isinstance(g, dict)]
    genres = [(count, label) for count, label in genres if count >= 0 and norm(label) not in INVALID]
    return max(genres)[1] if genres else ""

def tags(path):
    if path.suffix.lower() == ".flac":
        audio = FLAC(path)
        values = lambda key: (audio.get(key) or [""])[0]
        artist, title, genre = (values("artist"), values("title"), values("genre"))
    else:
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)],
                                capture_output=True, text=True, check=True)
        data = json.loads(result.stdout).get("format", {}).get("tags", {})
        data = {k.lower(): v for k, v in data.items()}
        artist, title, genre = (data.get("artist", ""), data.get("title", ""), data.get("genre", ""))
    parts = path.stem.split(" - ", 1)
    if len(parts) == 2:
        if not title or (" - " in title and similarity(title, parts[1]) < .7):
            title = parts[1]
        if not artist or norm(artist) in {"music", "youtube", "unknown", "various artists"}:
            artist = parts[0]
    return artist.strip(), title.strip(), genre.strip()

def write(path, genre):
    if path.suffix.lower() == ".flac":
        audio = FLAC(path)
        audio["genre"] = [genre]
        audio.save()
        return
    # Rekordbox reads WAV RIFF INFO IGNR. ID3-in-WAV alone is not enough.
    # -c:a copy preserves PCM samples, but rewrites the WAV container.
    fd, name = tempfile.mkstemp(prefix=".ytmscrap-", suffix=".wav", dir=path.parent)
    os.close(fd)
    temp = Path(name)
    try:
        subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(path),
                        "-map", "0:a:0", "-map_metadata", "0", "-c:a", "copy",
                        "-metadata", f"genre={genre}", str(temp)], capture_output=True, text=True, check=True)
        shutil.copystat(path, temp)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()

class Lookup:
    def __init__(self, path=CACHE):
        self.path = path
        try:
            self.cache = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}
        self.last_mb = 0
        self.mb_transient_failures = 0
        self.mb_retry_after = 0
        self.dirty = False
        self.failed_sources = set()
        self.successful_sources = set()
        self.request_failed = False
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def request(self, url, mb=False):
        host = urlparse(url).hostname or "nieznany serwer"
        endpoint = urlparse(url).path
        # MusicBrainz 503 can mean server overload, not an invalid request.
        # Pause MusicBrainz temporarily if it repeatedly fails, then try Deezer.
        if mb and time.monotonic() < self.mb_retry_after:
            self.request_failed = True
            return {}
        req = Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
        attempts = 3 if mb else 1
        for attempt in range(attempts):
            # Apply MusicBrainz's one-request-per-second limit to every attempt.
            if mb:
                remaining = 1.1 - (time.monotonic() - self.last_mb)
                if remaining > 0:
                    time.sleep(remaining)
                self.last_mb = time.monotonic()
            try:
                with urlopen(req, timeout=12, context=self.ssl_context) as response:
                    data = json.load(response)
                if not isinstance(data, dict):
                    raise ValueError("API zwróciło nieprawidłowy format danych")
                if data.get("error"):
                    raise ValueError(f"API zwróciło błąd: {data['error']}")
                self.successful_sources.add(host)
                self.failed_sources.discard(host)
                if mb:
                    self.mb_transient_failures = 0
                return data
            except (HTTPError, URLError, TimeoutError, ValueError) as error:
                transient = isinstance(error, HTTPError) and error.code in (429, 500, 502, 503, 504)
                if mb and transient and attempt + 1 < attempts:
                    delay = 2 ** (attempt + 1)
                    retry_after = error.headers.get("Retry-After") if error.headers else None
                    if retry_after is not None:
                        try:
                            delay = max(delay, min(60.0, float(retry_after)))
                        except ValueError:
                            pass
                    print(f"  [MusicBrainz] HTTP {error.code} na {endpoint}; ponawiam za {delay:g} s", file=sys.stderr)
                    time.sleep(delay)
                    continue

                self.request_failed = True
                self.failed_sources.add(host)
                if mb and transient:
                    self.mb_transient_failures += 1
                    if self.mb_transient_failures >= 2:
                        self.mb_retry_after = time.monotonic() + 120
                        print("  [MusicBrainz] Serwer wciąż niedostępny; używam Deezer przez 2 minuty.", file=sys.stderr)
                reason = error.reason if isinstance(error, URLError) else error
                if isinstance(error, HTTPError):
                    detail = f"HTTP {error.code} {error.reason}"
                else:
                    detail = str(reason)
                print(f"  [BŁĄD API] {host}{endpoint}: {detail}", file=sys.stderr)
                if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in detail:
                    print("  [POMOC] Problem z certyfikatem HTTPS. Zaktualizuj ytmscrap (instaluje certifi). Nie wyłączaj weryfikacji SSL.", file=sys.stderr)
                return {}

    def musicbrainz(self, artist, title):
        safe = lambda s: re.sub(r"[^\w\s-]", " ", s).strip()
        query = f'recording:"{safe(title)}" AND artist:"{safe(lead(artist))}"'
        url = "https://musicbrainz.org/ws/2/recording/?" + urlencode({"query": query, "fmt": "json", "limit": 8})
        records = self.request(url, mb=True).get("recordings", [])
        matches = []
        for entry in records:
            credited = "".join(i.get("name", "") if isinstance(i, dict) else str(i) for i in entry.get("artist-credit", []))
            score = confidence(title, artist, entry.get("title", ""), credited)
            if score >= .90 and entry.get("id"):
                matches.append((score, entry["id"]))
        if not matches:
            return ""
        record_id = max(matches)[1]
        detail = self.request(f"https://musicbrainz.org/ws/2/recording/{record_id}?inc=genres+releases&fmt=json", mb=True)
        genre = genre_from(detail.get("genres", []))
        if genre:
            return genre
        for release in detail.get("releases", [])[:3]:
            group_id = release.get("release-group", {}).get("id")
            if group_id:
                info = self.request(f"https://musicbrainz.org/ws/2/release-group/{group_id}?inc=genres&fmt=json", mb=True)
                genre = genre_from(info.get("genres", []))
                if genre:
                    return genre
        return ""

    def deezer(self, artist, title):
        url = "https://api.deezer.com/search/track?" + urlencode({"q": f"{lead(artist)} {title}", "limit": 10})
        matches = []
        for song in self.request(url).get("data", []):
            score = confidence(title, artist, song.get("title", ""), song.get("artist", {}).get("name", ""))
            album_id = song.get("album", {}).get("id")
            if score >= .91 and isinstance(album_id, int):
                matches.append((score, album_id))
        if not matches:
            return ""
        album_id = max(matches)[1]
        album = self.request(f"https://api.deezer.com/album/{album_id}")
        return genre_from(album.get("genres", {}).get("data", []))

    def find(self, artist, title):
        key = norm(artist) + "|" + norm(title)
        entry = self.cache.get(key, {})
        # Old versions cached network outages as empty genres for seven days.
        # Ignore those negative entries so a fixed connection can retry immediately.
        if entry.get("genre") and time.time() - entry.get("at", 0) < 60 * 86400:
            return entry["genre"], entry.get("source", "cache")
        self.request_failed = False
        genre = self.musicbrainz(artist, title)
        source = "MusicBrainz"
        if not genre:
            genre = self.deezer(artist, title)
            source = "Deezer"
        if not genre and self.request_failed and not self.successful_sources and {
            "musicbrainz.org", "api.deezer.com"
        }.issubset(self.failed_sources):
            raise ConnectionError(
                "Nie można połączyć się z MusicBrainz ani Deezer. "
                "Przerwano, aby nie sprawdzać setek plików bez dostępu do API. "
                "Uruchom: ytmscrap --check-genres"
            )
        # Never save an empty genre after HTTP, DNS or SSL errors.
        if genre or not self.request_failed:
            self.cache[key] = {"genre": genre, "source": source, "at": time.time()}
            self.dirty = True
        return genre, source

    def save(self):
        if self.dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)


# A DJ-focused vocabulary: keep dance subgenres distinct instead of flattening
# them to Electronic, and never infer Polish origin from a generic rap tag.
DJ_GENRES = {
    "Jumpstyle": "jumpstyle|polska jumpstyle|polish jumpstyle",
    "Hardtekk": "hardtekk|hard tekk|slowed hardtekk",
    "Hardtek": "hardtek|hardtekno|hard tekno",
    "Hard Techno": "hard techno|hardtechno",
    "Industrial Techno": "industrial techno",
    "Schranz": "schranz",
    "Hardstyle": "hardstyle|hard style",
    "Rawstyle": "rawstyle|raw hardstyle",
    "Hard Dance": "hard dance|harddance",
    "Hardcore": "hardcore techno|hardcore",
    "Uptempo Hardcore": "uptempo|uptempo hardcore",
    "Frenchcore": "frenchcore",
    "Gabber": "gabber",
    "Happy Hardcore": "happy hardcore",
    "Techno": "techno",
    "Melodic Techno": "melodic techno",
    "Acid Techno": "acid techno",
    "House": "house|house music",
    "Tech House": "tech house|techhouse",
    "Deep House": "deep house",
    "Bass House": "bass house",
    "Afro House": "afro house",
    "Electro House": "electro house",
    "Progressive House": "progressive house",
    "Big Room": "big room|big room house",
    "Trance": "trance",
    "Psytrance": "psytrance|psy trance",
    "Eurodance": "eurodance|euro dance",
    "Dance-Pop": "dance pop|dancepop|dance-pop",
    "Drum & Bass": "drum and bass|drum & bass|dnb|drum n bass|d&b",
    "Liquid Drum & Bass": "liquid drum and bass|liquid drum & bass|liquid dnb|liquid funk",
    "Dancefloor Drum & Bass": "dancefloor dnb|dancefloor drum and bass",
    "Neurofunk": "neurofunk|neuro dnb",
    "Jungle": "jungle",
    "Dubstep": "dubstep",
    "Riddim": "riddim|riddim dubstep",
    "UK Garage": "uk garage|ukg|2 step garage",
    "Phonk": "phonk",
    "Drift Phonk": "drift phonk",
    "Hip-Hop": "hip hop|hip-hop|hiphop|rap|rap music|hip-hop/rap|hip hop rap",
    "Polish Hip-Hop": "polish hip hop|polish hip-hop|polski hip hop|polish rap|polski rap",
    "Trap": "trap|trap music|trap rap",
    "Polish Trap": "polish trap|polski trap",
    "Drill": "drill",
    "UK Drill": "uk drill",
    "R&B": "rnb|r&b|rhythm and blues",
    "Reggaeton": "reggaeton",
    "Dancehall": "dancehall",
    "Disco Polo": "disco polo|discopolo",
    "Polish Pop": "polish pop|polski pop",
    "Pop": "pop|pop music",
    "Rock": "rock|rock music",
    "Pop Rock": "pop rock|pop-rock",
    "Alternative Rock": "alternative rock|alt rock",
    "Indie Rock": "indie rock",
    "Punk Rock": "punk rock|punk",
    "Metal": "metal|heavy metal",
    "Nu Metal": "nu metal|numetal",
    "Funk": "funk",
    "Disco": "disco",
    "Synthwave": "synthwave|retrowave",
    "Synth-Pop": "synth pop|synthpop",
    "Jazz": "jazz",
    "Blues": "blues",
    "Soul": "soul",
    "Country": "country",
    "Folk": "folk",
    "Electronic": "electronic|electronica|electronic music",
    "EDM": "edm|electronic dance music",
    "Dance": "dance|dance music",
}
DJ_ALIASES = {norm(alias): name for name, aliases in DJ_GENRES.items()
              for alias in (name + "|" + aliases).split("|")}
BROAD = {"Electronic", "EDM", "Dance", "Pop", "Rock", "Hip-Hop", "House", "Techno", "Hardcore", "R&B"}
NOISE_TAGS = {"seen live", "favorite", "favourite", "favorites", "polish", "poland",
              "male vocalists", "female vocalists", "awesome", "spotify", "youtube"}


def dj_canonical(label, strict=False):
    label = str(label).strip()
    key = norm(label)
    if key in INVALID or key in NOISE_TAGS:
        return ""
    return DJ_ALIASES.get(key, "" if strict else label)


def dj_best(labels):
    choices = {}
    for label, count in labels:
        name = dj_canonical(label, strict=True)
        if name:
            choices[name] = max(int(count), choices.get(name, -1))
    if not choices:
        return ""
    peak = max(choices.values())
    viable = [(name, score) for name, score in choices.items() if score >= peak * 0.25]
    return max(viable, key=lambda item: (item[0] not in BROAD, item[1], item[0]))[0]


def normalize_genre(existing):
    parts = re.split(r"\s*[;,|]\s*|\s+/\s+", existing)
    known = [(part, 1) for part in parts if dj_canonical(part, strict=True)]
    return dj_best(known) if known else dj_canonical(existing)


def genre_from(entries):
    choices = []
    for item in entries if isinstance(entries, list) else []:
        if isinstance(item, dict):
            try:
                choices.append((item.get("name", ""), int(item.get("count", 1))))
            except (TypeError, ValueError):
                pass
    return dj_best(choices)


class RequestBudget(Exception):
    pass


class DJLookup(Lookup):
    """SQLite cache, Last.fm first, polite API pacing and 429 backoff."""
    def __init__(self, max_requests=500, offline=False):
        super().__init__()
        import sqlite3
        self.db_path = Path.home() / ".cache/ytmscrap/genres.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS genres (key TEXT PRIMARY KEY, genre TEXT NOT NULL, source TEXT NOT NULL, expires INTEGER NOT NULL)")
        # Bring forward valid positive results from the old JSON cache.
        for key, item in self.cache.items():
            genre = dj_canonical(item.get("genre", ""), strict=True) if isinstance(item, dict) else ""
            if genre:
                self.db.execute("INSERT OR IGNORE INTO genres VALUES (?, ?, ?, ?)",
                                ("track:" + key, genre, str(item.get("source", "legacy")), int(time.time()) + 90 * 86400))
        self.db.commit()
        self.requests = 0
        self.max_requests = max_requests
        self.offline = offline
        self.api_key = os.environ.get("LASTFM_API_KEY", "")
        self.last_by_host = {}
        self.blocked = set()
        self.blocked_until = {}

    def request(self, url, mb=False):
        host = urlparse(url).hostname or ""
        if self.offline:
            return {}
        if host in self.blocked:
            if mb and time.monotonic() >= self.blocked_until.get(host, float("inf")):
                self.blocked.discard(host)
                self.blocked_until.pop(host, None)
            else:
                self.request_failed = True  # A blocked API is not a genuine no-genre result.
                return {}
        delay = 1.2 if mb else .65
        for retry in range(3):
            if self.max_requests and self.requests >= self.max_requests:
                raise RequestBudget("Request budget reached. Run again to resume from the cache.")
            wait = delay - (time.monotonic() - self.last_by_host.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            self.last_by_host[host] = time.monotonic()
            self.requests += 1
            req = Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
            try:
                with urlopen(req, timeout=15, context=self.ssl_context) as response:
                    data = json.load(response)
                if not isinstance(data, dict) or data.get("error"):
                    raise ValueError(data.get("message", "Invalid API response") if isinstance(data, dict) else "Invalid API response")
                self.successful_sources.add(host)
                return data
            except HTTPError as error:
                self.request_failed = True
                self.failed_sources.add(host)
                if error.code not in (429, 500, 502, 503, 504):
                    print(f"  [API] {host}: HTTP {error.code}", file=sys.stderr)
                    break
                retry_after = error.headers.get("Retry-After", "")
                seconds = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else 0
                time.sleep(min(30.0, max(seconds, 2 ** (retry + 1))))
            except (URLError, TimeoutError, OSError, ValueError) as error:
                self.request_failed = True
                self.failed_sources.add(host)
                if retry == 2:
                    print(f"  [API] {host}: {error}", file=sys.stderr)
                else:
                    time.sleep(2 ** retry)
        self.blocked.add(host)
        if mb:
            # Give MusicBrainz a fresh chance after a short cooldown.
            self.blocked_until[host] = time.monotonic() + 120
        return {}

    def lastfm(self, artist, title):
        if not self.api_key:
            return ""
        url = "https://ws.audioscrobbler.com/2.0/?" + urlencode({
            "method": "track.getTopTags", "artist": lead(artist), "track": title,
            "api_key": self.api_key, "format": "json", "autocorrect": 1
        })
        return genre_from(self.request(url).get("toptags", {}).get("tag", []))

    def find(self, artist, title, isrc=""):
        keys = (["isrc:" + norm(isrc)] if isrc else []) + ["track:" + norm(artist) + "|" + norm(title)]
        for key in keys:
            row = self.db.execute("SELECT genre, source FROM genres WHERE key=? AND expires>?",
                                  (key, int(time.time()))).fetchone()
            if row:
                return row[0], "cache/" + row[1]
        if self.offline:
            return "", "offline"
        self.request_failed = False
        sources = (("Last.fm", self.lastfm), ("Deezer", self.deezer), ("MusicBrainz", self.musicbrainz))
        for source, finder in sources:
            found = finder(artist, title)
            if found:
                genre = dj_canonical(found, strict=True)
                if genre:
                    for key in keys:
                        self.db.execute("INSERT OR REPLACE INTO genres VALUES (?, ?, ?, ?)",
                                        (key, genre, source, int(time.time()) + 90 * 86400))
                    self.db.commit()
                    return genre, source
        if not self.request_failed:
            for key in keys:
                self.db.execute("INSERT OR REPLACE INTO genres VALUES (?, ?, ?, ?)",
                                (key, "", "not-found", int(time.time()) + 7 * 86400))
            self.db.commit()
        return "", "not found"

    def save(self):
        self.db.commit()
        self.db.close()


def main():
    parser = argparse.ArgumentParser(description="Wyszukaj i zapisz brakujące gatunki dla Rekordbox")
    parser.add_argument("folder", nargs="?", default=".", help="Folder z WAV/FLAC")
    parser.add_argument("--dry-run", action="store_true", help="Pokaż gatunki bez zapisywania")
    parser.add_argument("--normalize-only", action="store_true", help="Tylko normalizuj istniejące gatunki; bez API")
    parser.add_argument("--offline", action="store_true", help="Tylko cache i normalizacja, bez API")
    parser.add_argument("--max-requests", type=int, default=500, help="Maksymalna liczba zapytań HTTP (0 = bez limitu)")
    parser.add_argument("--check-network", action="store_true", help="Sprawdź połączenie z MusicBrainz i Deezer")
    args = parser.parse_args()
    if args.max_requests < 0:
        parser.error('--max-requests must be >= 0')
    if args.check_network:
        lookup = DJLookup(max_requests=args.max_requests, offline=args.offline or args.normalize_only)
        endpoints = [
            ("MusicBrainz", "https://musicbrainz.org/ws/2/recording/?" + urlencode({"query": "artist:abba", "fmt": "json", "limit": 1}), True),
            ("Deezer", "https://api.deezer.com/search/track?" + urlencode({"q": "abba", "limit": 1}), False),
        ]
        accessible = 0
        for label, url, mb in endpoints:
            lookup.request(url, mb=mb)
            host = urlparse(url).hostname
            if host in lookup.successful_sources:
                accessible += 1
                print(f"[OK] {label}: połączenie HTTPS działa")
            else:
                print(f"[BRAK] {label}: sprawdź błąd powyżej")
        return 0 if accessible == len(endpoints) else 1
    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"[BŁĄD] Brak folderu: {folder}", file=sys.stderr)
        return 2
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
    print(f"[Genre] Pliki: {len(files)} | Last.fm (opcjonalny) + Deezer + MusicBrainz + SQLite cache")
    lookup = DJLookup(max_requests=args.max_requests, offline=args.offline or args.normalize_only)
    updated = kept = unknown = errors = 0
    try:
        for path in files:
            try:
                artist, title, current = tags(path)
                normalized = normalize_genre(current)
                if normalized:
                    if normalized == current:
                        kept += 1
                        continue
                    if not args.dry_run:
                        write(path, normalized)
                    updated += 1
                    print(f"[{'PODGLĄD' if args.dry_run else 'OK'}] {path.name}: {current} -> {normalized} (normalizacja)")
                    continue
                if args.normalize_only:
                    unknown += 1
                    continue
                if not artist or not title:
                    print(f"[BRAK DANYCH] {path.name}")
                    unknown += 1
                    continue
                isrc = (FLAC(path).get("isrc") or [""])[0] if path.suffix.lower() == ".flac" else ""
                genre, source = lookup.find(artist, title, isrc)
                if not genre:
                    print(f"[BRAK GATUNKU] {artist} - {title}")
                    unknown += 1
                    continue
                if not args.dry_run:
                    write(path, genre)
                updated += 1
                status = "PODGLĄD" if args.dry_run else "OK"
                print(f"[{status}] {artist} - {title} -> {genre} ({source})")
            except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                print(f"[BŁĄD] {path.name}: {exc}", file=sys.stderr)
                errors += 1
    except KeyboardInterrupt:
        print("\nPrzerwano, dotychczasowe zmiany zachowano.")
        return 130
    except RequestBudget as error:
        print(f"[LIMIT] {error}", file=sys.stderr)
        return 3
    except ConnectionError as error:
        print(f"[BŁĄD] {error}", file=sys.stderr)
        return 2
    finally:
        lookup.save()
    print(f"[Genre] Uzupełnione: {updated}, już poprawne: {kept}, brak danych: {unknown}, błędy: {errors}.")
    print("W Rekordbox zaznacz utwory i wybierz Reload Tag.")
    print(f"[Genre] Wykonane zapytania API: {lookup.requests}")
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
