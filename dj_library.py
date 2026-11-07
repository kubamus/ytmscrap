#!/usr/bin/env python3
"""Offline DJ genre playlists, safe copies and a 1-5 audio-energy estimate."""
from __future__ import annotations

import argparse
import csv
from array import array
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from mutagen.flac import FLAC

from genre_tagger import normalize_genre

EXTENSIONS = {".flac", ".wav"}
EXPORT_EXTENSIONS = EXTENSIONS | {".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".aif", ".aiff"}
EXPORT_COLUMNS = ("artist", "title", "album", "album_artist", "genre", "genre_group",
                  "year", "bpm", "key", "energy", "energy_source", "isrc",
                  "duration_seconds", "format", "relative_path")
DB_PATH = Path(os.environ.get("YTMSCRAP_ENERGY_DB", str(Path.home() / ".cache/ytmscrap/energy.sqlite3")))

# These groups reflect common open-format sets. Never guess a track is Polish
# based on a generic Hip-Hop, Trap or Pop tag.
GROUPS = {
    "Polish Hip-Hop": "Polish Hip-Hop",
    "Polish Trap": "Polish Hip-Hop",
    "Hip-Hop": "Hip-Hop",
    "Trap": "Hip-Hop",
    "Drill": "Hip-Hop",
    "UK Drill": "Hip-Hop",
    "Phonk": "Hip-Hop",
    "Drift Phonk": "Hip-Hop",
    "Pop": "Pop",
    "Polish Pop": "Pop",
    "Dance-Pop": "Pop",
    "Synth-Pop": "Pop",
    "Pop Rock": "Pop",
    "R&B": "R&B",
    "Disco Polo": "Polish Party",
    "Rock": "Rock",
    "Alternative Rock": "Rock",
    "Indie Rock": "Rock",
    "Punk Rock": "Rock",
    "Metal": "Rock",
    "Nu Metal": "Rock",
}
ELECTRONIC = {
    "Electronic", "EDM", "Dance", "House", "Deep House", "Tech House",
    "Bass House", "Afro House", "Electro House", "Progressive House",
    "Big Room", "Techno", "Melodic Techno", "Acid Techno",
    "Industrial Techno", "Schranz", "Trance", "Psytrance",
    "Eurodance", "Drum & Bass", "Liquid Drum & Bass",
    "Dancefloor Drum & Bass", "Neurofunk", "Jungle", "Dubstep",
    "Riddim", "UK Garage", "Hard Dance", "Hardstyle", "Rawstyle",
    "Jumpstyle", "Hardtekk", "Hardtek", "Hard Techno",
    "Hardcore", "Uptempo Hardcore", "Frenchcore", "Gabber",
    "Happy Hardcore", "Synthwave",
}


def category(raw: str) -> tuple[str, str]:
    genre = normalize_genre(raw or "")
    if not genre:
        return "Uncategorized", "Uncategorized"
    group = GROUPS.get(genre, "Electronic" if genre in ELECTRONIC else genre)
    return group, genre


def valid_energy(value: object) -> int | None:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return None
    return number if str(value).strip() == str(number) and 1 <= number <= 5 else None


def audio_files(folder: Path, excluded: Path | None = None) -> list[Path]:
    folder = folder.resolve()
    excluded = excluded.resolve() if excluded else None
    return sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in EXTENSIONS
        and not (excluded and p.resolve().is_relative_to(excluded))
    )


def read_genre(path: Path) -> str:
    if path.suffix.lower() == ".flac":
        return (FLAC(path).get("genre") or [""])[0]
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format_tags=genre",
           "-of", "json", str(path)]
    data = json.loads(subprocess.check_output(cmd, text=True))
    tags = data.get("format", {}).get("tags", {})
    return next((value for key, value in tags.items() if key.lower() == "genre"), "")


