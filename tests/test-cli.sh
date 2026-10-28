#!/usr/bin/env bash
# Offline smoke tests (no real YouTube downloads).
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/My Music"

cat > "$tmp/bin/yt-dlp" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$YTMSCRAP_ARG_LOG"
FAKE
cat > "$tmp/bin/ffmpeg" <<'FAKE'
#!/usr/bin/env bash
exit 0
FAKE
cat > "$tmp/bin/deno" <<'FAKE'
#!/usr/bin/env bash
exit 0
FAKE
chmod +x "$tmp/bin/yt-dlp" "$tmp/bin/ffmpeg" "$tmp/bin/deno"
export PATH="$tmp/bin:$PATH"
export YTMSCRAP_ARG_LOG="$tmp/args.txt"

output=$(printf '%s\n%s\n%s\n' "$tmp/My Music" 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw&si=test' '' | bash "$root/ytmscrap" 2>&1)
[ -f "$tmp/args.txt" ] || { echo 'FAIL: no yt-dlp invocation' >&2; exit 1; }
grep -Fq 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw&si=test' "$tmp/args.txt"
grep -Fqx -- '--embed-thumbnail' "$tmp/args.txt"
grep -Fqx -- '--embed-metadata' "$tmp/args.txt"
grep -Fqx -- '--download-archive' "$tmp/args.txt"
grep -Fqx -- 'bestaudio' "$tmp/args.txt"
grep -Fqx -- 'flac' "$tmp/args.txt"
grep -Fqx -- '%(artist,uploader)s - %(track,title)s.%(ext)s' "$tmp/args.txt"
grep -Fqx -- "$tmp/My Music/downloaded.txt" "$tmp/args.txt"
[[ "$output" == *'https://www.tunemymusic.com/'* ]]

rm -f "$tmp/args.txt"
if printf '.\nhttps://example.com/playlist?list=abc\n' | bash "$root/ytmscrap" > /dev/null 2>&1; then
  echo 'FAIL: invalid URL accepted' >&2; exit 1
fi
[ ! -f "$tmp/args.txt" ] || { echo 'FAIL: yt-dlp invoked for invalid URL' >&2; exit 1; }

if printf '.\nhttps://music.youtube.com/playlist?list=abc\nn\n' | bash "$root/ytmscrap" > /dev/null 2>&1; then
  :
else
  echo 'FAIL: cancel should exit 0' >&2; exit 1
fi
[ ! -f "$tmp/args.txt" ] || { echo 'FAIL: yt-dlp invoked on cancel' >&2; exit 1; }

printf 'PASS: prompt, paths, tags, URL validation and cancel\n'
