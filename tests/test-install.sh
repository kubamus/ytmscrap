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
[ -f "$tmp/home/.local/share/ytmscrap/proxy_fallback.py" ]
[ -f "$tmp/home/.local/share/ytmscrap/dj_library.py" ]
cmp -s "$tmp/home/.local/share/ytmscrap/VERSION" "$root/VERSION"
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
dest=''
url=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = --output ]; then
    shift
    dest="$1"
  elif [[ "$1" == https://* ]]; then
    url="$1"
  fi
  shift
done
printf '%s\n' "$url" >> "$YTMSCRAP_CURL_LOG"
case "$url" in
  */VERSION*) src="$YTMSCRAP_REMOTE_VERSION" ;;
  */install.sh*) src="$YTMSCRAP_REMOTE_INSTALLER" ;;
  */genre_tagger.py*) src="$YTMSCRAP_REMOTE_HELPER" ;;
  */rekordbox.py*) src="$YTMSCRAP_REMOTE_REKORDBOX" ;;
  */proxy_fallback.py*) src="$YTMSCRAP_REMOTE_PROXY" ;;
  */dj_library.py*) src="$YTMSCRAP_REMOTE_LIBRARY" ;;
  */ytmscrap*) src="$YTMSCRAP_REMOTE_FIXTURE" ;;
  *) exit 1 ;;
esac
if [ -n "$dest" ]; then cp "$src" "$dest"; else cat "$src"; fi
FAKE
chmod +x "$tmp/bin/curl"
export YTMSCRAP_CURL_LOG="$tmp/curl-urls.log"
export YTMSCRAP_REMOTE_INSTALLER="$root/install.sh"
export YTMSCRAP_REMOTE_FIXTURE="$root/ytmscrap"
export YTMSCRAP_REMOTE_HELPER="$root/genre_tagger.py"
export YTMSCRAP_REMOTE_REKORDBOX="$root/rekordbox.py"
export YTMSCRAP_REMOTE_PROXY="$root/proxy_fallback.py"
export YTMSCRAP_REMOTE_LIBRARY="$root/dj_library.py"
export YTMSCRAP_REMOTE_VERSION="$root/VERSION"
rm -f "$tmp/home/.local/bin/ytmscrap"
HOME="$tmp/home" bash "$root/install.sh" demo-user/ytmscrap > "$tmp/remote.log"
[ -x "$tmp/home/.local/bin/ytmscrap" ]
grep -Fq 'publicznego repozytorium demo-user/ytmscrap' "$tmp/remote.log"
head -n 1 "$tmp/home/.local/share/ytmscrap/genre_tagger.py" | grep -Fq '#!/usr/bin/env python3'
head -n 1 "$tmp/home/.local/share/ytmscrap/rekordbox.py" | grep -Fq '#!/usr/bin/env python3'
head -n 1 "$tmp/home/.local/share/ytmscrap/proxy_fallback.py" | grep -Fq '#!/usr/bin/env python3'
head -n 1 "$tmp/home/.local/share/ytmscrap/dj_library.py" | grep -Fq '#!/usr/bin/env python3'
cmp -s "$tmp/home/.local/share/ytmscrap/VERSION" "$root/VERSION"
# The installer must request a fresh URL for every downloaded source.
grep -E 'ytmscrap\?refresh=[0-9]+' "$tmp/curl-urls.log"
grep -E 'genre_tagger.py\?refresh=[0-9]+' "$tmp/curl-urls.log"
grep -E 'rekordbox.py\?refresh=[0-9]+' "$tmp/curl-urls.log"
grep -E 'proxy_fallback.py\?refresh=[0-9]+' "$tmp/curl-urls.log"
grep -E 'dj_library.py\?refresh=[0-9]+' "$tmp/curl-urls.log"
grep -E 'VERSION\?refresh=[0-9]+' "$tmp/curl-urls.log"