class EnergyStore:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS energy "
            "(path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, "
            "rating INTEGER NOT NULL, score REAL, source TEXT NOT NULL)"
        )

    def read(self, path: Path) -> tuple[int, float | None, str] | None:
        if path.suffix.lower() == ".flac":
            audio = FLAC(path)
            rating = valid_energy((audio.get("energy") or [""])[0])
            if rating:
                score_text = (audio.get("energy_score") or [""])[0]
                try:
                    score = float(score_text)
                except ValueError:
                    score = None
                return rating, score, (audio.get("energy_source") or ["tag"])[0]
        row = self.db.execute(
            "SELECT size, mtime_ns, rating, score, source FROM energy WHERE path=?",
            (str(path.resolve()),)
        ).fetchone()
        if not row:
            return None
        stat = path.stat()
        # Manual edits survive an audio file's timestamp change; automatic
        # estimates must be rerun if the source content may have changed.
        if row[4] != "manual" and (row[0], row[1]) != (stat.st_size, stat.st_mtime_ns):
            return None
        return row[2], row[3], row[4]

    def save(self, path: Path, rating: int, score: float | None, source: str):
        if path.suffix.lower() == ".flac":
            audio = FLAC(path)
            audio["ENERGY"] = [str(rating)]
            audio["ENERGY_SOURCE"] = [source]
            if score is None:
                audio.pop("ENERGY_SCORE", None)
            else:
                audio["ENERGY_SCORE"] = [f"{score:.2f}"]
            audio.save()  # Metadata only: no audio re-encoding.
        stat = path.stat()
        self.db.execute(
            "INSERT OR REPLACE INTO energy VALUES (?, ?, ?, ?, ?, ?)",
            (str(path.resolve()), stat.st_size, stat.st_mtime_ns, rating, score, source)
        )
        self.db.commit()

    def close(self):
        self.db.close()


def duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    return float(subprocess.check_output(cmd, text=True).strip())


