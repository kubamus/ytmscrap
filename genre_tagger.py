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
        self.dirty = False
        self.failed_sources = set()
        self.successful_sources = set()
        self.request_failed = False
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def request(self, url, mb=False):
        host = urlparse(url).hostname or "nieznany serwer"
        if mb:
            remaining = 1.1 - (time.monotonic() - self.last_mb)
            if remaining > 0:
                time.sleep(remaining)
            self.last_mb = time.monotonic()
        req = Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=12, context=self.ssl_context) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise ValueError("API zwróciło nieprawidłowy format danych")
            if data.get("error"):
                raise ValueError(f"API zwróciło błąd: {data['error']}")
            self.successful_sources.add(host)
            self.failed_sources.discard(host)
            return data
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            self.request_failed = True
            self.failed_sources.add(host)
            reason = error.reason if isinstance(error, URLError) else error
            if isinstance(error, HTTPError):
                detail = f"HTTP {error.code} {error.reason}"
            else:
                detail = str(reason)
            print(f"  [BŁĄD API] {host}: {detail}", file=sys.stderr)
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

def main():
    parser = argparse.ArgumentParser(description="Wyszukaj i zapisz brakujące gatunki dla Rekordbox")
    parser.add_argument("folder", nargs="?", default=".", help="Folder z WAV/FLAC")
    parser.add_argument("--dry-run", action="store_true", help="Pokaż gatunki bez zapisywania")
    parser.add_argument("--check-network", action="store_true", help="Sprawdź połączenie z MusicBrainz i Deezer")
    args = parser.parse_args()
    if args.check_network:
        lookup = Lookup()
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
    print(f"[Genre] Pliki: {len(files)} | MusicBrainz + Deezer")
    lookup = Lookup()
    updated = kept = unknown = errors = 0
    try:
        for path in files:
            try:
                artist, title, current = tags(path)
                if norm(current) not in INVALID:
                    kept += 1
                    continue
                if not artist or not title:
                    print(f"[BRAK DANYCH] {path.name}")
                    unknown += 1
                    continue
                genre, source = lookup.find(artist, title)
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
    except ConnectionError as error:
        print(f"[BŁĄD] {error}", file=sys.stderr)
        return 2
    finally:
        lookup.save()
    print(f"[Genre] Uzupełnione: {updated}, już poprawne: {kept}, brak danych: {unknown}, błędy: {errors}.")
    print("W Rekordbox zaznacz utwory i wybierz Reload Tag.")
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
