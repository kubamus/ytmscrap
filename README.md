# ytmscrap

Proste CLI do pobierania **pojedynczych utworów i całych playlist z YouTube oraz YouTube Music** do plików **WAV lub FLAC** z metadanymi i okładkami, gotowych do importu w Rekordbox. Tryb Rekordbox przycina szerokie miniatury YouTube do formatu 1:1. Narzędzie potrafi też wyszukać gatunek `Genre` na podstawie MusicBrainz i Deezer. Działa w **Git Bash na Windows 10/11** i w terminalu **macOS**.

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
Link utworu lub playlisty YouTube / YouTube Music: https://music.youtube.com/watch?v=BaW_jenozKcj

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
ytmscrap "https://music.youtube.com/watch?v=BaW_jenozKcj"

# YouTube
ytmscrap "https://www.youtube.com/watch?v=BaW_jenozKcj"

# Krótki link
ytmscrap "https://youtu.be/BaW_jenozKcj"

# Jedna piosenka, nawet gdy URL zawiera list=...
ytmscrap "https://www.youtube.com/watch?v=BaW_jenozKcj&list=PLQLDyACIOtUw"

# Jedna piosenka i tryb Rekordbox
ytmscrap --rekordbox "https://music.youtube.com/watch?v=BaW_jenozKcj"
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

Po pobraniu program pyta **„Automatycznie uzupełnić gatunki Genre?”**. Domyślnie próbuje naprawić gatunki w wybranym folderze. Bez pobierania utworów ponownie możesz użyć:

```bash
ytmscrap --fix-genres .                      # bieżący folder i podfoldery
ytmscrap --fix-genres "/Users/me/Music/DJ"   # wskazany folder
ytmscrap --fix-genres . --dry-run            # tylko pokaż propozycje
```

- Wyszukuje gatunki w **MusicBrainz** (nagranie lub wydanie) i, gdy brak danych, w **Deezer** (gatunek albumu). Nie wymaga klucza API. Działanie wymaga internetu.
- Sprawdza zgodność tytułu i wykonawcy. Nie zawsze znajdzie gatunek, zwłaszcza dla remixów, mashupów i mniej znanych polskich nagrań; zamiast zgadywać, pozostawia pole puste lub `Music`.
- Zmienia wyłącznie `Genre` — i tylko jeśli tag jest pusty lub ma wartość `Music`. Nie nadpisuje pozostałych gatunków.
- **FLAC**: zmienia tag Vorbis Comment bez ponownego kodowania audio; zachowuje okładkę. **WAV**: FFmpeg zapisuje `Genre` jako RIFF INFO/IGNR przez `-c:a copy`, czyli bez zmiany próbek audio; wymaga chwilowo miejsca na kopię pliku.
- Wyniki udanych zapytań zapisuje w `~/.cache/ytmscrap/genres-v1.json`. MusicBrainz ma limit **1 zapytanie na sekundę**, więc duże foldery mogą zająć kilka minut.
- Jeśli pole `Genre` nie odświeży się od razu w Rekordboxie, zaznacz utwory w **Collection** → **Reload Tag**. Przed użyciem tej opcji zwróć uwagę, że odświeża również inne tagi odczytane z pliku.

Uwaga: przy instalacji starszej wersji ponownie uruchom instalator, żeby pobrać `genre_tagger.py`, Python i Mutagen.

## Przydatne komendy

```bash
ytmscrap --check-genres    # test połączenia z MusicBrainz i Deezer
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
