#!/usr/bin/env bash
# One-time setup for Windows Git Bash and macOS.
set -euo pipefail

err() { printf '[BŁĄD] %s\n' "$*" >&2; }
info() { printf '\n==> %s\n' "$*"; }

# Supports local ZIP/clone installation and a single-line download from GitHub.
remote_repo=${1:-}
tmp_script=''
tmp_helper=''
if [ -n "$remote_repo" ]; then
  if [[ ! "$remote_repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
    err 'Repozytorium powinno mieć postać OWNER/REPO.'
    exit 2
  fi
  command -v curl >/dev/null 2>&1 || { err 'Brak curl.'; exit 1; }
  tmp_script=$(mktemp)
  tmp_helper=$(mktemp)
  trap 'rm -f "$tmp_script" "$tmp_helper"' EXIT
  info "Pobieranie CLI z publicznego repozytorium $remote_repo"
  curl -fL --retry 2 --output "$tmp_script" "https://raw.githubusercontent.com/$remote_repo/main/ytmscrap"
  script_source=$tmp_script
  curl -fL --retry 2 --output "$tmp_helper" "https://raw.githubusercontent.com/$remote_repo/main/genre_tagger.py"
  helper_source=$tmp_helper
else
  base_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
  script_source="$base_dir/ytmscrap"
  helper_source="$base_dir/genre_tagger.py"
  if [ ! -f "$script_source" ] || [ ! -f "$helper_source" ]; then
    err 'Brak ytmscrap lub genre_tagger.py obok install.sh. Pobierz całe repozytorium lub użyj trybu OWNER/REPO.'
    exit 1
  fi
fi

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) os=windows ;;
  Darwin*) os=macos ;;
  *) err 'Obsługiwane systemy: Windows (Git Bash) i macOS.'; exit 1 ;;
esac

info "Instalowanie ytmscrap ($os)"
printf 'Wymagania: yt-dlp, FFmpeg, Deno, Python 3.10+ i Mutagen. Zainstaluję brakujące narzędzia.\n'

# Package managers may add executable links to locations missing from the
# current shell's PATH; discover those directories before and after install.
setup_windows_path() {
  if command -v cygpath >/dev/null 2>&1; then
    local win_app_data=${LOCALAPPDATA:-}
    if [ -n "$win_app_data" ]; then
      local unix_app_data
      unix_app_data=$(cygpath -u "$win_app_data")
      export PATH="$unix_app_data/Microsoft/WinGet/Links:$PATH"
    else
      export PATH="$HOME/AppData/Local/Microsoft/WinGet/Links:$PATH"
    fi
  fi
}

setup_brew_path() {
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
}

python_exec=''
find_python() {
  local name path
  python_exec=''
  for name in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$name" >/dev/null 2>&1 && "$name" -c 'import sys; assert sys.version_info >= (3,10)' >/dev/null 2>&1; then
      python_exec=$name
      return 0
    fi
  done
  if [ "$os" = windows ]; then
    for path in "$HOME/AppData/Local/Programs/Python/Python313/python.exe" "$HOME/AppData/Local/Programs/Python/Python312/python.exe"; do
      if [ -f "$path" ] && "$path" -c 'import sys; assert sys.version_info >= (3,10)' >/dev/null 2>&1; then
        python_exec=$path
        return 0
      fi
    done
  fi
  return 1
}

