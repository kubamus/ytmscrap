#!/usr/bin/env python3
"""Offline tests: no YouTube or metadata API calls."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import genre_tagger as g
from mutagen.flac import FLAC, Picture


def decoded_hash(path):
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                             "-f", "s16le", "-acodec", "pcm_s16le", "-"],
                            capture_output=True, check=True)
    return hashlib.sha256(result.stdout).hexdigest()


class GenreTests(unittest.TestCase):
    def test_matching_rejects_wrong_artist_or_remix(self):
        self.assertGreater(g.confidence("California", "White 2115", "California", "White 2115"), .99)
        self.assertEqual(g.confidence("California", "White 2115", "California", "Different Artist"), 0)
        self.assertEqual(g.confidence("California (DJ Remix)", "White 2115", "California", "White 2115"), 0)
        self.assertEqual(g.genre_from([{"name": "Music", "count": 50},
                                       {"name": "Hip-Hop/Rap", "count": 3}]), "Hip-Hop/Rap")

    def test_api_fallback_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            lookup = g.Lookup(Path(tmp) / "cache.json")
            api = [
                {"recordings": [{"id": "123", "title": "California",
                                 "artist-credit": [{"name": "White 2115"}]}]},
                {"genres": []},
                {"data": [{"title": "California", "artist": {"name": "White 2115"},
                           "album": {"id": 42}}]},
                {"genres": {"data": [{"name": "Hip-Hop/Rap"}]}},
            ]
            with patch.object(lookup, "request", side_effect=api):
                self.assertEqual(lookup.find("White 2115", "California"), ("Hip-Hop/Rap", "Deezer"))
            lookup.save()
            with patch.object(lookup, "request", side_effect=AssertionError("Cache expected")):
                self.assertEqual(lookup.find("White 2115", "California")[0], "Hip-Hop/Rap")

    def test_file_tags_and_audio_not_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for ext in ("wav", "flac"):
                path = Path(tmp) / f"White 2115 - California.{ext}"
                subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                                "-i", "sine=frequency=440:sample_rate=48000:duration=0.2",
                                "-metadata", "title=California", "-metadata", "artist=White 2115",
                                "-metadata", "genre=Music", str(path)], check=True)
                if ext == "flac":
                    audio = FLAC(path)
                    picture = Picture()
                    picture.type = 3
                    picture.mime = "image/png"
                    picture.data = b"embedded-cover-test"
                    audio.add_picture(picture)
                    audio.save()
                before = decoded_hash(path)
                self.assertEqual(g.tags(path), ("White 2115", "California", "Music"))
                g.write(path, "Hip-Hop/Rap")
                self.assertEqual(g.tags(path), ("White 2115", "California", "Hip-Hop/Rap"))
                self.assertEqual(before, decoded_hash(path))
                if ext == "flac":
                    self.assertEqual(len(FLAC(path).pictures), 1)
                else:
                    self.assertIn(b"IGNR", path.read_bytes())

    def test_ssl_failures_do_not_cache_empty_genre(self):
        import ssl
        from urllib.error import URLError
        from contextlib import redirect_stderr
        from io import StringIO

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "genres.json"
            lookup = g.Lookup(cache)
            error = URLError(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"))
            log = StringIO()
            with patch.object(g, "urlopen", side_effect=error), redirect_stderr(log):
                with self.assertRaises(ConnectionError):
                    lookup.find("White 2115", "California")
            self.assertIn("CERTIFICATE_VERIFY_FAILED", log.getvalue())
            self.assertIn("certifi", log.getvalue())
            self.assertEqual(lookup.cache, {})
            lookup.save()
            self.assertFalse(cache.exists())

    def test_stale_empty_genre_is_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "genres.json"
            cache.write_text('{"white 2115|california": {"genre": "", "source": "Deezer", "at": 9999999999}}')
            lookup = g.Lookup(cache)
            with patch.object(lookup, "musicbrainz", return_value="Hip-Hop"):
                self.assertEqual(lookup.find("White 2115", "California")[0], "Hip-Hop")
            self.assertEqual(lookup.cache["white 2115|california"]["genre"], "Hip-Hop")

    def test_protect_existing_genre(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "White 2115 - California.flac"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "sine=frequency=440:duration=0.2",
                            "-metadata", "title=California", "-metadata", "artist=White 2115",
                            "-metadata", "genre=Rock", str(path)], check=True)
            # Already-correct Genre must stay intact; the CLI only edits unknown/Music.
            self.assertNotIn(g.norm(g.tags(path)[2]), g.INVALID)


if __name__ == "__main__":
    unittest.main()
