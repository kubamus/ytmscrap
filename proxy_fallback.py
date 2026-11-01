#!/usr/bin/env python3
"""Find public HTTP proxies that can access a YouTube video.

Called only after a direct download hits a YouTube bot/rate-limit error.
No browser cookies, secrets or user tokens are ever sent to public proxies.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

SOURCES = (
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/http.txt",
)
IP_PORT = re.compile(r"^([0-9.]+):([0-9]{1,5})$")
CHECK_URL = "https://www.youtube.com/generate_204"
MAX_CANDIDATES = 48
MAX_YTDLP_CHECKS = 16
MAX_RESULTS = 3
SSL_CONTEXT = ssl.create_default_context()


def fetch_list(url: str) -> list[str]:
    # Ignore inherited proxy environment variables for the list download.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"User-Agent": "ytmscrap-proxy-check/1.0"})
    try:
        with opener.open(request, timeout=6) as response:
            lines = response.read(128_000).decode("utf-8", errors="replace").splitlines()
    except (OSError, urllib.error.URLError, ValueError) as exc:
        print(f"[Proxy] Lista niedostępna: {url} ({exc})", file=sys.stderr)
        return []
    result = []
    for line in lines:
        match = IP_PORT.fullmatch(line.strip())
        if not match:
            continue
        ip, port_text = match.groups()
        try:
            address = ipaddress.ip_address(ip)
            port = int(port_text)
        except ValueError:
            continue
        # Public lists are untrusted: never connect to local or private addresses.
        if address.version != 4 or not address.is_global or not 1 <= port <= 65535:
            continue
        result.append(f"http://{address}:{port}")
    return result


def candidates() -> list[str]:
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        lists = list(pool.map(fetch_list, SOURCES))
    # Alternate between the two fastest-first lists, then deduplicate.
    result = []
    seen = set()
    for pair in zip_longest(*lists):
        for proxy in pair:
            if proxy and proxy not in seen:
                result.append(proxy)
                seen.add(proxy)
                if len(result) >= MAX_CANDIDATES:
                    return result
    return result


def zip_longest(*lists: list[str]):
    from itertools import zip_longest as itertools_zip_longest
    return itertools_zip_longest(*lists)


def allows_https(proxy: str) -> bool:
    # This must tunnel TLS to YouTube with normal certificate validation.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"https": proxy}),
        urllib.request.HTTPSHandler(context=SSL_CONTEXT),
    )
    try:
        with opener.open(
            urllib.request.Request(CHECK_URL, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=5,
        ) as response:
            return response.status == 204
    except (OSError, urllib.error.URLError, ValueError):
        return False


def can_extract_video(proxy: str, video_url: str) -> bool:
    command = [
        "yt-dlp", "--ignore-config", "--no-playlist", "--simulate",
        "--no-warnings", "--no-progress", "--remote-components", "ejs:github",
        "--retries", "0", "--extractor-retries", "0", "--socket-timeout", "6",
        "--proxy", proxy, "-f", "bestaudio", video_url,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    output = (result.stdout + result.stderr).lower()
    return result.returncode == 0 and "sign in to confirm" not in output


def find_working(video_url: str) -> list[str]:
    pool = candidates()
    if not pool:
        print("[Proxy] Nie udało się pobrać listy proxy.", file=sys.stderr)
        return []
    print(f"[Proxy] Test HTTPS: {len(pool)} adresów (12 równolegle)...", file=sys.stderr)
    responsive = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(allows_https, proxy): proxy for proxy in pool}
        for future in as_completed(futures):
            if future.result():
                responsive.append(futures[future])
    if not responsive:
        print("[Proxy] Żaden serwer nie zapewnił połączenia HTTPS z YouTube.", file=sys.stderr)
        return []
    # Keep source order (the upstream lists rank fast proxies first).
    rank = {proxy: index for index, proxy in enumerate(pool)}
    responsive.sort(key=lambda proxy: rank[proxy])
    check = responsive[:MAX_YTDLP_CHECKS]
    print(f"[Proxy] Test yt-dlp: {len(check)} adresów (6 równolegle)...", file=sys.stderr)
    valid = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(can_extract_video, proxy, video_url): proxy for proxy in check}
        for future in as_completed(futures):
            if future.result():
                valid.append(futures[future])
    valid.sort(key=lambda proxy: rank[proxy])
    if not valid:
        print("[Proxy] Żaden z testowanych serwerów nie przeszedł testu yt-dlp.", file=sys.stderr)
    return valid[:MAX_RESULTS]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_url", help="URL pojedynczego filmu YouTube do szybkiego testu")
    args = parser.parse_args()
    if not re.fullmatch(
        r"https://(?:www\.|m\.|music\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]{11}",
        args.video_url,
    ):
        parser.error("Wymagany jest zwykły adres filmu YouTube z ID (bez playlisty)")
    for proxy in find_working(args.video_url):
        print(proxy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
