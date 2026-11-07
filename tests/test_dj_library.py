#!/usr/bin/env python3
"""Offline integration tests for DJ organizer and 1-5 energy ratings."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dj_library as dj
from mutagen.flac import FLAC, Picture


def make_audio(path: Path, genre: str = "Trap", duration: float = 1.0):
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
         f"sine=frequency=440:sample_rate=44100:duration={duration}",
         "-metadata", "artist=Test Artist", "-metadata", "title=Test Song",
         "-metadata", f"genre={genre}", "-y", str(path)],
        check=True,
    )


def pcm_hash(path: Path) -> str:
    data = subprocess.check_output(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
         "-map", "0:a:0", "-f", "s16le", "-acodec", "pcm_s16le", "-"]
    )
    return hashlib.sha256(data).hexdigest()


class LibraryTests(unittest.TestCase):
    def test_genre_grouping_preserves_specific_subgenres(self):
        self.assertEqual(dj.category("polski rap"), ("Polish Hip-Hop", "Polish Hip-Hop"))
        self.assertEqual(dj.category("Polish Trap"), ("Polish Hip-Hop", "Polish Trap"))
        self.assertEqual(dj.category("trap"), ("Hip-Hop", "Trap"))
        self.assertEqual(dj.category("Dance-Pop"), ("Pop", "Dance-Pop"))
        self.assertEqual(dj.category("Hard Techno"), ("Electronic", "Hard Techno"))
        self.assertEqual(dj.category("music"), ("Uncategorized", "Uncategorized"))

    def test_energy_rating_keeps_flac_samples_cover_and_other_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            song = Path(tmp) / "Artist - Track.flac"
            make_audio(song, "Polish Hip-Hop")
            audio = FLAC(song)
            cover = Picture()
            cover.type = 3
            cover.mime = "image/png"
            cover.data = b"picture-test"
            audio.add_picture(cover)
            audio.save()
            before = pcm_hash(song)
            store = dj.EnergyStore(Path(tmp) / "cache.sqlite3")
            try:
                store.save(song, 5, None, "manual")
                self.assertEqual(store.read(song)[0], 5)
                self.assertEqual(store.read(song)[2], "manual")
                self.assertEqual(FLAC(song).get("genre"), ["Polish Hip-Hop"])
                self.assertEqual(len(FLAC(song).pictures), 1)
                self.assertEqual(FLAC(song).get("energy"), ["5"])
                self.assertEqual(before, pcm_hash(song))
            finally:
                store.close()

    def test_estimate_and_existing_manual_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            song = folder / "Track.flac"
            make_audio(song, duration=3)
            energy, score = dj.estimate_energy(song)
            self.assertIn(energy, range(1, 6))
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)
            store = dj.EnergyStore(folder / "energy.sqlite3")
            store.save(song, 1, None, "manual")
            store.close()
            # Existing manual ratings must not change during analysis.
            args = type("Args", (), dict(action="analyze", path=str(folder),
                                          force=False, write=True))()
            prior = dj.DB_PATH
            dj.DB_PATH = folder / "energy.sqlite3"
            try:
                self.assertEqual(dj.cmd_energy(args), 0)
                self.assertEqual((FLAC(song).get("energy") or [""])[0], "1")
            finally:
                dj.DB_PATH = prior

    def test_organize_preview_and_m3u8_import_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            songs = root / "Music"
            songs.mkdir()
            rap = songs / "Artist - Rap.flac"
            pop = songs / "Artist - Pop.flac"
            make_audio(rap, "Polish Trap")
            make_audio(pop, "Dance-Pop")
            store = dj.EnergyStore(root / "energy.sqlite3")
            store.save(rap, 5, None, "manual")
            store.save(pop, 3, None, "manual")
            store.close()
            prior = dj.DB_PATH
            dj.DB_PATH = root / "energy.sqlite3"
            try:
                args = type("Args", (), dict(folder=str(songs), output=None,
                                              mode="playlists", dry_run=True))()
                self.assertEqual(dj.cmd_organize(args), 0)
                self.assertFalse((songs / "_DJ_Playlists").exists())
                args.dry_run = False
                self.assertEqual(dj.cmd_organize(args), 0)
                playlist = songs / "_DJ_Playlists" / "Genres" / "Polish Hip-Hop" / "Polish Trap.m3u8"
                self.assertTrue(playlist.exists())
                paths = playlist.read_text(encoding="utf-8").splitlines()
                self.assertEqual(paths[0], "#EXTM3U")
                self.assertTrue((playlist.parent / paths[1]).resolve().samefile(rap))
                self.assertTrue((songs / "_DJ_Playlists" / "Energy" / "Energy 5.m3u8").exists())
                self.assertTrue((songs / "_DJ_Playlists" / "Genres" / "Pop" / "Dance-Pop.m3u8").exists())
                self.assertEqual(dj.cmd_organize(args), 0)  # Ignore generated output.
                self.assertEqual(len(dj.audio_files(songs, songs / "_DJ_Playlists")), 2)
                self.assertEqual(pcm_hash(rap), pcm_hash(rap))
            finally:
                dj.DB_PATH = prior

    def test_copy_mode_does_not_move_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DJ"
            source.mkdir()
            song = source / "Track.flac"
            make_audio(song, "Rock")
            out = root / "Sorted"
            args = type("Args", (), dict(folder=str(source), output=str(out),
                                          mode="copy", dry_run=False))()
            self.assertEqual(dj.cmd_organize(args), 0)
            self.assertTrue(song.exists())
            copy = out / "Rock" / "Rock" / "Track.flac"
            self.assertTrue(copy.exists())
            self.assertEqual(pcm_hash(song), pcm_hash(copy))
            self.assertTrue((out / "Playlists" / "Genres" / "Rock" / "All.m3u8").exists())

    def test_wav_ratings_use_sidecar_without_modifying_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            song = root / "Song.wav"
            make_audio(song, "Pop")
            before = song.read_bytes()
            store = dj.EnergyStore(root / "energy.sqlite3")
            store.save(song, 4, None, "manual")
            self.assertEqual(store.read(song)[0], 4)
            store.close()
            self.assertEqual(before, song.read_bytes())

if __name__ == "__main__":
    unittest.main()
