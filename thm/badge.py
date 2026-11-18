#!/usr/bin/env python3
"""Render a TryHackMe profile badge as a self-contained SVG.

Usage:
    python3 thm/badge.py <username|userPublicId> -o assets/thm_badge.svg
"""

import argparse
import base64
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from curl_cffi import requests

try:
    from PIL import Image
except ImportError:  # only needed to shrink the avatar for SVG output
    Image = None

WIDTH, HEIGHT = 329, 88
BG_URL = "https://tryhackme.com/img/thm_public_badge_bg.svg"

# Layout, matching TryHackMe's official badge card.
TEXT_X = 86.0
TITLE_BASE = 28.65
ROW1_BASE = 50.95
ROW2_BASE = 71.8
AV_CX, AV_CY, AV_R = 42.0, 44.0, 30.0
RING_R = 32.0
BG_COVER_W = 335.63   # background-size: cover for a 328x86 image in 329x88
AVATAR_EMBED = 180    # avatar pixels embedded in the SVG (displayed at 60)

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

_ASSETS = None


def rank_display(hex_level):
    return f"[{hex_level}][{RANK_BY_HEX.get(hex_level, hex_level)}]"


def _assets():
    """Load the committed glyph tables (Ubuntu + Font Awesome outlines)."""
    global _ASSETS
    if _ASSETS is None:
        here = Path(__file__).resolve().parent
        _ASSETS = {
            "ubuntu": json.loads((here / "glyphs.json").read_text(encoding="utf-8")),
            "icons": json.loads((here / "icons.json").read_text(encoding="utf-8")),
        }
    return _ASSETS


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
            return r.json().get("data") or {}
        except Exception as e:
            print(f"fetch failed ({attempt + 1}/5): {e}")
            time.sleep(2)
    raise RuntimeError("could not fetch public profile")


def _download_avatar(avatar_url):
    if not avatar_url:
        return None, None
    try:
        r = requests.get(avatar_url, impersonate="chrome", timeout=20)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "image/png")
    except Exception as e:
        print(f"avatar download failed, using fallback: {e}")
        return None, None


