#!/usr/bin/env bash
# Installer smoke test using fake dependencies; no network/no package writes.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/home"
for tool in yt-dlp ffmpeg deno; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$tmp/bin/$tool"
  chmod +x "$tmp/bin/$tool"
done
# Mock uname to simulate both platforms, without invoking a real package manager.
cat > "$tmp/bin/uname" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$YTMSCRAP_MOCK_UNAME"
FAKE
chmod +x "$tmp/bin/uname"
export PATH="$tmp/bin:$PATH"

# Simulate Python and its virtual environment without pip/network.
cat > "$tmp/bin/python3.14" <<'FAKEPY'
#!/usr/bin/env bash
if [ "$1" = -c ]; then exit 0; fi
if [ "$1" = -m ] && [ "$2" = venv ]; then
  mkdir -p "$3/bin"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$3/bin/python"
  chmod +x "$3/bin/python"
  exit 0
fi
exit 1
FAKEPY
chmod +x "$tmp/bin/python3.14"

cat > "$tmp/bin/brew" <<'FAKE'
#!/usr/bin/env bash
exit 0
FAKE
chmod +x "$tmp/bin/brew"
export YTMSCRAP_MOCK_UNAME=Darwin
HOME="$tmp/home" bash "$root/install.sh" > "$tmp/mac.log"
[ -x "$tmp/home/.local/bin/ytmscrap" ]
[ -f "$tmp/home/.local/share/ytmscrap/genre_tagger.py" ]
[ -f "$tmp/home/.local/share/ytmscrap/rekordbox.py" ]
grep -Fqx 'export PATH="$HOME/.local/bin:$PATH"' "$tmp/home/.zprofile"
grep -Fqx 'export PATH="$HOME/.local/bin:$PATH"' "$tmp/home/.zshrc"

# Check reinstall is idempotent for shell startup files.
HOME="$tmp/home" bash "$root/install.sh" > /dev/null
[ "$(grep -Fc 'export PATH="$HOME/.local/bin:$PATH"' "$tmp/home/.zprofile")" -eq 1 ]

cat > "$tmp/bin/winget.exe" <<'FAKE'
#!/usr/bin/env bash
exit 0
FAKE
chmod +x "$tmp/bin/winget.exe"
export YTMSCRAP_MOCK_UNAME=MINGW64_NT-10.0
HOME="$tmp/home" bash "$root/install.sh" > "$tmp/win.log"
grep -Fqx 'export PATH="$HOME/.local/bin:$PATH"' "$tmp/home/.bashrc"
grep -Fqx 'export PATH="$HOME/.local/bin:$PATH"' "$tmp/home/.bash_profile"

# Remote one-line installer: mock curl to return the CLI script, no internet.
cat > "$tmp/bin/curl" <<'FAKE'
#!/usr/bin/env bash
if [ "${YTMSCRAP_MOCK_CURL_FAIL:-0}" = 1 ]; then exit 22; fi
while [ "$#" -gt 0 ]; do
  if [ "$1" = --output ]; then
    shift
    dest="$1"
    shift
    url=""
    for arg in "$@"; do url="$arg"; done
    case "$url" in
      */install.sh) cp "$YTMSCRAP_REMOTE_INSTALLER" "$dest" ;;
      */genre_tagger.py) cp "$YTMSCRAP_REMOTE_HELPER" "$dest" ;;
      */rekordbox.py) cp "$YTMSCRAP_REMOTE_REKORDBOX" "$dest" ;;
      */ytmscrap) cp "$YTMSCRAP_REMOTE_FIXTURE" "$dest" ;;
      *) exit 1 ;;
    esac
    exit 0
  fi
  shift
done
exit 1
FAKE
chmod +x "$tmp/bin/curl"
export YTMSCRAP_REMOTE_INSTALLER="$root/install.sh"
export YTMSCRAP_REMOTE_FIXTURE="$root/ytmscrap"
export YTMSCRAP_REMOTE_HELPER="$root/genre_tagger.py"
export YTMSCRAP_REMOTE_REKORDBOX="$root/rekordbox.py"
rm -f "$tmp/home/.local/bin/ytmscrap"
HOME="$tmp/home" bash "$root/install.sh" demo-user/ytmscrap > "$tmp/remote.log"
[ -x "$tmp/home/.local/bin/ytmscrap" ]
grep -Fq 'publicznego repozytorium demo-user/ytmscrap' "$tmp/remote.log"
head -n 1 "$tmp/home/.local/share/ytmscrap/genre_tagger.py" | grep -Fq '#!/usr/bin/env python3'
head -n 1 "$tmp/home/.local/share/ytmscrap/rekordbox.py" | grep -Fq '#!/usr/bin/env python3'

# Self-update should invoke the official installer without touching the system,
# replace CLI as well as both Python helper files, and work on both shells.
for mock_os in Darwin MINGW64_NT-10.0; do
  export YTMSCRAP_MOCK_UNAME="$mock_os"
  printf '#!/usr/bin/env bash\nprintf "old CLI\\n"\n' > "$tmp/home/.local/bin/ytmscrap"
  printf 'old helper\n' > "$tmp/home/.local/share/ytmscrap/genre_tagger.py"
  printf 'old rekordbox\n' > "$tmp/home/.local/share/ytmscrap/rekordbox.py"
  HOME="$tmp/home" bash "$root/ytmscrap" --update > "$tmp/update.log"
  cmp -s "$tmp/home/.local/bin/ytmscrap" "$root/ytmscrap"
  cmp -s "$tmp/home/.local/share/ytmscrap/genre_tagger.py" "$root/genre_tagger.py"
  cmp -s "$tmp/home/.local/share/ytmscrap/rekordbox.py" "$root/rekordbox.py"
  grep -Fq 'Aktualizacja zakończona' "$tmp/update.log"
done

# The alias must work too and a failed download must not overwrite the CLI.
export YTMSCRAP_MOCK_UNAME=Darwin
HOME="$tmp/home" bash "$root/ytmscrap" update > "$tmp/update-alias.log"
grep -Fq 'Aktualizacja zakończona' "$tmp/update-alias.log"
export YTMSCRAP_MOCK_CURL_FAIL=1
if HOME="$tmp/home" bash "$root/ytmscrap" --update > "$tmp/update-failed.log" 2>&1; then
  echo 'FAIL: --update returned success despite download error' >&2
  exit 1
fi
unset YTMSCRAP_MOCK_CURL_FAIL
cmp -s "$tmp/home/.local/bin/ytmscrap" "$root/ytmscrap"

echo 'PASS: Windows/macOS installer, self-update, remote helpers, PATH and failure handling'

