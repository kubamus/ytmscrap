# ytmscrap

Proste CLI do pobierania **pojedynczych utworów i całych playlist z YouTube oraz YouTube Music** do plików **WAV lub FLAC** z metadanymi i okładkami, gotowych do importu w Rekordbox. Tryb Rekordbox przycina szerokie miniatury YouTube do formatu 1:1. Narzędzie potrafi też znormalizować gatunki `Genre`, korzystając z Last.fm (opcjonalnie), Deezer i MusicBrainz oraz lokalnego cache SQLite. Działa w **Git Bash na Windows 10/11** i w terminalu **macOS**.

> **Jakość:** YouTube Music dostarcza audio skompresowane stratnie (AAC/Opus). WAV i FLAC powstają z tego samego źródła i **nie poprawiają jego jakości**. WAV zapisuje nieskompresowany PCM, a FLAC kompresuje bezstratnie, więc oba brzmią tak samo. WAV zajmuje zwykle więcej miejsca. Pobieraj tylko materiały, do których masz prawa lub zgodę.

## Instalacja

**Najprościej:** uruchom **jedną komendę** w Git Bash (Windows) lub Terminalu (macOS):

```bash
curl -fsSL https://raw.githubusercontent.com/kubamus/ytmscrap/main/install.sh | bash -s -- kubamus/ytmscrap
```

Polecenie pobierze skrypt z GitHuba i zainstaluje brakujące narzędzia. Ponieważ wykonuje kod z internetu, używaj tylko zaufanego repozytorium; możesz najpierw przejrzeć plik `install.sh`. Repo musi być publiczne i mieć gałąź `main`.

Jeśli wolisz nie uruchamiać instalatora z internetu, użyj instalacji z ZIP poniżej.


### Windows (Git Bash)

