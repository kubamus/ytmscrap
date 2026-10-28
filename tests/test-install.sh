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

cat > "$tmp/bin/brew" <<'FAKE'
#!/usr/bin/env bash
exit 0
FAKE
chmod +x "$tmp/bin/brew"
export YTMSCRAP_MOCK_UNAME=Darwin
HOME="$tmp/home" bash "$root/install.sh" > "$tmp/mac.log"
[ -x "$tmp/home/.local/bin/ytmscrap" ]
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
    cp "$YTMSCRAP_REMOTE_FIXTURE" "$1"
    exit 0
  fi
  shift
done
exit 1
FAKE
chmod +x "$tmp/bin/curl"
export YTMSCRAP_REMOTE_FIXTURE="$root/ytmscrap"
rm -f "$tmp/home/.local/bin/ytmscrap"
HOME="$tmp/home" bash "$root/install.sh" demo-user/ytmscrap > "$tmp/remote.log"
[ -x "$tmp/home/.local/bin/ytmscrap" ]
grep -Fq 'publicznego repozytorium demo-user/ytmscrap' "$tmp/remote.log"

echo 'PASS: Windows/macOS local and remote install, PATH and repeated setup' 