def avatar_svg_data_uri(avatar_url):
    """Small still frame, inlined in the SVG (the source can be a 99-frame APNG)."""
    raw, _ = _download_avatar(avatar_url)
    if raw is None:
        return FALLBACK_AVATAR
    if Image is None:
        raise RuntimeError("Pillow is required for SVG output: pip install pillow")
    with Image.open(io.BytesIO(raw)) as im:
        im.seek(0)
        im = im.convert("RGBA").resize((AVATAR_EMBED, AVATAR_EMBED), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def fetch_background():
    """The official card artwork, inlined so the SVG needs no network."""
    try:
        r = requests.get(BG_URL, impersonate="chrome", timeout=30)
        r.raise_for_status()
        if "svg" in (r.headers.get("content-type") or ""):
            return r.content
        print("background is not an SVG, using fallback")
    except Exception as e:
        print(f"background fetch failed, using fallback: {e}")
    return None


def _esc(text):
    text = str(text)
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def _advance(text, weight, size):
    ubuntu = _assets()["ubuntu"][weight]
    glyphs = ubuntu["glyphs"]
    return sum(glyphs.get(c, glyphs["?"])["a"] for c in text) * size / ubuntu["upm"]


def _text(s, x, y, size, weight, fill):
    ubuntu = _assets()["ubuntu"][weight]
    glyphs = ubuntu["glyphs"]
    scale = size / ubuntu["upm"]
    cursor, out = 0.0, []
    for ch in s:
        glyph = glyphs.get(ch) or glyphs["?"]
        if glyph["d"]:
            out.append(f'<path transform="translate({cursor:.2f} 0)" d="{glyph["d"]}"/>')
        cursor += glyph["a"]
    if not out:
        return ""
    return (f'<g fill="{fill}" transform="translate({x:.2f} {y:.2f}) '
            f'scale({scale:.6f} {-scale:.6f})">' + "".join(out) + "</g>")


def _ellipsize(s, size, weight, limit):
    if _advance(s, weight, size) <= limit:
        return s
    while s and _advance(s + "…", weight, size) > limit:
        s = s[:-1]
    return s + "…"


def _icon_advance(name, size):
    icons = _assets()["icons"]
    return icons["glyphs"][name]["a"] * size / icons["upm"]


def _icon(name, x, baseline, size, fill):
    icons = _assets()["icons"]
    glyph = icons["glyphs"][name]
    scale = size / icons["upm"]
    return (f'<g fill="{fill}" transform="translate({x:.2f} {baseline:.2f}) '
            f'scale({scale:.6f} {-scale:.6f})"><path d="{glyph["d"]}"/></g>')


def _stat_row(items, x, baseline):
    parts = []
    for i, (name, size, color, label) in enumerate(items):
        if i:
            x += 8
        parts.append(_icon(name, x, baseline, size, color))
        x += _icon_advance(name, size) + 5
        parts.append(_text(label, x, baseline, 11, "regular", "#ffffff"))
        x += _advance(label, "regular", 11)
    return "".join(parts)


def render_svg(stats, avatar_uri, background, total_points, top_percentage=None):
    """Build the badge as a self-contained 329x88 SVG (text as outlines)."""
    name = _ellipsize(stats["username"], 14, "medium", 135)
    name_w = _advance(name, "medium", 14)
    rank_title = rank_display(stats["rank_hex"])
    rank_x = TEXT_X + name_w + 6 + _icon_advance("bolt-lightning", 10)

    row1 = _stat_row([
        ("crosshairs", 11, "#a3ea2a", str(total_points)),
        ("fire", 13, "#a3ea2a", stats["streak"]),
        ("award", 13, "#d752ff", str(stats["badges"])),
        ("door-closed", 12, "#719cf9", str(stats["rooms"])),
    ], TEXT_X, ROW1_BASE)

    row2_items = [("trophy", 11, "#9ca4b4", str(stats["rank"]))]
    if isinstance(top_percentage, int) and top_percentage > 0:
        row2_items.append(("ranking-star", 11, "#a3ea2a", f"top {top_percentage}%"))
    row2 = _stat_row(row2_items, TEXT_X, ROW2_BASE)

    if background:
        bg = ('<image href="data:image/svg+xml;base64,'
              f'{base64.b64encode(background).decode()}" x="0" y="0" '
              f'width="{BG_COVER_W}" height="{HEIGHT}" preserveAspectRatio="none"/>')
    else:
        bg = (f'<rect width="{WIDTH}" height="{HEIGHT}" rx="12" fill="#171c2b"/>'
              f'<circle cx="250" cy="90" r="130" fill="#22304a" opacity="0.55"/>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{_esc(stats['username'])} on TryHackMe: {_esc(stats['rank'])}, level {_esc(stats['rank_hex'])}, {total_points} points, {stats['rooms']} rooms">
  <title>{_esc(stats['username'])} on TryHackMe</title>
  <defs>
    <clipPath id="card"><rect width="{WIDTH}" height="{HEIGHT}" rx="12"/></clipPath>
    <clipPath id="avatar"><circle cx="{AV_CX}" cy="{AV_CY}" r="{AV_R}"/></clipPath>
    <linearGradient id="ring" x1="1" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#a3ea2a"/><stop offset="1" stop-color="#2e4463"/>
    </linearGradient>
    <filter id="avatar-shadow" x="-25%" y="-25%" width="150%" height="150%">
      <feGaussianBlur stdDeviation="1.2"/>
    </filter>
  </defs>
  <g clip-path="url(#card)">
    {bg}
  </g>
  <circle cx="{AV_CX}" cy="{AV_CY}" r="{RING_R}" fill="url(#ring)"/>
  <circle cx="{AV_CX}" cy="{AV_CY}" r="{AV_R}" fill="#303030" filter="url(#avatar-shadow)"/>
  <circle cx="{AV_CX}" cy="{AV_CY}" r="{AV_R}" fill="#121212"/>
  <image href="{avatar_uri}" x="{AV_CX - AV_R}" y="{AV_CY - AV_R}" width="{2 * AV_R}" height="{2 * AV_R}" preserveAspectRatio="xMidYMid slice" clip-path="url(#avatar)"/>
  {_text(name, TEXT_X, TITLE_BASE, 14, "medium", "#f9f9fb")}
  {_icon("bolt-lightning", TEXT_X + name_w + 6, TITLE_BASE, 10, "#ffbb45")}
  {_text(rank_title, rank_x, TITLE_BASE, 12, "medium", "#ffffff")}
  {row1}
  {row2}
</svg>
"""


def level_hex(level):
    if isinstance(level, int) and level > 0:
        return f"0x{level:X}"
    return "0x1"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Render a TryHackMe profile badge as SVG.",
        epilog="Examples:\n"
               "  thm/badge.py 0xnhl\n"
               "  thm/badge.py 0xnhl -o assets/thm_badge.svg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("username",
                        help="TryHackMe username (or numeric userPublicId)")
    parser.add_argument("-o", "--out", default="thm_badge.svg",
                        help="output SVG path (default: thm_badge.svg)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    who = args.username
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.suffix.lower() != ".svg":
        raise SystemExit(f"error: output must end in .svg (got '{output}')")

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
    avatar_uri = avatar_svg_data_uri(stats["avatar_url"])
    print("rendering badge...")
    output.write_text(
        render_svg(stats, avatar_uri, fetch_background(), total_points, top_percentage),
        encoding="utf-8",
    )
    print(f"saved {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