def estimate_energy(path: Path) -> tuple[int, float]:
    """Heuristic: level + rhythmic attacks + short-term contrast, NOT a trained mood model."""
    length = duration(path)
    if length <= 0:
        raise ValueError("Invalid duration")
    samples = array("h")
    # Three short segments avoid classifying a quiet intro as a quiet track.
    segment = min(12.0, length)
    starts = sorted({max(0.0, (length - segment) * fraction)
                     for fraction in (0.12, 0.48, 0.82)})
    for start in starts:
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start:.3f}",
               "-i", str(path), "-t", f"{segment:.3f}", "-vn", "-ac", "1",
               "-ar", "11025", "-f", "s16le", "-acodec", "pcm_s16le", "-"]
        raw = subprocess.check_output(cmd, stderr=subprocess.PIPE, timeout=90)
        batch = array("h")
        batch.frombytes(raw[:len(raw) // 2 * 2])
        if sys.byteorder != "little":
            batch.byteswap()
        samples.extend(batch)
    if not samples:
        raise ValueError("No decoded audio")

    # Each 50 ms frame gets an RMS level; no extra numerical packages needed.
    width = 551
    frames = []
    total_square = 0
    for i in range(0, len(samples) - width + 1, width):
        piece = samples[i:i + width]
        square = sum(sample * sample for sample in piece)
        total_square += square
        frames.append(math.sqrt(square / width) / 32768.0)
    if not frames:
        raise ValueError("Audio too short")

    rms = math.sqrt(total_square / (len(frames) * width)) / 32768.0
    dbfs = 20 * math.log10(max(rms, 1e-9))
    ordered = sorted(frames)
    median = ordered[len(ordered) // 2]
    p90 = ordered[int((len(ordered) - 1) * .9)]
    # Count rising volume attacks per second; scale against local level.
    attacks = sum(
        1 for previous, current in zip(frames, frames[1:])
        if current > max(.015, median * .70) and current > previous * 1.28
    )
    attacks_per_second = attacks / (len(frames) * width / 11025)
    loud = max(0.0, min(1.0, (dbfs + 28) / 18))
    rhythm = max(0.0, min(1.0, attacks_per_second / 2.6))
    contrast = max(0.0, min(1.0, (p90 / max(median, .003) - 1) / 2.5))
    score = round(100 * (.30 * loud + .50 * rhythm + .20 * contrast), 2)
    rating = min(5, max(1, int(score // 20) + 1))
    return rating, score


def cmd_energy(args) -> int:
    path = Path(args.path).expanduser().resolve()
    store = EnergyStore()
    errors = 0
    try:
        if args.action == "set":
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                raise ValueError("Choose a FLAC or WAV file")
            store.save(path, args.rating, None, "manual")
            print(f"[ENERGY] {path.name}: {args.rating}/5 (manual)")
        elif args.action == "get":
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                raise ValueError("Choose a FLAC or WAV file")
            value = store.read(path)
            print(f"[ENERGY] {path.name}: " +
                  (f"{value[0]}/5 ({value[2]}; score={value[1]})" if value else "not set"))
        else:
            if not path.is_dir() and not path.is_file():
                raise ValueError("Folder or file not found")
            files = audio_files(path) if path.is_dir() else [path]
            for song in files:
                try:
                    existing = store.read(song)
                    if existing and not args.force:
                        print(f"[KEEP] {song.name}: {existing[0]}/5 ({existing[2]})")
                        continue
                    rating, score = estimate_energy(song)
                    if args.write:
                        store.save(song, rating, score, "audio-v1")
                    print(f"[{'SAVE' if args.write else 'PREVIEW'}] {song.name}: "
                          f"{rating}/5, score={score}")
                except (OSError, ValueError, subprocess.CalledProcessError,
                        subprocess.TimeoutExpired) as exc:
                    errors += 1
                    print(f"[ERROR] {song.name}: {exc}", file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    finally:
        store.close()
    return 1 if errors else 0


def safe_name(text: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")
    return value[:100] or "Unknown"


def same_content(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    # Only hash on path collisions. Never assume equal sizes imply equal audio.
    def digest(path: Path) -> str:
        sha = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest()
    return digest(left) == digest(right)


def playlist_write(path: Path, files: list[Path], preview: bool):
    if preview:
        print(f"[PREVIEW] {path}: {len(files)} tracks")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace only our playlist files, not users' audio or cue data.
    contents = "#EXTM3U\n" + "".join(
        os.path.relpath(song, path.parent).replace("\\", "/") + "\n"
        for song in files
    )
    path.write_text(contents, encoding="utf-8")
    print(f"[PLAYLIST] {path}: {len(files)} tracks")


def cmd_organize(args) -> int:
    source = Path(args.folder).expanduser().resolve()
    if not source.is_dir():
        print(f"[ERROR] Folder not found: {source}", file=sys.stderr)
        return 2
    output = (Path(args.output).expanduser().resolve() if args.output else
              (source / "_DJ_Playlists" if args.mode == "playlists" else
               source.parent / (source.name + "-Organized")))
    if output == source:
        print("[ERROR] Output must be different from source.", file=sys.stderr)
        return 2
    files = audio_files(source, excluded=output)
    groups = defaultdict(list)
    by_energy = defaultdict(list)
    store = EnergyStore()
    issues = 0
    try:
        for song in files:
            try:
                main, sub = category(read_genre(song))
                target = song
                if args.mode == "copy":
                    target_dir = output / safe_name(main) / safe_name(sub)
                    basename = safe_name(song.stem)[:90] + song.suffix.lower()
                    target = target_dir / basename
                    if target.exists() and not same_content(target, song):
                        digest = hashlib.sha256(str(song.relative_to(source)).encode()).hexdigest()[:8]
                        target = target_dir / (safe_name(song.stem)[:80] + "-" + digest + song.suffix.lower())
                    if target.exists() and not same_content(target, song):
                        raise FileExistsError(f"Refusing to overwrite a different file: {target}")
                    if not target.exists():
                        print(f"[{'PREVIEW' if args.dry_run else 'COPY'}] {song} -> {target}")
                        if not args.dry_run:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(song, target)
                groups[(main, sub)].append(target)
                rating = store.read(song)
                if rating:
                    by_energy[rating[0]].append(target)
            except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                issues += 1
                print(f"[ERROR] {song}: {exc}", file=sys.stderr)
        base = output if args.mode == "playlists" else output / "Playlists"
        all_by_group = defaultdict(list)
        for (main, sub), songs in groups.items():
            all_by_group[main].extend(songs)
            playlist_write(base / "Genres" / safe_name(main) /
                           (safe_name(sub) + ".m3u8"), songs, args.dry_run)
        for main, songs in all_by_group.items():
            playlist_write(base / "Genres" / safe_name(main) / "All.m3u8",
                           sorted(set(songs)), args.dry_run)
        for rating, songs in sorted(by_energy.items()):
            playlist_write(base / "Energy" / f"Energy {rating}.m3u8",
                           sorted(set(songs)), args.dry_run)
        print(f"[LIBRARY] {len(files)} tracks, {len(all_by_group)} genre groups, "
              f"{len(by_energy)} energy playlists, {issues} errors.")
    finally:
        store.close()
    return 1 if issues else 0


def tag_value(tags: dict, *keys: str) -> str:
    for key in keys:
        value = tags.get(key.lower())
        if isinstance(value, (tuple, list)):
            value = value[0] if value else ""
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def export_record(song: Path, folder: Path, store: EnergyStore) -> dict[str, str]:
    """Read tags only. Never change a song, decode audio or query online services."""
    if song.suffix.lower() == ".flac":
        audio = FLAC(song)
        tags = {key.lower(): value for key, value in audio.tags.items()} if audio.tags else {}
        seconds = audio.info.length
    else:
        data = json.loads(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags",
             "-of", "json", str(song)], text=True
        )).get("format", {})
        tags = {key.lower(): value for key, value in data.get("tags", {}).items()}
        seconds = float(data.get("duration") or 0)

    artist = tag_value(tags, "artist", "albumartist", "album_artist")
    title = tag_value(tags, "title")
    parts = song.stem.split(" - ", 1)
    if len(parts) == 2:
        artist = artist or parts[0]
        title = title or parts[1]
    title = title or song.stem
    raw_genre = tag_value(tags, "genre")
    group, genre = category(raw_genre)
    raw_date = tag_value(tags, "originaldate", "date", "year", "release_date")
    year_match = re.search(r"\\b(18|19|20|21)\\d{2}\\b", raw_date)
    energy = store.read(song) if song.suffix.lower() in EXTENSIONS else None
    return {
        "artist": artist,
        "title": title,
        "album": tag_value(tags, "album"),
        "album_artist": tag_value(tags, "albumartist", "album_artist"),
        "genre": "" if group == "Uncategorized" else genre,
        "genre_group": group,
        "year": year_match.group(0) if year_match else "",
        "bpm": tag_value(tags, "bpm", "tbpm"),
        "key": tag_value(tags, "initialkey", "initial_key", "key"),
        "energy": str(energy[0]) if energy else "",
        "energy_source": str(energy[2]) if energy else "",
        "isrc": tag_value(tags, "isrc"),
        "duration_seconds": f"{seconds:.2f}",
        "format": song.suffix[1:].upper(),
        "relative_path": song.relative_to(folder).as_posix(),
    }


def safe_csv_value(value: str) -> str:
    # Protect spreadsheet imports against formulas in untrusted song metadata.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\\t", "\\r")) else value


def cmd_export(args) -> int:
    source = Path(args.folder).expanduser().resolve()
    if not source.is_dir():
        print(f"[ERROR] Folder not found: {source}", file=sys.stderr)
        return 2
    output_hint = Path(args.output).expanduser() if args.output else None
    chosen = output_hint.suffix.lower().lstrip(".") if output_hint else ""
    fmt = args.format or (chosen if chosen in {"csv", "txt", "json"} else "csv")
    if output_hint and chosen in {"csv", "txt", "json"} and chosen != fmt:
        print("[ERROR] Output extension conflicts with --format.", file=sys.stderr)
        return 2
    output = output_hint.resolve() if output_hint else source / f"song-list.{fmt}"
    if output.suffix.lower() in EXPORT_EXTENSIONS:
        print("[ERROR] Refusing to overwrite an audio file.", file=sys.stderr)
        return 2
    paths = (source.iterdir() if args.no_recursive else source.rglob("*"))
    files = sorted(path for path in paths
                   if path.is_file() and path.suffix.lower() in EXPORT_EXTENSIONS)
    store = EnergyStore()
    rows = []
    failures = 0
    try:
        for song in files:
            try:
                rows.append(export_record(song, source, store))
            except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
                failures += 1
                print(f"[EXPORT ERROR] {song}: {exc}", file=sys.stderr)
                # Include the file in the inventory even when its tags are corrupt.
                row = dict.fromkeys(EXPORT_COLUMNS, "")
                row.update(title=song.stem, format=song.suffix[1:].upper(),
                           relative_path=song.relative_to(source).as_posix())
                rows.append(row)
    finally:
        store.close()
    rows.sort(key=lambda row: (row["artist"].casefold(), row["title"].casefold(),
                                row["relative_path"].casefold()))

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".ytmscrap-export-", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig" if fmt == "csv" else "utf-8",
                       newline="") as file:
            if fmt == "csv":
                writer = csv.DictWriter(file, fieldnames=EXPORT_COLUMNS)
                writer.writeheader()
                writer.writerows({key: safe_csv_value(row[key]) for key in EXPORT_COLUMNS}
                                 for row in rows)
            elif fmt == "txt":
                for row in rows:
                    title = f'{row["artist"]} - {row["title"]}' if row["artist"] else row["title"]
                    file.write(title + "\\n")
            else:
                json.dump(rows, file, ensure_ascii=False, indent=2)
                file.write("\\n")
        os.replace(tmp_name, output)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    print(f"[EXPORT] {len(rows)} songs -> {output} ({fmt.upper()}); {failures} tag errors.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize a DJ library without moving originals")
    sub = parser.add_subparsers(dest="command", required=True)

    organize = sub.add_parser("organize", help="Generate genre/energy playlists or genre folder copies")
    organize.add_argument("folder", nargs="?", default=".")
    organize.add_argument("--output", help="Destination directory")
    organize.add_argument("--mode", choices=["playlists", "copy"], default="playlists")
    organize.add_argument("--dry-run", action="store_true")

    export = sub.add_parser("export", help="Export a song list as CSV, TXT or JSON")
    export.add_argument("folder", nargs="?", default=".")
    export.add_argument("--format", choices=["csv", "txt", "json"], default=None)
    export.add_argument("--output", help="Path to the exported list")
    export.add_argument("--no-recursive", action="store_true", help="Only direct child files")

    energy = sub.add_parser("energy", help="Get, set or estimate energy (1-5)")
    actions = energy.add_subparsers(dest="action", required=True)
    get = actions.add_parser("get")
    get.add_argument("path")
    set_ = actions.add_parser("set")
    set_.add_argument("path")
    set_.add_argument("rating", type=int, choices=range(1, 6), metavar="{1,2,3,4,5}")
    analyze = actions.add_parser("analyze")
    analyze.add_argument("path", nargs="?", default=".")
    analyze.add_argument("--write", action="store_true", help="Save estimates (preview by default)")
    analyze.add_argument("--force", action="store_true", help="Replace existing, even manual ratings")

    args = parser.parse_args()
    if args.command == "organize":
        return cmd_organize(args)
    if args.command == "export":
        return cmd_export(args)
    return cmd_energy(args)


if __name__ == "__main__":
    raise SystemExit(main())