# Self-update should invoke the official installer without touching the system,
# replace CLI as well as both Python helper files, and work on both shells.
for mock_os in Darwin MINGW64_NT-10.0; do
  export YTMSCRAP_MOCK_UNAME="$mock_os"
  printf '#!/usr/bin/env bash\nprintf "old CLI\\n"\n' > "$tmp/home/.local/bin/ytmscrap"
  printf '0.0.1\n' > "$tmp/home/.local/share/ytmscrap/VERSION"
  printf 'old helper\n' > "$tmp/home/.local/share/ytmscrap/genre_tagger.py"
  printf 'old rekordbox\n' > "$tmp/home/.local/share/ytmscrap/rekordbox.py"
  printf 'old proxy helper\n' > "$tmp/home/.local/share/ytmscrap/proxy_fallback.py"
  printf 'old dj library\n' > "$tmp/home/.local/share/ytmscrap/dj_library.py"
  HOME="$tmp/home" bash "$root/ytmscrap" --update > "$tmp/update.log"
  cmp -s "$tmp/home/.local/bin/ytmscrap" "$root/ytmscrap"
  cmp -s "$tmp/home/.local/share/ytmscrap/genre_tagger.py" "$root/genre_tagger.py"
  cmp -s "$tmp/home/.local/share/ytmscrap/rekordbox.py" "$root/rekordbox.py"
  cmp -s "$tmp/home/.local/share/ytmscrap/proxy_fallback.py" "$root/proxy_fallback.py"
  cmp -s "$tmp/home/.local/share/ytmscrap/dj_library.py" "$root/dj_library.py"
  grep -Fq 'Aktualizacja zakończona' "$tmp/update.log"
  cmp -s "$tmp/home/.local/share/ytmscrap/VERSION" "$root/VERSION"
done

# A current install must not download or run the installer again.
export YTMSCRAP_MOCK_UNAME=Darwin
before=$(grep -c '/install.sh?refresh=' "$tmp/curl-urls.log")
HOME="$tmp/home" bash "$root/ytmscrap" update > "$tmp/update-alias.log"
grep -Fq 'Aktualizacja nie jest potrzebna' "$tmp/update-alias.log"
HOME="$tmp/home" bash "$root/ytmscrap" --update > "$tmp/update-noop.log"
grep -Fq 'Aktualizacja nie jest potrzebna' "$tmp/update-noop.log"
after=$(grep -c '/install.sh?refresh=' "$tmp/curl-urls.log")
[ "$before" -eq "$after" ] || { echo 'FAIL: update fetched the installer unnecessarily' >&2; exit 1; }

export YTMSCRAP_MOCK_CURL_FAIL=1
if HOME="$tmp/home" bash "$root/ytmscrap" --update > "$tmp/update-failed.log" 2>&1; then
  echo 'FAIL: --update returned success despite download error' >&2
  exit 1
fi
unset YTMSCRAP_MOCK_CURL_FAIL
cmp -s "$tmp/home/.local/bin/ytmscrap" "$root/ytmscrap"

# The CLI displays a notice when outdated and caches checks for 24 hours.
printf '0.0.1\n' > "$tmp/home/.local/share/ytmscrap/VERSION"
rm -rf "$tmp/home/.cache/ytmscrap"
before=$(grep -c '/VERSION?refresh=' "$tmp/curl-urls.log")
notice=$(HOME="$tmp/home" bash "$root/ytmscrap" --help 2>&1)
[[ "$notice" == *'Dostępna aktualizacja'* ]] || { echo 'FAIL: no update notice' >&2; exit 1; }
notice=$(HOME="$tmp/home" bash "$root/ytmscrap" --help 2>&1)
[[ "$notice" == *'Dostępna aktualizacja'* ]]
after=$(grep -c '/VERSION?refresh=' "$tmp/curl-urls.log")
[ "$after" -eq $((before + 1)) ] || { echo 'FAIL: update check did not use cache' >&2; exit 1; }

# GitHub failures should not prevent normal commands.
rm -rf "$tmp/home/.cache/ytmscrap"
export YTMSCRAP_MOCK_CURL_FAIL=1
HOME="$tmp/home" bash "$root/ytmscrap" --help > "$tmp/offline-help.log" 2>&1
grep -Fq 'ytmscrap --update' "$tmp/offline-help.log"
unset YTMSCRAP_MOCK_CURL_FAIL
[ "$(HOME="$tmp/home" bash "$root/ytmscrap" --version)" = 'ytmscrap v0.0.1' ]

echo 'PASS: Windows/macOS installer, version checks, update notices and offline handling'