if [ "$os" = windows ]; then
  setup_windows_path
  if ! command -v winget.exe >/dev/null 2>&1 && ! command -v winget >/dev/null 2>&1; then
    err 'Nie znaleziono winget. Zainstaluj App Installer z Microsoft Store i ponów próbę.'
    exit 1
  fi
  winget_cmd=winget.exe
  if ! command -v winget.exe >/dev/null 2>&1; then
    winget_cmd=winget
  fi
  for item in 'yt-dlp:yt-dlp.yt-dlp' 'ffmpeg:Gyan.FFmpeg' 'deno:DenoLand.Deno'; do
    tool=${item%%:*}
    package=${item#*:}
    if ! command -v "$tool" >/dev/null 2>&1; then
      info "Instalowanie $tool ($package) przez winget"
      "$winget_cmd" install --exact --id "$package" --source winget --accept-source-agreements --accept-package-agreements
      setup_windows_path
    else
      printf '[OK] %s już zainstalowany\n' "$tool"
    fi
  done
  if ! find_python; then
    info 'Instalowanie Python 3.12 przez winget'
    "$winget_cmd" install --exact --id Python.Python.3.12 --source winget --accept-source-agreements --accept-package-agreements
    setup_windows_path
  fi
else
  setup_brew_path
  if ! command -v brew >/dev/null 2>&1; then
    info 'Brak Homebrew. Instaluję Homebrew z oficjalnej strony.'
    command -v curl >/dev/null 2>&1 || { err 'Brak curl.'; exit 1; }
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    setup_brew_path
  fi
  command -v brew >/dev/null 2>&1 || { err 'Homebrew nie jest dostępny po instalacji.'; exit 1; }
  missing=()
  for tool in yt-dlp ffmpeg deno; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing+=("$tool")
    else
      printf '[OK] %s już zainstalowany\n' "$tool"
    fi
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    info "Instalowanie przez Homebrew: ${missing[*]}"
    brew install "${missing[@]}"
  fi
  if ! find_python; then
    info 'Instalowanie Python przez Homebrew'
    brew install python
    setup_brew_path
  fi
fi

# Private Python environment for metadata tagging.
if ! find_python; then
  err 'Python 3.10+ nie jest dostępny. Otwórz nowy terminal i ponów instalację.'
  exit 1
fi
share_dir="$HOME/.local/share/ytmscrap"
mkdir -p -- "$share_dir"
cp -- "$helper_source" "$share_dir/genre_tagger.py"
if [ ! -x "$share_dir/venv/bin/python" ] && [ ! -x "$share_dir/venv/Scripts/python.exe" ]; then
  info 'Tworzenie środowiska Python'
  "$python_exec" -m venv "$share_dir/venv"
fi
if [ -x "$share_dir/venv/Scripts/python.exe" ]; then
  venv_python="$share_dir/venv/Scripts/python.exe"
else
  venv_python="$share_dir/venv/bin/python"
fi
info 'Instalowanie Mutagen'
"$venv_python" -m pip install --disable-pip-version-check 'mutagen>=1.47,<2'

# Install in user's home (no system-wide write permissions needed).
bin_dir="$HOME/.local/bin"
mkdir -p -- "$bin_dir"
cp -- "$script_source" "$bin_dir/ytmscrap"
chmod +x "$bin_dir/ytmscrap"

# Only add exact lines that aren't present yet. No PATH duplicates on re-run.
append_line() {
  local line=$1 target=$2
  touch "$target"
  if ! grep -Fqx -- "$line" "$target"; then
    printf '\n%s\n' "$line" >> "$target"
  fi
}
path_line='export PATH="$HOME/.local/bin:$PATH"'
if [ "$os" = windows ]; then
  append_line "$path_line" "$HOME/.bashrc"
  append_line "$path_line" "$HOME/.bash_profile"
else
  # Homebrew on Apple Silicon is often not already in a fresh PATH.
  if [ -x /opt/homebrew/bin/brew ]; then
    append_line 'eval "$(/opt/homebrew/bin/brew shellenv)"' "$HOME/.zprofile"
  elif [ -x /usr/local/bin/brew ]; then
    append_line 'eval "$(/usr/local/bin/brew shellenv)"' "$HOME/.zprofile"
  fi
  append_line "$path_line" "$HOME/.zprofile"
  append_line "$path_line" "$HOME/.zshrc"
  append_line "$path_line" "$HOME/.bash_profile"
fi
export PATH="$bin_dir:$PATH"

info 'Sprawdzanie zależności'
missing_any=0
for tool in yt-dlp ffmpeg deno; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '[OK] %s\n' "$tool"
  else
    printf '[UWAGA] %s nie jest jeszcze w PATH\n' "$tool"
    missing_any=1
  fi
done

printf '\nZainstalowano ytmscrap: %s/ytmscrap\n' "$bin_dir"
if [ "$missing_any" -ne 0 ]; then
  printf 'Otwórz nowy terminal i uruchom: ytmscrap --check\n'
  printf 'Jeśli brak nadal występuje, sprawdź ścieżki narzędzi z winget/Homebrew.\n'
else
  printf 'Otwórz nowy terminal i wpisz: ytmscrap\n'
fi
printf 'Spotify -> YouTube Music: https://www.tunemymusic.com/\n'
