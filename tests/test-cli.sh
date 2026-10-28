#!/usr/bin/env bash
# Offline smoke tests (no real YouTube downloads).
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/My Music"
expected_output_dir=$(cd "$tmp/My Music" && pwd -P)

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

output=$(printf '%s\n%s\n%s\n%s\n' "$tmp/My Music" 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw&si=test' '2' '' | bash "$root/ytmscrap" 2>&1)
[ -f "$tmp/args.txt" ] || { echo 'FAIL: no yt-dlp invocation' >&2; exit 1; }
grep -Fq 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw&si=test' "$tmp/args.txt"
grep -Fqx -- '--embed-thumbnail' "$tmp/args.txt"
grep -Fqx -- '--embed-metadata' "$tmp/args.txt"
grep -Fqx -- '--download-archive' "$tmp/args.txt"
grep -Fqx -- 'bestaudio' "$tmp/args.txt"
grep -Fqx -- 'flac' "$tmp/args.txt"
grep -Fqx -- '%(artist,uploader)s - %(track,title)s.%(ext)s' "$tmp/args.txt"
grep -Fqx -- "$expected_output_dir/downloaded.txt" "$tmp/args.txt"
[[ "$output" == *'https://www.tunemymusic.com/'* ]]

[[ "$output" == *'Format: FLAC'* ]]

# WAV keeps the cover as a separate JPG.
rm -f "$tmp/args.txt"
output_wav=$(printf '%s\n%s\n%s\n%s\n' "$tmp/My Music" 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw' '1' '' | bash "$root/ytmscrap" 2>&1)
grep -Fqx -- 'wav' "$tmp/args.txt"
grep -Fqx -- '--write-thumbnail' "$tmp/args.txt"
grep -Fqx -- '--convert-thumbnails' "$tmp/args.txt"
grep -Fqx -- 'jpg' "$tmp/args.txt"
grep -Fqx -- "$expected_output_dir/downloaded-wav.txt" "$tmp/args.txt"
if grep -Fqx -- '--embed-thumbnail' "$tmp/args.txt"; then
  echo 'FAIL: WAV attempted to embed artwork' >&2; exit 1
fi
[[ "$output_wav" == *'Format: WAV'* ]]
rm -f "$tmp/args.txt"
if printf '.\nhttps://example.com/playlist?list=abc\n' | bash "$root/ytmscrap" > /dev/null 2>&1; then
  echo 'FAIL: invalid URL accepted' >&2; exit 1
fi
[ ! -f "$tmp/args.txt" ] || { echo 'FAIL: yt-dlp invoked for invalid URL' >&2; exit 1; }

if printf '.\nhttps://music.youtube.com/playlist?list=abc\n2\nn\n' | bash "$root/ytmscrap" > /dev/null 2>&1; then
  :
else
  echo 'FAIL: cancel should exit 0' >&2; exit 1
fi
[ ! -f "$tmp/args.txt" ] || { echo 'FAIL: yt-dlp invoked on cancel' >&2; exit 1; }

printf 'PASS: WAV, FLAC, paths, metadata, thumbnails, archives, URL validation and cancel\n'
