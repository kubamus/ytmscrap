# ytmscrap

Proste CLI do pobierania **całych playlist z YouTube Music** do plików **FLAC** z metadanymi i okładkami, gotowych do importu w Rekordbox. Działa w **Git Bash na Windows 10/11** i w terminalu **macOS**.

> **Jakość:** YouTube Music dostarcza audio skompresowane stratnie. Konwersja do FLAC nie odzyskuje jakości lossless; zapobiega jednak **dalszej** stratnej kompresji. Pliki FLAC mogą być duże. Pobieraj tylko materiały, do których masz prawa lub zgodę.

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

4. Instalator doinstaluje brakujące `yt-dlp`, `FFmpeg`, `Deno` przez `winget` i skopiuje polecenie `ytmscrap` do `~/.local/bin`. Zamknij Git Bash, otwórz go ponownie i wpisz:

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

3. Instalator użyje Homebrew do instalacji brakujących `yt-dlp`, `ffmpeg`, `deno`. Jeśli Homebrew nie ma, spróbuje je zainstalować z oficjalnego instalatora (może wymagać hasła administratora i narzędzi Apple). Instaluje `ytmscrap` w `~/.local/bin` i aktualizuje PATH.
4. Otwórz nowy terminal i wpisz `ytmscrap`.

### Szybki start po instalacji

```bash
ytmscrap
```

Przykładowe pytania:

```text
=== ytmscrap | YouTube Music -> FLAC ===
Spotify -> YouTube Music: https://www.tunemymusic.com/

Gdzie zapisać? (Enter lub ./ = bieżący katalog): ./DJ
Link playlisty YouTube Music: https://music.youtube.com/playlist?list=PLQLDyACIOtUw

Folder: .../DJ
Format: FLAC
Metadane: tagi i okładki
Nazwy: Wykonawca - Tytuł.flac (bez numeru playlisty)

Rozpocząć pobieranie? [T/n]: t
```

Zostaw pierwsze pole **puste** lub wpisz `./`, aby zapisać pliki tam, gdzie w danej chwili pracuje terminal. Możesz też podać pełną ścieżkę. W Windows Git Bash działa zapis typu `C:\Music\DJ`.

Możesz podać URL od razu (folder nadal wybierzesz przez pytanie):

```bash
ytmscrap "https://music.youtube.com/playlist?list=PLQLDyACIOtUw"
```

Aby **przenieść playlistę ze Spotify do YouTube Music**, skorzystaj z: **https://www.tunemymusic.com/**. Ten link pojawia się też przy każdym uruchomieniu skryptu.

## Co robi program

- Pobiera najlepszy strumień audio udostępniony `yt-dlp` z YouTube Music.
- Konwertuje do FLAC za pomocą FFmpeg.
- Dodaje dostępne metadane i okładkę (nie zawsze wszystkie tagi są poprawne — zależy od YouTube).
- Nadaje nazwy `Artysta - Tytuł.flac`, bez numeru pozycji na playliście.
- Zapisuje `downloaded.txt` **w folderze docelowym**, żeby nie pobierać ponownie wcześniej przetworzonych utworów.
- Działa na Windows (Git Bash) i macOS. `Deno` i skrypty EJS pomagają yt-dlp obsłużyć obecne wymagania YouTube.

## Przydatne komendy

```bash
ytmscrap --help        # pomoc
ytmscrap --check       # sprawdzenie zależności
bash install.sh        # ponowna instalacja/naprawa PATH (w folderze repo)
bash tests/test-cli.sh  # testy bez pobierania audio
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

**`ytmscrap: command not found`** — otwórz nowy terminal lub w bieżącym uruchom `export PATH="$HOME/.local/bin:$PATH"`.

**`yt-dlp`/`ffmpeg`/`deno` nie znaleziono** — uruchom `ytmscrap --check`, sprawdź, czy `winget` lub Homebrew dodały programy do PATH, i ponów `bash install.sh`.

**Brak starszych utworów przy ponownym pobieraniu** — plik `downloaded.txt` w folderze zapisu służy do pomijania już pobranych pozycji. Jeśli wcześniej pobrałeś pliki z numerami playlisty, skrypt ich automatycznie nie przemianuje. Usuń wpisy w archiwum lub zmień nazwy starych plików ręcznie, jeśli potrzebujesz pobrania ich od nowa.

**FLAC a jakość dźwięku** — `ffprobe` pokaże FLAC o wysokim bitrate, ale to nie dowód na bezstratne źródło. YouTube Music nie daje strumienia lossless do pobrania przez yt-dlp.

**Rekordbox** — użyj opcji Import w Rekordbox i wskaż folder FLAC. Jeśli wydanie utworu na YouTube ma błędne tagi, sprawdź je przed setem.

## Kod źródłowy

Publiczne repozytorium: **https://github.com/kubamus/ytmscrap**

```bash
git clone https://github.com/kubamus/ytmscrap.git
cd ytmscrap
bash install.sh
```

## Licencja

MIT. Narzędzia `yt-dlp`, FFmpeg i Deno mają własne licencje i są instalowane niezależnie — nie są dołączone do repo.
