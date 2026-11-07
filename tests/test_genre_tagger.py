from __future__ import annotations
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import genre_tagger as t
from mutagen.flac import FLAC


class GenresTest(unittest.TestCase):
    def test_dj_subgenres(self):
        cases = {
            "polska jumpstyle": "Jumpstyle",
            "slowed hardtekk": "Hardtekk",
            "hardtechno": "Hard Techno",
            "raw hardstyle": "Rawstyle",
            "dnb": "Drum & Bass",
            "polski rap": "Polish Hip-Hop",
            "discopolo": "Disco Polo",
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(t.normalize_genre(label), expected)

    def test_preserve_unknown_and_no_nationality_guess(self):
        self.assertEqual(t.normalize_genre("Rare Regional Style"), "Rare Regional Style")
        self.assertEqual(t.dj_canonical("rap", strict=True), "Hip-Hop")
        self.assertEqual(t.dj_canonical("polish", strict=True), "")
        self.assertEqual(t.dj_canonical("seen live", strict=True), "")

    def test_specific_tag_wins_if_relevant(self):
        self.assertEqual(t.normalize_genre("EDM; Hardtekk"), "Hardtekk")
        self.assertEqual(t.dj_best([("electronic", 100), ("hard techno", 40)]), "Hard Techno")
        self.assertEqual(t.dj_best([("electronic", 100), ("hard techno", 4)]), "Electronic")

    def test_sqlite_cache_reuse_and_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            from unittest.mock import patch
            home = Path(temp)
            with patch.object(Path, "home", return_value=home):
                lookup = t.DJLookup(offline=True)
                try:
                    lookup.db.execute("INSERT INTO genres VALUES (?, ?, ?, ?)",
                                      ("isrc:pl123", "Jumpstyle", "test", 4102444800))
                    lookup.db.commit()
                    with patch.object(lookup, "request", side_effect=AssertionError("network call")):
                        self.assertEqual(lookup.find("DJ", "Track", "PL123"), ("Jumpstyle", "cache/test"))
                        self.assertEqual(lookup.find("Unknown", "No Track"), ("", "offline"))
                finally:
                    lookup.save()

    def test_flac_audio_is_not_reencoded(self):
        with tempfile.TemporaryDirectory() as temp:
            song = Path(temp) / "DJ - Track.flac"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "sine=frequency=440:duration=0.2", "-c:a", "flac", str(song)], check=True)
            audio = FLAC(song)
            audio["title"] = ["Track"]
            audio["isrc"] = ["PL1234567890"]
            audio.save()
            def pcm_hash():
                out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(song), "-f", "s16le",
                                      "-acodec", "pcm_s16le", "-"], capture_output=True, check=True).stdout
                return hashlib.sha256(out).hexdigest()
            before = pcm_hash()
            t.write(song, "Hardtekk")
            self.assertEqual(before, pcm_hash())
            self.assertEqual(FLAC(song)["isrc"], ["PL1234567890"])
            self.assertEqual(FLAC(song)["genre"], ["Hardtekk"])


if __name__ == "__main__":
    unittest.main()
