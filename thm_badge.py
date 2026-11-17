#!/usr/bin/env python3
"""Render a TryHackMe profile badge PNG from a username or userPublicId.

Usage:
    python3 thm_badge.py <username|userPublicId> -o assets/thm_badge.png
"""

import argparse
import base64
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

from curl_cffi import requests

WIDTH, HEIGHT = 329, 88
FALLBACK_AVATAR = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='60' height='60' viewBox='0 0 60 60'%3E"
    "%3Ccircle cx='30' cy='30' r='30' fill='%23333'/%3E%3C/svg%3E"
)

RANK_BY_HEX = {
    "0x1": "Neophyte",
    "0x2": "Apprentice",
    "0x3": "Pathfinder",
    "0x4": "Seeker",
    "0x5": "Visionary",
    "0x6": "Voyager",
    "0x7": "Adept",
    "0x8": "Hacker",
    "0x9": "Mage",
    "0xA": "Wizard",
    "0xB": "Master",
    "0xC": "Guru",
    "0xD": "Legend",
    "0xE": "Guardian",
    "0xF": "TITAN",
    "0x10": "SAGE",
    "0x11": "VANGUARD",
    "0x12": "SHOGUN",
    "0x13": "ASCENDED",
    "0x14": "MYTHIC",
    "0x15": "GRANDMASTER",
}


def rank_display(hex_level):
    return f"[{hex_level}][{RANK_BY_HEX.get(hex_level, hex_level)}]"


def fetch_badge_html(user_public_id):
    url = f"https://tryhackme.com/api/v2/badges/public-profile?userPublicId={user_public_id}"
    for attempt in range(5):
        try:
            r = requests.get(url, impersonate="chrome", timeout=30)
            if r.status_code == 429:
                print(f"rate limited, retrying in 3s ({attempt + 1}/5)")
                time.sleep(3)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"fetch failed ({attempt + 1}/5): {e}")
            time.sleep(2)
    raise RuntimeError("could not fetch badge HTML")


def extract_identity(html):
    username = (re.search(r'<span class="user_name">([^<]+)</span>', html) or [None, ""])[1].strip()
    rank_hex = (re.search(r'<span class="rank-title">\[([^\]]+)\]</span>', html) or [None, ""])[1].strip()
    if not username or not rank_hex:
        raise RuntimeError("could not parse username/level from badge HTML")
    return username, rank_hex


def fetch_profile(username):
    url = f"https://tryhackme.com/api/v2/public-profile?username={quote(username)}"
    for attempt in range(5):
        try:
            r = requests.get(url, impersonate="chrome", timeout=30)
            if r.status_code == 429:
                print(f"rate limited, retrying in 3s ({attempt + 1}/5)")
                time.sleep(3)
                continue
            r.raise_for_status()
            data = r.json().get("data") or {}
            return data
        except Exception as e:
            print(f"fetch failed ({attempt + 1}/5): {e}")
            time.sleep(2)
    raise RuntimeError("could not fetch public profile")


def avatar_data_uri(avatar_url):
    if not avatar_url:
        return FALLBACK_AVATAR
    try:
        r = requests.get(avatar_url, impersonate="chrome", timeout=20)
        r.raise_for_status()
        mime = r.headers.get("content-type", "image/png")
        return f"data:{mime};base64,{base64.b64encode(r.content).decode()}"
    except Exception as e:
        print(f"avatar download failed, using fallback: {e}")
        return FALLBACK_AVATAR


