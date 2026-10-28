#!/usr/bin/env python3
"""Make a music library Rekordbox-friendly: FLAC, tags, square embedded covers."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

try:
    from mutagen.flac import FLAC, Picture
except ImportError:
    print('[BŁĄD] Brak Mutagen. Uruchom ponownie instalator ytmscrap.', file=sys.stderr)
    raise SystemExit(2)

EXTENSIONS = {'.flac', '.wav', '.mp3', '.m4a', '.mp4', '.opus', '.ogg', '.aac', '.aiff', '.aif'}
SIDE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def ffmpeg(*args, source=None):
    return subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', *args],
                          input=source, capture_output=True, check=True).stdout


def sidecar(path):
    for ext in SIDE_EXTENSIONS:
        img = path.with_suffix(ext)
        if img.is_file():
            return img.read_bytes()
    return None


def cover_for(path):
    if path.suffix.lower() == '.flac':
        covers = FLAC(path).pictures
        if covers:
            return next((p.data for p in covers if p.type == 3), covers[0].data)
    # yt-dlp puts the cover in an attached picture video stream for some formats.
    try:
        data = ffmpeg('-i', str(path), '-map', '0:v:0', '-frames:v', '1',
                      '-c:v', 'png', '-f', 'image2pipe', 'pipe:1')
        if data:
            return data
    except subprocess.CalledProcessError:
        pass
    return sidecar(path)


def cover_details(data):
    result = subprocess.run(['ffprobe', '-v', 'error', '-f', 'image2pipe', '-i', 'pipe:0',
                             '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                             '-of', 'json'], input=data, capture_output=True, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    if not streams:
        raise ValueError('Nie można odczytać wymiarów okładki')
    return streams[0]['width'], streams[0]['height']


def square_picture(data):
    w, h = cover_details(data)
    # No loss from repeatedly running the command on an already square JPEG/PNG.
    if w == h and (data.startswith(b'\xff\xd8\xff') or data.startswith(b'\x89PNG')):
        mime = 'image/jpeg' if data.startswith(b'\xff\xd8\xff') else 'image/png'
        return data, mime, w, h
    jpg = ffmpeg('-i', 'pipe:0', '-vf', 'crop=min(iw\\,ih):min(iw\\,ih),scale=600:600:flags=lanczos',
                 '-frames:v', '1', '-q:v', '2', '-f', 'image2', '-vcodec', 'mjpeg', 'pipe:1', source=data)
    if not jpg:
        raise ValueError('Konwersja okładki nie powiodła się')
    return jpg, 'image/jpeg', 600, 600


def add_cover(path, source_cover, dry_run=False):
    if source_cover is None:
        return False, 'brak okładki'
    data, mime, w, h = square_picture(source_cover)
    audio = FLAC(path)
    front = next((p for p in audio.pictures if p.type == 3), None)
    if front and front.data == data and front.mime == mime:
        return False, 'okładka już kwadratowa'
    if dry_run:
        return True, f'okładka {w}x{h}'
    picture = Picture()
    picture.type = 3
    picture.mime = mime
    picture.width, picture.height = w, h
    picture.depth = 24
    picture.data = data
    others = [p for p in audio.pictures if p.type != 3]
    audio.clear_pictures()
    audio.add_picture(picture)
    for other in others:
        audio.add_picture(other)
    audio.save()
    return True, f'okładka {w}x{h}'


def fill_tags(path, stem, dry_run=False):
    audio = FLAC(path)
    if ' - ' not in stem:
        return
    artist, title = stem.split(' - ', 1)
    changed = False
    if not audio.get('artist') and artist.strip():
        audio['artist'] = artist.strip()
        changed = True
    if not audio.get('title') and title.strip():
        audio['title'] = title.strip()
        changed = True
    if changed and not dry_run:
        audio.save()


def process(path, dry_run=False):
    if path.suffix.lower() not in EXTENSIONS or not path.is_file():
        return 'skip', 'nieobsługiwany plik'
    cover = cover_for(path)
    if path.suffix.lower() == '.flac':
        if cover is None:
            return 'skip', 'brak okładki'
        if dry_run:
            changed, detail = add_cover(path, cover, dry_run=True)
        else:
            # Work on a copy so a failed tag write never damages the original.
            fd, name = tempfile.mkstemp(prefix='.ytmscrap-', suffix='.flac', dir=path.parent)
            os.close(fd)
            temp = Path(name)
            try:
                shutil.copy2(path, temp)
                changed, detail = add_cover(temp, cover)
                if changed:
                    os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
        return ('updated' if changed else 'skip'), detail

    target = path.with_suffix('.flac')
    if target.exists():
        return 'skip', 'FLAC już istnieje'
    if dry_run:
        return 'created', f'powstanie {target.name}'
    fd, name = tempfile.mkstemp(prefix='.ytmscrap-', suffix='.flac', dir=path.parent)
    os.close(fd)
    temp = Path(name)
    try:
        ffmpeg('-y', '-i', str(path), '-map', '0:a:0', '-map_metadata', '0',
               '-vn', '-c:a', 'flac', str(temp))
        fill_tags(temp, path.stem)
        add_cover(temp, cover)
        shutil.copystat(path, temp)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return 'created', f'utworzono {target.name}'


def main():
    parser = argparse.ArgumentParser(description='FLAC + kwadratowe okładki dla rekordbox')
    parser.add_argument('folder', nargs='?', default='.', help='Folder z muzyką')
    parser.add_argument('--dry-run', action='store_true', help='Tylko podgląd')
    parser.add_argument('--from-list', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.from_list:
        try:
            paths = [Path(line) for line in args.from_list.read_text(encoding='utf-8').splitlines() if line]
        except OSError as error:
            parser.error(str(error))
    else:
        folder = Path(args.folder).expanduser()
        if not folder.is_dir():
            parser.error(f'Brak folderu: {folder}')
        paths = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS)
    counts = {'created': 0, 'updated': 0, 'skip': 0, 'error': 0}
    print(f'[Rekordbox] Pliki: {len(paths)} | FLAC + okładki 1:1' + (' | PODGLĄD' if args.dry_run else ''))
    try:
        for path in paths:
            try:
                status, detail = process(path, args.dry_run)
                counts[status] += 1
                print(f'[{status.upper()}] {path.name}: {detail}')
            except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
                counts['error'] += 1
                print(f'[BŁĄD] {path}: {error}', file=sys.stderr)
    except KeyboardInterrupt:
        print('\nPrzerwano.', file=sys.stderr)
        return 130
    print(f"[Rekordbox] Nowe: {counts['created']}, zmienione: {counts['updated']}, "
          f"pominięte: {counts['skip']}, błędy: {counts['error']}.")
    print('W rekordbox zaznacz utwory w Collection i wybierz Reload Tag.')
    return 1 if counts['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