1. Upewnij się, że masz [Git for Windows / Git Bash](https://git-scm.com/download/win) i [App Installer (`winget`)](https://learn.microsoft.com/windows/package-manager/winget/).
2. Pobierz projekt przez **Code → Download ZIP** na GitHubie i rozpakuj go lub użyj `git clone`.
3. Otwórz **Git Bash w katalogu projektu** i uruchom:

   ```bash
   bash install.sh
   ```

4. Instalator doinstaluje brakujące `yt-dlp`, `FFmpeg`, `Deno` i `Python 3.12` przez `winget`, a pakiet `Mutagen` w osobnym środowisku Pythona i skopiuje polecenie `ytmscrap` do `~/.local/bin`. Zamknij Git Bash, otwórz go ponownie i wpisz:

   ```bash
   ytmscrap
   ```

Instalacja `winget` może wymagać potwierdzenia zgód lub uprawnień systemu. Jeśli narzędzie nie jest jeszcze w PATH, uruchom nową sesję Git Bash i sprawdź `ytmscrap --check`.

### macOS (Terminal)

1. Pobierz ZIP projektu i rozpakuj go lub sklonuj repozytorium przez `git`.
2. W terminalu przejdź do katalogu projektu, po czym wpisz:

   ```bash
   bash install.sh
   ```

3. Instalator użyje Homebrew do instalacji brakujących `yt-dlp`, `ffmpeg`, `deno` i `python`, a następnie skonfiguruje `Mutagen` w osobnym środowisku. Jeśli Homebrew nie ma, spróbuje je zainstalować z oficjalnego instalatora (może wymagać hasła administratora i narzędzi Apple). Instaluje `ytmscrap` w `~/.local/bin` i aktualizuje PATH.
4. Otwórz nowy terminal i wpisz `ytmscrap`. Jeśli chcesz uruchomić go w tym samym oknie, wykonaj `source ~/.zshrc`, a potem `ytmscrap --check`.

### Aktualizacja CLI

Po jednorazowym zainstalowaniu programu wystarczy wpisać w **Git Bash (Windows)** lub **Terminalu (macOS)**:

```bash
ytmscrap update
```

Możesz też użyć `ytmscrap --update`. Komenda **najpierw sprawdza plik `VERSION` w GitHubie** i uruchamia instalator tylko wtedy, gdy dostępna jest nowsza wersja. W takim przypadku pobiera aktualny instalator z publicznego repo `kubamus/ytmscrap`, aktualizuje **CLI, moduł gatunków, moduł Rekordbox i moduł proxy** oraz sprawdza brakujące zależności. Nie kasuje pobranych plików, folderów ani historii `downloaded.txt`. Zainstalowane programy, które już działają (yt-dlp, FFmpeg, Deno), pozostają bez zmian; instalator nie wymusza ich aktualizacji.

Podczas zwykłego używania CLI sprawdza aktualizacje maksymalnie raz na 24 godziny. Gdy dostępna jest nowa wersja, pokazuje polecenie `ytmscrap update`. Brak internetu nie blokuje programu. `ytmscrap --version` pokazuje zainstalowaną wersję. Automatyczne sprawdzanie możesz wyłączyć przez `YTMSCRAP_NO_UPDATE_CHECK=1`. Każde nowe wydanie musi zwiększyć numer w pliku `VERSION` (`major.minor.patch`).

**Pierwsze uruchomienie:** starsza wersja `ytmscrap` nie zna jeszcze komendy `update`. Wykonaj poniższe polecenie tylko raz, aby ją dodać:

```bash
curl -fsSL https://raw.githubusercontent.com/kubamus/ytmscrap/main/install.sh | bash -s -- kubamus/ytmscrap
```

Instalator uruchamia kod pobrany z GitHuba; przed aktualizacją możesz przejrzeć `install.sh` w repozytorium. Jeśli pobieranie się nie uda, `ytmscrap update` zgłosi błąd zamiast uruchamiać niepełny plik.

### Szybki start po instalacji

```bash
ytmscrap
```

Przykładowe pytania:

```text
=== ytmscrap | YouTube Music -> WAV / FLAC ===
Spotify -> YouTube Music: https://www.tunemymusic.com/

Gdzie zapisać? (Enter lub ./ = bieżący katalog): ./DJ
Link utworu lub playlisty YouTube / YouTube Music: https://music.youtube.com/playlist?list=PLQLDyACIOtUw

Wybierz format audio:
  1) WAV  - bez kompresji, wieksze pliki (jakosc zrodla YouTube)
  2) FLAC - bezstratna kompresja, mniejsze pliki [domyslnie]
Format [1/2] (Enter = FLAC): 1

Źródło: playlista
Folder: .../DJ
Format: WAV (bez dodatkowej stratnej kompresji)
Metadane: tagi; osobny plik JPG
Nazwy: Wykonawca - Tytuł.wav (bez numeru playlisty)

Rozpocząć pobieranie? [T/n]: t
...
Automatycznie uzupełnić gatunki Genre? [T/n]: t
```

Zostaw pierwsze pole **puste** lub wpisz `./`, aby zapisać pliki tam, gdzie w danej chwili pracuje terminal. Możesz też podać pełną ścieżkę. W Windows Git Bash działa zapis typu `C:\Music\DJ`.

Możesz podać link do utworu lub playlisty od razu (folder nadal wybierzesz przez pytanie):

```bash
ytmscrap "https://music.youtube.com/playlist?list=PLQLDyACIOtUw"
```

### Pobieranie jednej piosenki

Uruchom `ytmscrap`, wybierz folder i wklej link do **pojedynczego utworu** zamiast playlisty:

```text
$ ytmscrap
Gdzie zapisać? (Enter lub ./ = bieżący katalog): ./
Link utworu lub playlisty YouTube / YouTube Music: https://music.youtube.com/watch?v=BaW_jenozKc

Wybierz format audio:
  1) WAV
  2) FLAC [domyślnie]
Format [1/2] (Enter = FLAC): 2

Źródło: pojedynczy utwór
...
```

Możesz też podać link od razu (na macOS, w Git Bash lub na Windows):

```bash
# YouTube Music
ytmscrap "https://music.youtube.com/watch?v=BaW_jenozKc"

# YouTube
ytmscrap "https://www.youtube.com/watch?v=BaW_jenozKc"

# Krótki link
ytmscrap "https://youtu.be/BaW_jenozKc"

# Jedna piosenka, nawet gdy URL zawiera list=...
ytmscrap "https://www.youtube.com/watch?v=BaW_jenozKc&list=PLQLDyACIOtUw"

# Jedna piosenka i tryb Rekordbox
ytmscrap --rekordbox "https://music.youtube.com/watch?v=BaW_jenozKc"
```

Dla linków do utworów program używa `--no-playlist`, dzięki czemu **nie pobierze całej playlisty** nawet wtedy, gdy link zawiera parametr `list`. Adresy `/playlist?list=...` nadal pobierają całą playlistę za pomocą `--yes-playlist`. Obsługuje też linki `/shorts/...` i `/live/...`.

W obu trybach dostępne są WAV/FLAC, metadane, okładki i opcjonalne uzupełnianie gatunków. Pobierany jest dźwięk z podanego filmu, więc jego jakość i tytuł zależą od źródła YouTube.

Aby **przenieść playlistę ze Spotify do YouTube Music**, skorzystaj z: **https://www.tunemymusic.com/**. Ten link pojawia się też przy każdym uruchomieniu skryptu.

## Co robi program

- Pobiera najlepszy dostępny strumień audio udostępniony `yt-dlp` z pojedynczego filmu lub całej playlisty YouTube / YouTube Music.
- Przed pobraniem pyta o WAV (nieskompresowany PCM) lub FLAC (bezstratna kompresja, domyślnie); konwertuje za pomocą FFmpeg.
- FLAC: osadza dostępne tagi i okładkę w pliku. WAV: osadza dostępne tagi i zapisuje okładkę jako osobny JPG, ponieważ osadzanie grafiki w WAV nie jest obsługiwane w tym trybie. Część aplikacji może ignorować metadane WAV.
- Nadaje nazwy `Artysta - Tytuł.wav` lub `Artysta - Tytuł.flac`, bez numeru pozycji na playliście.
- Zapisuje historię pobrań w folderze docelowym: `downloaded.txt` dla FLAC i `downloaded-wav.txt` dla WAV. Możesz pobrać obie wersje bez kasowania historii.
- Działa na Windows (Git Bash) i macOS. `Deno` i skrypty EJS pomagają yt-dlp obsłużyć obecne wymagania YouTube.

## Tryb Rekordbox: FLAC + kwadratowe okładki

Podczas pobierania program pyta, czy przygotować pliki dla rekordbox. Opcja jest domyślnie wyłączona. Możesz włączyć ją od razu:

```bash
ytmscrap --rekordbox "https://music.youtube.com/playlist?list=TWOJA_PLAYLISTA"
```

Naprawa już pobranych plików (także w podfolderach):

```bash
ytmscrap --fix-rekordbox .                         # bieżący folder
ytmscrap --fix-rekordbox "/Users/me/Music/DJ"      # wybrany folder
ytmscrap --fix-rekordbox . --dry-run               # podgląd
```

- FLAC: zmienia prostokątną okładkę na kwadrat 600×600 i usuwa wyraźne czarne pasy osadzone w obrazie (także gdy plik JPG jest już kwadratowy). Zachowuje audio, tagi i inne grafiki. Poprawne kwadratowe JPEG/PNG zostają bez zmian.
- WAV, MP3, M4A, Opus, Ogg, AAC, AIFF: tworzy FLAC obok oryginału; zachowuje tagi. Jeśli artist/title są puste, może uzupełnić je z nazwy Artysta - Tytuł. Istniejącego FLAC nie nadpisuje.
- Okładkę pobiera z pliku audio lub z JPG/PNG/WEBP o tej samej nazwie obok utworu.
- Przy pobieraniu poprawia tylko nowe pliki. WAV + tryb Rekordbox daje WAV oraz dodatkowy FLAC.
- MP3/Opus nie odzyskają jakości przy konwersji do FLAC. Zmiana grafiki w FLAC nie koduje dźwięku ponownie.
- W rekordbox użyj Collection → Reload Tag, by odświeżyć miniatury.

## Automatyczne darmowe proxy przy limitach YouTube

**Domyślnie włączone.** Program najpierw pobiera bez proxy. Jeśli YouTube zgłosi blokadę bota lub limit zapytań (np. HTTP 429), sam szuka publicznych proxy, sprawdza je równolegle i ponawia niedokończone pobieranie.

```bash
ytmscrap "https://www.youtube.com/watch?v=BaW_jenozKc"
ytmscrap --rekordbox "https://music.youtube.com/playlist?list=TWOJA_PLAYLISTA"

# Wyłącz awaryjne proxy dla jednego uruchomienia:
ytmscrap --no-auto-proxy "https://www.youtube.com/watch?v=BaW_jenozKc"
```

- **Nie trzeba podawać `--auto-proxy`.** Starsza flaga nadal działa, by nie psuć skryptów.
- Proxy nie bierze udziału w zwykłych, udanych pobraniach. Tylko wykryty błąd limitu/bota uruchamia fallback.
- Pobiera aktualne listy darmowych proxy HTTP z `monosans/proxy-list` i `maximilianfeix/free-proxy-list` na GitHubie. **Nie zapisuje stałej listy IP.**
- Sprawdza do 48 adresów przez HTTPS, testując 12 równolegle; następnie do 16 przez `yt-dlp`, testując 6 równolegle. Może spróbować maksymalnie 3 działających proxy podczas pobierania.
- Pliki już pobrane pozostają na dysku, a historia `downloaded.txt` pozwala pominąć gotowe utwory po ponowieniu playlisty.
- Przez publiczne proxy program nie przekazuje konfiguracji `yt-dlp` (np. plików cookies). Nie ma gwarancji, że darmowe proxy zadziałają.
- **Uwaga:** operator publicznego proxy może poznać Twój adres IP i odwiedzane hosty. Jeśli nie akceptujesz tego ryzyka, uruchamiaj `--no-auto-proxy`. Nie loguj się przez publiczne proxy.

## Diagnostyka połączenia z API gatunków

Gdy skrypt zgłasza błędy API (np. `URLError` na macOS), zaktualizuj instalację:

```bash
curl -fsSL https://raw.githubusercontent.com/kubamus/ytmscrap/main/install.sh | bash -s -- kubamus/ytmscrap
source ~/.zshrc
ytmscrap --check-genres
```

Instalator konfiguruje `certifi` z aktualnymi certyfikatami HTTPS. Skrypt nadal **weryfikuje certyfikaty** (nie stosuje `verify=False`). Test wyświetla konkretny powód błędu: SSL, brak DNS, timeout lub kod HTTP. Jeśli występuje błąd certyfikatu także po aktualizacji, sprawdź certyfikaty proxy/VPN i ustawienia sieci; nie wyłączaj SSL.

Nieudane zapytania sieciowe **nie trafiają do cache jako brak gatunku**. Stare puste wpisy są pomijane, więc po naprawie połączenia można od razu ponowić `ytmscrap --fix-genres .`. Jeśli oba serwisy są niedostępne, program przerwie skan zamiast błędnie oznaczać wszystkie utwory jako nierozpoznane.

## Automatyczne gatunki Genre

`ytmscrap --fix-genres` uzupełnia puste tagi i **normalizuje już istniejące gatunki** bez zbędnych zapytań HTTP. Działa rekurencyjnie z FLAC i WAV, także z osobnymi plikami pobranymi z TIDAL.

```bash
# Najpierw podgląd: nie zmienia plików muzycznych.
ytmscrap --fix-genres "$HOME/Music/DJ" --dry-run

# Normalizuj gatunki bez używania internetu:
ytmscrap --fix-genres "$HOME/Music/DJ" --normalize-only

# Uzupełnij brakujące gatunki i normalizuj istniejące:
ytmscrap --fix-genres "$HOME/Music/DJ"

# Używaj wyłącznie lokalnego cache:
ytmscrap --fix-genres "$HOME/Music/DJ" --offline

# Przetwarzaj większe biblioteki w częściach:
ytmscrap --fix-genres "$HOME/Music/DJ" --max-requests 1000
```

**Last.fm (opcjonalny):** ustaw klucz API jako `LASTFM_API_KEY`. Bez niego program użyje Deezer i MusicBrainz; nie trzeba podawać klucza żadnej z tych usług.

```bash
export LASTFM_API_KEY="YOUR_LASTFM_API_KEY"
ytmscrap --fix-genres "$HOME/Music/DJ"
```

**Kolejność źródeł:** istniejący gatunek → SQLite cache (ISRC lub wykonawca + tytuł) → Last.fm (gdy jest klucz) → Deezer → MusicBrainz. Nie pobiera kolejnych źródeł po pierwszym znalezionym gatunku. Sprawdza tytuły i wykonawców przed przypisaniem gatunku. `--max-requests` ogranicza liczbę zapytań w jednym uruchomieniu (domyślnie 500); można wznowić polecenie, korzystając z cache.

**Gatunki pod DJ sety:** normalizuje `dnb` → `Drum & Bass`, `polski rap` → `Polish Hip-Hop`, `hardtechno` → `Hard Techno`. Zachowuje rozróżnienie m.in. `Jumpstyle`, `Hardtekk`, `Hardtek`, `Hardstyle`, `Rawstyle`, `Frenchcore`, `Uptempo Hardcore`, `Neurofunk`, `Disco Polo` i `Polish Trap`. Nie zgaduje polskiego gatunku wyłącznie na podstawie narodowości artysty. Nieznane, istniejące gatunki zostają bez zmian.

**Cache i limity:** `~/.cache/ytmscrap/genres.sqlite3`; dodatnie wpisy 90 dni, udane wyszukiwania bez wyniku 7 dni. Błędy połączeń, 429 i 5xx nie trafiają do cache jako brak gatunku. Zapytania są wysyłane pojedynczo z odstępami: MusicBrainz co najmniej 1,2 s, inne serwisy 0,65 s, z dodatkowymi przerwami po 429/5xx. <https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting>

**Zapis:** w FLAC zmienia tylko Vorbis Comment `GENRE` bez konwersji audio. Dla WAV używa FFmpeg i kopiowania strumienia PCM do nowego kontenera. Importując zmiany do Rekordbox, zaznacz utwory i wybierz **Reload Tag**. Przed masowym uruchomieniem skopiuj kilka przykładowych plików i przetestuj na nich `--dry-run`.

Program nie zawiera automatycznego lokalnego modelu AI do klasyfikacji nierozpoznanych utworów. Gdy serwisy nie zwrócą wiarygodnego gatunku, pozostawia tag pusty zamiast zgadywać.

## Przydatne komendy

```bash
ytmscrap update             # aktualizuj CLI i moduły, jeśli jest nowa wersja
ytmscrap --version         # pokaż zainstalowaną wersję
ytmscrap --check-genres    # test połączenia z bazami gatunków
ytmscrap --fix-genres .    # napraw gatunki w istniejących plikach
ytmscrap --help        # pomoc
ytmscrap --check       # sprawdzenie zależności
bash install.sh        # ponowna instalacja/naprawa PATH (w folderze repo)
bash tests/test-cli.sh        # testy bez pobierania audio
bash tests/test-install.sh    # test instalatora (mock)
python3 -m unittest discover -s tests -p 'test_genres.py' -v  # tagi
```

Aktualizacja narzędzi:

```bash
# Windows (Git Bash)
winget upgrade --id yt-dlp.yt-dlp -e
winget upgrade --id Gyan.FFmpeg -e
winget upgrade --id DenoLand.Deno -e

# macOS
brew upgrade yt-dlp ffmpeg deno
```

## Problemy

**`zsh: command not found: ytmscrap` (macOS)** — skrypt instalacyjny działa w osobnym procesie i nie może zmienić `PATH` obecnej sesji. Wpisz:
```bash
source ~/.zshrc
ytmscrap --check
```
Jeżeli nadal nie działa, sprawdź:
```bash
ls -l ~/.local/bin/ytmscrap
~/.local/bin/ytmscrap --check
```
Jeśli nie ma pliku, ponów instalację i sprawdź komunikat błędu instalatora.

**`ytmscrap: command not found` (Windows Git Bash)** — otwórz nowy terminal lub wpisz `source ~/.bashrc`.

**`yt-dlp`/`ffmpeg`/`deno`/`python` nie znaleziono** — uruchom `ytmscrap --check`, sprawdź, czy `winget` lub Homebrew dodały programy do PATH, i ponów `bash install.sh`.

**Brak starszych utworów przy ponownym pobieraniu** — pliki `downloaded.txt` (FLAC) i `downloaded-wav.txt` (WAV) w folderze zapisu służą do pomijania już pobranych pozycji. Jeśli wcześniej pobrałeś pliki z numerami playlisty, skrypt ich automatycznie nie przemianuje. Usuń wpisy w archiwum lub zmień nazwy starych plików ręcznie, jeśli potrzebujesz pobrania ich od nowa.

**WAV/FLAC a jakość dźwięku** — `ffprobe` może pokazać wysoki bitrate, ale to nie dowód na bezstratne źródło. YouTube Music nie daje oryginalnych WAV ani FLAC przez yt-dlp. Konwersja z AAC/Opus nie odzyskuje utraconych danych.

**Rekordbox** — importuj pliki WAV lub FLAC. FLAC ma lepszą obsługę osadzonych okładek i tagów; przy WAV obraz znajduje się obok pliku. Jeśli wydanie utworu na YouTube ma błędne tagi, sprawdź je przed setem.

## Kod źródłowy

Publiczne repozytorium: **https://github.com/kubamus/ytmscrap**

```bash
git clone https://github.com/kubamus/ytmscrap.git
cd ytmscrap
bash install.sh
```

## Licencja

MIT. Narzędzia `yt-dlp`, FFmpeg i Deno mają własne licencje i są instalowane niezależnie — nie są dołączone do repo.

## DJ library: genre playlists and energy (1–5)

These commands work offline after genre tagging. They do not query MusicBrainz or Discogs again.

```bash
# Estimate each song's energy (preview only)
ytmscrap --energy analyze "$HOME/Music/DJ"

# Save ratings; keep existing values by default
ytmscrap --energy analyze "$HOME/Music/DJ" --write

# Read/set a rating for one song
ytmscrap --energy get "$HOME/Music/DJ/Artist - Song.flac"
ytmscrap --energy set "$HOME/Music/DJ/Artist - Song.flac" 5

# Force re-analysis (also replaces manual ratings)
ytmscrap --energy analyze "$HOME/Music/DJ" --write --force

# Generate M3U8 playlists grouped by genre, subgenre, and energy
ytmscrap --organize-library "$HOME/Music/DJ" --dry-run
ytmscrap --organize-library "$HOME/Music/DJ"

# Optional copies arranged into genre folders; originals stay put
ytmscrap --organize-library "$HOME/Music/DJ" --mode copy --output "$HOME/Music/DJ-Organized" --dry-run
ytmscrap --organize-library "$HOME/Music/DJ" --mode copy --output "$HOME/Music/DJ-Organized"
```

The program keeps specific genres (Trap, Dance-Pop, Hard Techno, etc.) and groups
them into practical playlists for Polish Hip-Hop, Hip-Hop, Pop, Rock, R&B, Polish Party,
and Electronic. It does not guess a track is Polish based on a generic Trap or Pop tag.
Tracks without a genre go to Uncategorized.

The 1–5 energy score is a rough offline estimate based on three audio excerpts,
volume, attack rate and contrast. It is **not** a trained mood/party-energy model.
Inspect and override important tracks. Manual ratings persist unless you specify
`--force`. FLAC uses custom `ENERGY`, `ENERGY_SCORE`, `ENERGY_SOURCE` tags,
without re-encoding audio; WAV ratings live only in the local SQLite sidecar
at `~/.cache/ytmscrap/energy.sqlite3`. Rekordbox may not display custom ENERGY
tags, so the tool exports `Energy/Energy N.m3u8` playlists too.

The default is playlist-only mode, which never moves audio and preserves Rekordbox
file paths. The optional copy mode duplicates audio into genre folders and builds
playlists pointing to the copies. It never deletes originals. Import the M3U8
files into Rekordbox, and use Reload Tag after editing FLAC metadata.

## Export a song list

Create an inventory of all supported audio files in a folder. Subfolders are included by default. This does **not** change or move any songs, and no network/API requests are made.

```bash
# Spreadsheet-friendly CSV (default): song-list.csv inside the folder
ytmscrap --export-songs "$HOME/Music/DJ"

# Plain artist - title list
ytmscrap --export-songs "$HOME/Music/DJ" --format txt

# Detailed JSON, including genres and saved 1-5 energy ratings
ytmscrap --export-songs "$HOME/Music/DJ" --format json

# Select your output path and include only songs directly in the folder
ytmscrap --export-songs "$HOME/Music/DJ" --output "$HOME/Desktop/dj-library.csv" --no-recursive
```

CSV and JSON include artist, title, album, album artist, normalized genre, genre group,
year, BPM, key, saved energy (if set), energy source, ISRC, duration, format and
relative path. TXT contains one `Artist - Title` per line. CSV is saved with a
UTF-8 BOM to open Polish characters correctly in spreadsheet apps. MP3, M4A,
FLAC, WAV, OGG/Opus, AAC and AIFF files are recognized; energy scores are
read from the FLAC tags or the existing WAV cache. Missing fields remain blank.
Songs with invalid tags stay in the list using their filenames and raise a
warning. Output is rewritten on each export; audio files are never overwritten.