def build_html(stats, avatar_uri, total_points, rank_hex, top_percentage=None):
    rank = rank_display(rank_hex)
    pct = (
        f'<div class="details-icon-wrapper"><i class="fa-solid fa-ranking-star detail-icons pct-icon"></i>'
        f'<span class="details-text">top {top_percentage}%</span></div>'
        if isinstance(top_percentage, int) and top_percentage > 0
        else ""
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" crossorigin="anonymous" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Ubuntu:ital,wght@0,400;0,500;1,400;1,500&display=swap" rel="stylesheet" />
  <style>
    body {{ width: 329px; height: 88px; margin: 0; background: transparent; }}
    #thm-badge {{
      width: 329px; height: 88px;
      background-image: url('https://tryhackme.com/img/thm_public_badge_bg.svg');
      background-size: cover;
      display: flex; align-items: center; gap: 12px;
      user-select: none; cursor: pointer; border-radius: 12px;
    }}
    .thm-avatar-outer {{
      width: 60px; height: 60px; border-radius: 50%;
      background: linear-gradient(to bottom left, #a3ea2a, #2e4463);
      padding: 2px; margin-left: 10px;
    }}
    .thm-avatar {{
      background-image: url('{avatar_uri}');
      width: 60px; height: 60px;
      background-size: cover; background-position: center;
      border-radius: 50%; background-color: #121212;
      box-shadow: 0 0 3px 0 #303030;
    }}
    .badge-user-details {{ display: flex; flex-direction: column; gap: 8px; }}
    .details-wrapper {{ display: flex; gap: 8px; }}
    .details-icon-wrapper {{ display: flex; gap: 5px; }}
    .title-wrapper {{ display: flex; align-items: center; gap: 6px; }}
    .user_name {{
      font-family: 'Ubuntu', sans-serif; font-weight: 500; font-size: 14px;
      color: #f9f9fb; max-width: 135px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .rank-icon {{ color: #ffbb45; font-size: 10px; }}
    .rank-title {{ font-family: Ubuntu, sans-serif; font-weight: 500; font-size: 12px; color: #ffffff; }}
    .crosshair-icon {{ color: #a3ea2a; font-size: 12px; }}
    .detail-icons {{ font-weight: 900; font-size: 11px; }}
    .trophy-icon {{ color: #9ca4b4; }}
    .fire-icon {{ color: #a3ea2a; font-size: 13px; }}
    .award-icon {{ color: #d752ff; font-size: 13px; }}
    .door-closed-icon {{ color: #719cf9; font-size: 12px; }}
    .details-text {{ font-family: Ubuntu, sans-serif; font-weight: 400; font-size: 11px; color: #ffffff; }}
    .thm-link {{ font-family: Ubuntu, sans-serif; font-size: 11px; color: #f9f9fb; text-decoration: none; }}
    .pct-icon {{ color: #a3ea2a; font-size: 11px; }}
  </style>
</head>
<body>
  <div id="thm-badge">
    <div class="thm-avatar-outer"><div class="thm-avatar"></div></div>
    <div class="badge-user-details">
      <div class="title-wrapper">
        <span class="user_name">{stats['username']}</span>
        <div><i class="fa-solid fa-bolt-lightning rank-icon"></i><span class="rank-title">{rank}</span></div>
      </div>
      <div class="details-wrapper">
        <div class="details-icon-wrapper"><i class="fa-solid fa-crosshairs detail-icons crosshair-icon"></i><span class="details-text">{total_points}</span></div>
        <div class="details-icon-wrapper"><i class="fa-solid fa-fire detail-icons fire-icon"></i><span class="details-text">{stats['streak']}</span></div>
        <div class="details-icon-wrapper"><i class="fa-solid fa-award detail-icons award-icon"></i><span class="details-text">{stats['badges']}</span></div>
        <div class="details-icon-wrapper"><i class="fa-solid fa-door-closed detail-icons door-closed-icon"></i><span class="details-text">{stats['rooms']}</span></div>
      </div>
      <div class="details-wrapper">
        <div class="details-icon-wrapper"><i class="fa-solid fa-trophy detail-icons trophy-icon"></i><span class="details-text">{stats['rank']}</span></div>
        {pct}
      </div>
    </div>
  </div>
</body>
</html>"""


def find_chrome():
    for c in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
        try:
            subprocess.run([c, "--version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    raise RuntimeError("no chrome binary found")


def render(html, output):
    chrome = find_chrome()
    tmp = Path("/tmp") / f"thm_badge_{int(time.time())}.html"
    tmp.write_text(html)
    cmd = [
        chrome,
        "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
        "--default-background-color=00000000",
        f"--virtual-time-budget=15000",
        f"--window-size={WIDTH},{HEIGHT}",
        f"--screenshot={output}",
        f"file://{tmp}",
    ]
    subprocess.run(cmd, check=True)
    if not Path(output).exists():
        raise RuntimeError("screenshot was not produced")


def level_hex(level):
    if isinstance(level, int) and level > 0:
        return f"0x{level:X}"
    return "0x1"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Render a TryHackMe profile badge PNG.",
        epilog="Examples:\n"
               "  thm_badge.py 0xnhl\n"
               "  thm_badge.py 0xnhl -o assets/thm_badge.png",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("username",
                        help="TryHackMe username (or numeric userPublicId)")
    parser.add_argument("-o", "--out", default="thm_badge.png",
                        help="output path (default: thm_badge.png)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    who = args.username
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    user_public_id, username = (who, None) if who.isdigit() else (None, who)

    if username:
        print(f"looking up {username}...")
        profile = fetch_profile(username)
        username = profile.get("username") or username
        rank_hex = level_hex(profile.get("level"))
    else:
        print("fetching badge html...")
        html = fetch_badge_html(user_public_id)
        username, rank_hex = extract_identity(html)
        print("fetching live profile stats...")
        profile = fetch_profile(username)

    print(f"got {username} ([{rank_hex}])")
    stats = {
        "username": profile.get("username") or username,
        "rank_hex": rank_hex,
        "avatar_url": profile.get("avatar"),
        "rank": profile.get("rank"),
        "streak": f'{profile.get("streak", 0)} days',
        "badges": profile.get("badgesNumber"),
        "rooms": profile.get("completedRoomsNumber"),
    }
    total_points = profile.get("totalPoints")
    top_percentage = profile.get("topPercentage")
    stat_parts = [
        f"rank {stats['rank']}",
        stats["streak"],
        f"{stats['badges']} badges",
        f"{stats['rooms']} rooms",
        f"{total_points} pts",
    ]
    if top_percentage:
        stat_parts.append(f"top {top_percentage}%")
    print(", ".join(stat_parts))

    print("downloading avatar...")
    avatar_uri = avatar_data_uri(stats["avatar_url"])

    print("rendering badge...")
    render(build_html(stats, avatar_uri, total_points, stats["rank_hex"], top_percentage), output)
    print(f"saved {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
