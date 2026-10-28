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
while [ "$#" -gt 0 ]; do
  if [ "$1" = --output ]; then
    shift
    dest="$1"
    shift
    url=""
    for arg in "$@"; do url="$arg"; done
    case "$url" in
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
export YTMSCRAP_REMOTE_FIXTURE="$root/ytmscrap"
export YTMSCRAP_REMOTE_HELPER="$root/genre_tagger.py"
export YTMSCRAP_REMOTE_REKORDBOX="$root/rekordbox.py"
rm -f "$tmp/home/.local/bin/ytmscrap"
HOME="$tmp/home" bash "$root/install.sh" demo-user/ytmscrap > "$tmp/remote.log"
[ -x "$tmp/home/.local/bin/ytmscrap" ]
grep -Fq 'publicznego repozytorium demo-user/ytmscrap' "$tmp/remote.log"
head -n 1 "$tmp/home/.local/share/ytmscrap/genre_tagger.py" | grep -Fq '#!/usr/bin/env python3'
head -n 1 "$tmp/home/.local/share/ytmscrap/rekordbox.py" | grep -Fq '#!/usr/bin/env python3'

echo 'PASS: Windows/macOS local/remote install, Python helper, PATH and repeat setup' 
