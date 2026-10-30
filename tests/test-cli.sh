#!/usr/bin/env bash
# Offline smoke tests (no real YouTube downloads).
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/My Music"
expected_output_dir=$(cd "$tmp/My Music" && pwd -P)
expected_native_dir="$expected_output_dir"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) expected_native_dir=$(cygpath -m "$expected_output_dir") ;;
esac

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
grep -Fqx -- "$expected_native_dir/downloaded.txt" "$tmp/args.txt"
[[ "$output" == *'https://www.tunemymusic.com/'* ]]

[[ "$output" == *'Format: FLAC'* ]]

# WAV keeps the cover as a separate JPG.
rm -f "$tmp/args.txt"
output_wav=$(printf '%s\n%s\n%s\n%s\n' "$tmp/My Music" 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw' '1' '' | bash "$root/ytmscrap" 2>&1)
grep -Fqx -- 'wav' "$tmp/args.txt"
grep -Fqx -- '--write-thumbnail' "$tmp/args.txt"
grep -Fqx -- '--convert-thumbnails' "$tmp/args.txt"
grep -Fqx -- 'jpg' "$tmp/args.txt"
grep -Fqx -- "$expected_native_dir/downloaded-wav.txt" "$tmp/args.txt"
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

# Opt-in applies only to new downloads (yt-dlp after_move manifest).
rm -f "$tmp/args.txt"
output_rb=$(printf '%s\n%s\n%s\n%s\n' "$tmp/My Music" 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw' '2' '' | bash "$root/ytmscrap" --rekordbox 2>&1)
grep -Fqx -- '--print-to-file' "$tmp/args.txt"
grep -Fqx -- 'after_move:%(filepath)s' "$tmp/args.txt"
[[ "$output_rb" == *'Brak nowych utworów'* ]]

# The interactive prompt also enables the same mode.
rm -f "$tmp/args.txt"
printf '%s\n%s\n%s\n%s\n%s\n' "$tmp/My Music" 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw' '2' '' 't' | bash "$root/ytmscrap" > /dev/null 2>&1
grep -Fqx -- '--print-to-file' "$tmp/args.txt"

# Playlist URLs must download the whole playlist (not just one video).
rm -f "$tmp/args.txt"
printf '%s\n%s\n%s\n%s\n%s\n%s\n' "$tmp/My Music" 'https://music.youtube.com/playlist?list=PLQLDyACIOtUw' 2 '' n n | bash "$root/ytmscrap" > /dev/null 2>&1
grep -Fqx -- '--yes-playlist' "$tmp/args.txt"
if grep -Fqx -- '--no-playlist' "$tmp/args.txt"; then echo 'FAIL: playlist treated as song' >&2; exit 1; fi

# Direct song links must not expand a watch URL to the attached playlist.
assert_song() {
  local url=$1
  rm -f "$tmp/args.txt"
  output_song=$(printf '%s\n%s\n%s\n%s\n%s\n%s\n' "$tmp/My Music" "$url" 2 '' n n | bash "$root/ytmscrap" 2>&1)
  grep -Fqx -- '--no-playlist' "$tmp/args.txt"
  grep -Fqx -- '--embed-metadata' "$tmp/args.txt"
  grep -Fqx -- '--embed-thumbnail' "$tmp/args.txt"
  grep -Fqx -- "$url" "$tmp/args.txt"
  if grep -Fqx -- '--yes-playlist' "$tmp/args.txt"; then echo "FAIL: song URL expanded into a playlist: $url" >&2; exit 1; fi
  [[ "$output_song" == *'Źródło: pojedynczy utwór'* ]]
}
assert_song 'https://music.youtube.com/watch?v=BaW_jenozKc'
assert_song 'https://www.youtube.com/watch?v=BaW_jenozKc&list=PLQLDyACIOtUw'
assert_song 'https://m.youtube.com/watch?v=BaW_jenozKc&si=test'
assert_song 'https://youtu.be/BaW_jenozKc?si=test'
assert_song 'https://www.youtube.com/shorts/BaW_jenozKc'
assert_song 'https://www.youtube.com/live/BaW_jenozKc'

# Positional URL works without a link prompt.
rm -f "$tmp/args.txt"
printf '%s\n%s\n%s\n%s\n%s\n' "$tmp/My Music" 1 '' n n | bash "$root/ytmscrap" 'https://youtube.com/watch?v=BaW_jenozKc' > /dev/null 2>&1
grep -Fqx -- '--no-playlist' "$tmp/args.txt"
grep -Fqx -- 'wav' "$tmp/args.txt"

# Rekordbox option must work for direct video links too.
rm -f "$tmp/args.txt"
output_single_rb=$(printf '%s\n%s\n%s\n%s\n' "$tmp/My Music" 2 '' n | bash "$root/ytmscrap" --rekordbox 'https://music.youtube.com/watch?v=BaW_jenozKc' 2>&1)
grep -Fqx -- '--no-playlist' "$tmp/args.txt"
grep -Fqx -- '--print-to-file' "$tmp/args.txt"
[[ "$output_single_rb" == *'Brak nowych utworów'* ]]

# Reject unsupported sites, malformed video IDs and a watch URL with only list=.
for invalid in 'https://example.com/watch?v=BaW_jenozKc' 'https://music.youtube.com/watch?list=PLQLDyACIOtUw' 'https://youtu.be/short'; do
  rm -f "$tmp/args.txt"
  if printf '%s\n%s\n' "$tmp/My Music" "$invalid" | bash "$root/ytmscrap" > /dev/null 2>&1; then
    echo "FAIL: invalid URL accepted: $invalid" >&2; exit 1
  fi
  [ ! -f "$tmp/args.txt" ]
done

# Simulate native yt-dlp on Windows from either test runner. All paths passed
# to yt-dlp.exe must be Windows paths, never Git Bash /c/... paths.
mkdir -p "$tmp/mock-win"
cat > "$tmp/mock-win/uname" <<'FAKE_UNAME'
#!/usr/bin/env bash
printf '%s\n' 'MINGW64_NT-10.0'
FAKE_UNAME
cat > "$tmp/mock-win/cygpath" <<'FAKE_CYGPATH'
#!/usr/bin/env bash
case "$1" in
  -u) printf '%s\n' "$YTMSCRAP_TEST_POSIX_OUTPUT" ;;
  -m)
    if [ "$2" = "$YTMSCRAP_TEST_POSIX_OUTPUT" ]; then
      printf 'C:/Users/test/Music/DJ Songs\n'
    else
      printf 'C:/Users/test/AppData/Local/Temp/manifest.txt\n'
    fi
    ;;
  *) exit 3 ;;
