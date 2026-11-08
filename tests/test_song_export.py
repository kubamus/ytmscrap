#!/usr/bin/env python3
"""Offline song-list export tests: formats, recursion, tags and safety."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dj_library as dj
from mutagen.flac import FLAC


def make_audio(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=44100:duration=0.3",
                    "-y", str(path)], check=True)


def args(folder: Path, fmt=None, output=None, no_recursive=False):
    return SimpleNamespace(folder=str(folder), format=fmt,
                           output=str(output) if output else None,
                           no_recursive=no_recursive)


class ExportTests(unittest.TestCase):
    def test_recursive_csv_has_metadata_genre_and_saved_energy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            song = root / "Rap" / "Żabson - Kiedy.flac"
            make_audio(song)
            audio = FLAC(song)
            audio["artist"] = ["Żabson"]
            audio["title"] = ["Kiedy"]
            audio["album"] = ["Album, One"]
            audio["date"] = ["2023-08-12"]
            audio["genre"] = ["Polish Trap"]
            audio["isrc"] = ["PL1234567890"]
            audio["ENERGY"] = ["4"]
            audio["ENERGY_SOURCE"] = ["manual"]
            audio.save()

            self.assertEqual(dj.cmd_export(args(root)), 0)
            path = root / "song-list.csv"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["artist"], "Żabson")
            self.assertEqual(row["title"], "Kiedy")
            self.assertEqual(row["album"], "Album, One")
            self.assertEqual(row["genre"], "Polish Trap")
            self.assertEqual(row["genre_group"], "Polish Hip-Hop")
            self.assertEqual(row["energy"], "4")
            self.assertEqual(row["energy_source"], "manual")
            self.assertEqual(row["year"], "2023")
            self.assertEqual(row["relative_path"], "Rap/Żabson - Kiedy.flac")
            self.assertTrue(song.exists())

    def test_txt_json_and_no_recursive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            top = root / "Artist - Main.mp3"
            nested = root / "Other" / "Nested.wav"
            make_audio(top)
            make_audio(nested)
            with open(root / "ignored.txt", "w") as out:
                out.write("not a song")
            self.assertEqual(dj.cmd_export(args(root, fmt="txt", no_recursive=True)), 0)
            self.assertEqual((root / "song-list.txt").read_text().splitlines(),
                             ["Artist - Main"])
            self.assertEqual(dj.cmd_export(args(root, fmt="json")), 0)
            songs = json.loads((root / "song-list.json").read_text())
            self.assertEqual(len(songs), 2)
            self.assertEqual({row["format"] for row in songs}, {"MP3", "WAV"})
            self.assertEqual({row["relative_path"] for row in songs},
                             {"Artist - Main.mp3", "Other/Nested.wav"})
            self.assertTrue(all("genre" in row and "energy" in row for row in songs))

    def test_invalid_tags_still_show_file_and_audio_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            invalid = root / "Broken.flac"
            invalid.write_bytes(b"not real flac")
            self.assertEqual(dj.cmd_export(args(root, fmt="json")), 1)
            rows = json.loads((root / "song-list.json").read_text())
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "Broken")
            self.assertEqual(rows[0]["relative_path"], "Broken.flac")
            self.assertEqual(invalid.read_bytes(), b"not real flac")
            # Explicitly reject an audio output path, even if requested.
            self.assertEqual(dj.cmd_export(args(root, output=invalid)), 2)
            self.assertEqual(invalid.read_bytes(), b"not real flac")

    def test_spreadsheet_formula_escape_and_auto_format(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            song = root / "test.flac"
            make_audio(song)
            audio = FLAC(song)
            audio["artist"] = ["=DANGEROUS()"]
            audio["title"] = ["Song"]
            audio.save()
            self.assertEqual(dj.cmd_export(args(root)), 0)
            with (root / "song-list.csv").open(encoding="utf-8-sig", newline="") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["artist"], "'=DANGEROUS()")
            self.assertEqual(dj.cmd_export(args(root, output=root / "other.json")), 0)
            rows = json.loads((root / "other.json").read_text())
            self.assertEqual(rows[0]["artist"], "=DANGEROUS()")


if __name__ == "__main__":
    unittest.main()
