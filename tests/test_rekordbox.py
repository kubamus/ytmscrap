#!/usr/bin/env python3
"""Offline tests for Rekordbox artwork and lossless audio handling."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rekordbox as r
from mutagen.flac import FLAC, Picture


def run(*args):
    subprocess.run(args, stdout=subprocess.DEVNULL, check=True)


def pcm_hash(path):
    output = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                             '-f', 's16le', '-acodec', 'pcm_s16le', '-'],
                            capture_output=True, check=True).stdout
    return hashlib.sha256(output).digest()


class RekordboxTests(unittest.TestCase):
    def test_flac_square_cover_preserves_audio_and_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Artist - Track.flac'
            cover = Path(tmp) / 'cover.jpg'
            run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=red:s=1280x720:d=0.1', '-frames:v', '1', str(cover))
            run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'sine=frequency=440:sample_rate=48000:duration=1',
                '-metadata', 'artist=Artist', '-metadata', 'title=Track',
                '-metadata', 'genre=Rock', str(path))
            audio = FLAC(path)
            pic = Picture()
            pic.mime = 'image/jpeg'
            pic.type = 3
            pic.data = cover.read_bytes()
            pic.width, pic.height = 1280, 720
            audio.add_picture(pic)
            audio.save()
            before = pcm_hash(path)
            self.assertEqual(r.process(path)[0], 'updated')
            audio = FLAC(path)
            self.assertEqual(r.cover_details(audio.pictures[0].data), (600, 600))
            self.assertEqual(audio['genre'], ['Rock'])
            self.assertEqual(before, pcm_hash(path))
            self.assertEqual(r.process(path)[0], 'skip')

    def test_wav_conversion_keeps_original_and_sidecar_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Artist - Track.wav'
            run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'sine=frequency=440:sample_rate=48000:duration=0.2', str(path))
            run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=green:s=1280x720:d=0.1', '-frames:v', '1',
                str(path.with_suffix('.jpg')))
            before = pcm_hash(path)
            self.assertEqual(r.process(path)[0], 'created')
            target = path.with_suffix('.flac')
            self.assertTrue(path.exists())
            self.assertEqual(before, pcm_hash(target))
            self.assertEqual(FLAC(target)['artist'], ['Artist'])
            self.assertEqual(r.cover_details(FLAC(target).pictures[0].data), (600, 600))
            self.assertEqual(r.process(path)[0], 'skip')

    def test_square_jpeg_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'A - B.flac'
            pic_file = Path(tmp) / 'square.jpg'
            run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'sine=frequency=440:duration=0.2', str(path))
            run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=blue:s=640x640:d=0.1', '-frames:v', '1', str(pic_file))
            audio = FLAC(path)
            pic = Picture()
            pic.type = 3
            pic.mime = 'image/jpeg'
            pic.data = pic_file.read_bytes()
            audio.add_picture(pic)
            audio.save()
            self.assertEqual(r.process(path, dry_run=True)[0], 'skip')
            self.assertEqual(r.process(path)[0], 'skip')


if __name__ == '__main__':
    unittest.main()