esac
FAKE_CYGPATH
chmod +x "$tmp/mock-win/uname" "$tmp/mock-win/cygpath"
export YTMSCRAP_TEST_POSIX_OUTPUT="$expected_output_dir"

rm -f "$tmp/args.txt"
printf '%s\n%s\n%s\n%s\n%s\n%s\n' 'C:\\Users\\test\\Music\\DJ Songs' 'https://www.youtube.com/watch?v=BaW_jenozKc' 2 '' n n |
  PATH="$tmp/mock-win:$PATH" bash "$root/ytmscrap" > /dev/null 2>&1
grep -Fqx -- 'C:/Users/test/Music/DJ Songs' "$tmp/args.txt"
grep -Fqx -- 'C:/Users/test/Music/DJ Songs/downloaded.txt' "$tmp/args.txt"
grep -Fqx -- '--no-playlist' "$tmp/args.txt"
if grep -Fqx -- "$expected_output_dir" "$tmp/args.txt"; then
  echo 'FAIL: passed a POSIX path to Windows yt-dlp' >&2; exit 1
fi

# The manifest filename must be native as well when --rekordbox is enabled.
rm -f "$tmp/args.txt"
printf '%s\n%s\n%s\n%s\n' "$expected_output_dir" 2 '' n |
  PATH="$tmp/mock-win:$PATH" bash "$root/ytmscrap" --rekordbox 'https://www.youtube.com/watch?v=BaW_jenozKc' > /dev/null 2>&1
grep -Fqx -- 'C:/Users/test/AppData/Local/Temp/manifest.txt' "$tmp/args.txt"

# Update command should be visible in help before download starts.
help_output=$(bash "$root/ytmscrap" --help)
[[ "$help_output" == *'ytmscrap --update'* ]]
[[ "$help_output" == *'ytmscrap update'* ]]
if bash "$root/ytmscrap" --update extra > /dev/null 2>&1; then
  echo 'FAIL: accepted invalid update arguments' >&2; exit 1
fi

printf 'PASS: native Windows output paths, single songs, WAV, FLAC, Rekordbox and validation\n'
