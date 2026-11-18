#!/usr/bin/env python3
"""htb_badge.py — render a minimal Hack The Box profile badge as SVG.

Reads only public endpoints (no API token), writes a self-contained 329x88 SVG
that matches the dimensions of the TryHackMe badge.

    python3 htb_badge.py 1965095 -o assets/htb_badge.svg
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API = "https://labs.hackthebox.com"
UA = "htb-badge/1.0"

W, H = 329, 88
PAD_X, AVATAR = 8, 54
TEXT_X = PAD_X + AVATAR + 10

FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")
CHAR_W = 0.6  # monospace advance width, in em

# Official Hack The Box cube, extracted from the nav logo SVG on hackthebox.com.
CUBE_PATH = (
    "M25.6309 22.3007C25.6309 22.5049 25.4942 22.7083 25.3575 22.7755L16.5409 27.7951C16.2675 "
    "27.9308 15.9257 27.8623 15.789 27.5917C15.7207 27.5232 15.7207 27.3875 15.7207 27.3197V17.2824"
    "C15.7207 17.079 15.8574 16.8748 15.9941 16.807L24.8107 11.7202C25.0841 11.5845 25.4258 11.6524"
    " 25.5625 11.9237C25.6309 11.9915 25.6309 12.1271 25.6309 12.1956V22.3007ZM12.6426 27.3885C12.6426"
    " 27.7276 12.3692 27.9318 12.0958 27.9318C12.0275 27.9318 11.8908 27.9318 11.8224 27.8633L3.00581"
    " 22.845C2.80077 22.7765 2.73242 22.573 2.73242 22.3702V12.1966C2.73242 11.8575 3.00581 11.6533"
    " 3.27919 11.6533C3.34754 11.6533 3.48423 11.6533 3.55257 11.7212L12.3692 16.7408C12.5742 16.808"
    " 12.6426 17.0114 12.6426 17.2149V27.3885ZM5.05854 8.1265L13.8752 3.03971C14.0802 2.97121"
    " 14.2852 2.97121 14.4219 3.03971L23.2386 8.1265C23.512 8.26147 23.5803 8.60059 23.4436 8.87189"
    "L23.2386 9.07536L14.4219 14.1622C14.2169 14.2307 14.0119 14.2307 13.8752 14.1622L5.05854 9.07536"
    "C4.78516 8.93971 4.71681 8.60059 4.8535 8.3293L5.05854 8.1265ZM28.3636 8.66846C28.3636 8.32934"
    " 28.2269 7.99022 28.0219 7.78743H27.9535L27.8852 7.71893L27.8168 7.6511H27.7485L14.7627 0.190472"
    "L14.6944 0.122648C14.3527 -0.0808236 13.8742 -0.0123214 13.5325 0.190472L0.546768 7.58328H0.478422"
    "L0.410076 7.6511L0.34173 7.71893L0.273384 7.78743C0.068346 7.99022 0 8.26152 0 8.60064V8.66846"
    "V23.5226C0 23.9288 0.273384 24.3358 0.615114 24.5399L13.6009 31.9321C13.6009 31.9321 13.6692"
    " 31.9321 13.6692 32.0006H13.7375H13.8059H13.8742H13.9426H14.0109H14.2843H14.3527H14.421H14.4894"
    "H14.5577H14.626C14.626 32.0006 14.6944 32.0006 14.6944 31.9321L27.6801 24.5399C28.0902 24.3358"
    " 28.2952 23.9288 28.2952 23.5226L28.3636 8.66846Z"
)
CUBE_W, CUBE_H = 28.3636, 32.0
CUBE_SCALE = 0.95


class BadgeError(Exception):
    """Anything the user can act on: bad id, private profile, network failure."""


@dataclass(frozen=True)
class Theme:
    bg: str
    border: str
    text: str
    dim: str
    accent: str
    sep: str


THEMES = {
    "dark": Theme(bg="#171b22", border="#2b313b", text="#e6edf3",
                  dim="#8b949e", accent="#9fef00", sep="#3a414d"),
    "light": Theme(bg="#ffffff", border="#d0d7de", text="#1f2328",
                   dim="#59636e", accent="#4a7d00", sep="#afb8c1"),
}


@dataclass
class Stats:
    profile_id: int
    name: str
    rank: str
    level: int
    level_title: str
    xp_total: int
    xp_level: int
    xp_needed: int
    machines_owned: int
    machines_total: int
    challenges_owned: int
    challenges_total: int
    respect: int
    avatar_url: str
    avatar_b64: str | None = field(default=None, repr=False)


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise BadgeError(f"no such profile or endpoint (404): {url}") from exc
        if exc.code in (401, 403):
            raise BadgeError(
                "profile is private or requires auth — enable a public profile "
                "in HTB settings (Profile -> Settings -> Privacy)") from exc
        raise BadgeError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise BadgeError(f"network error for {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise BadgeError(f"expected JSON from {url}") from exc


def parse_profile_id(raw: str) -> int:
    """Accept the numeric profile id only."""
    text = raw.strip()
    if text.isdigit():
        return int(text)
    raise BadgeError(
        f"'{raw}' is not a profile id. Pass the number from your profile URL "
        "(app.hackthebox.com/users/<id>) — HTB has no public username lookup."
    )


def fetch_stats(profile_id: int) -> Stats:
    profile = _get_json(f"{API}/api/v4/profile/{profile_id}").get("profile")
    if not profile:
        raise BadgeError(f"profile {profile_id} returned no data")

    account_id = profile.get("account_id")
    if not account_id:
        raise BadgeError("profile has no account_id; cannot read experience level")

    xp = _get_json(f"{API}/api/experience/v1/account/{account_id}")
    machines = _get_json(
        f"{API}/api/v4/profile/progress/machines/{profile_id}").get("profile", {})
    challenges = _get_json(
        f"{API}/api/v4/profile/progress/challenges/{profile_id}").get("profile", {})

    avatar_url = profile.get("avatar") or ""
    return Stats(
        profile_id=profile_id,
        name=profile.get("name") or f"user-{profile_id}",
        rank=profile.get("rank") or "Noob",
        level=int(xp.get("level") or 0),
        level_title=xp.get("levelTitle") or "",
        xp_total=int(xp.get("totalExperiencePoints") or 0),
        xp_level=int(xp.get("levelExperiencePoints") or 0),
        xp_needed=int(xp.get("experienceUntilNextLevel") or 0),
        machines_owned=int(machines.get("machine_owns", {}).get("solved") or 0),
        machines_total=int(machines.get("machine_owns", {}).get("total") or 0),
        challenges_owned=int(challenges.get("challenge_owns", {}).get("solved") or 0),
        challenges_total=int(challenges.get("challenge_owns", {}).get("total") or 0),
        respect=int(profile.get("respects") or 0),
        avatar_url=avatar_url,
        avatar_b64=_embed_avatar(avatar_url),
    )


def _embed_avatar(url: str) -> str | None:
    if not url:
        return None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=20) as response:
            mime = (response.headers.get("Content-Type") or "image/png").split(";")[0]
            return f"data:{mime};base64,{base64.b64encode(response.read()).decode()}"
    except (urllib.error.URLError, OSError):
        return None  # fall back to linking the remote avatar


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def _advance(text: str, size: float, tracking: float = 0.0) -> float:
    """Monospace advance of `text` at `size` px, plus optional letter-spacing."""
    return len(text) * (size * CHAR_W + tracking)


def _num(value: int) -> str:
    return f"{value:,}"


def _compact(value: int) -> str:
    if value < 10_000:
        return f"{value:,}"
    if value < 1_000_000:
        return f"{value / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"


Span = tuple[str, float, str, str]


def _layout(parts: list[Span], x: float, gap: float = 4.0) -> tuple[str, float]:
    """Render text spans left-to-right with monospace advances; return width."""
    cursor, out = float(x), []
    for index, (text, size, weight, color) in enumerate(parts):
        if index:
            cursor += gap
        out.append(
            f'<tspan x="{cursor:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}">{_esc(text)}</tspan>'
        )
        cursor += _advance(text, size)
    return "".join(out), cursor - x


def render_svg(stats: Stats, theme: Theme) -> str:
    name = _esc(stats.name)
    rank = _esc(stats.rank.upper())

    cube_x = W - 14 - CUBE_W * CUBE_SCALE
    cube_y = (H - CUBE_H * CUBE_SCALE) / 2
    text_limit = cube_x - 10

    name_size, rank_size = 16.0, 9.5
    name_x, name_y, rank_y = TEXT_X, 33.0, 32.4
    # Shrink unusually long names instead of letting them run under the cube.
    name_w = _advance(name, name_size)
    max_name_w = text_limit - name_x - 4
    if name_w > max_name_w:
        name_size = max(10.0, name_size * max_name_w / name_w)
        name_w = _advance(name, name_size)
    rank_x = name_x + name_w + 9
    # Drop the rank label rather than let it run into the cube mark.
    show_rank = rank_x + _advance(rank, rank_size, tracking=0.4) <= text_limit

    # Stat line: LVL n . X XP . N pwned — drop trailing segments until it fits.
    accent, text_c, dim, sep = theme.accent, theme.text, theme.dim, theme.sep
    xp_full, xp_short = f"{_num(stats.xp_total)} XP", f"{_compact(stats.xp_total)} XP"
    candidates = [
        [(f"LVL {stats.level}", 13.5, "700", accent),
         ("·", 13.5, "700", sep),
         (xp_full, 12.5, "500", text_c),
         ("·", 13.5, "700", sep),
         (f"{stats.machines_owned} pwned", 12.5, "500", dim)],
        [(f"LVL {stats.level}", 13.5, "700", accent),
         ("·", 13.5, "700", sep),
         (xp_full, 12.5, "500", text_c)],
        [(f"LVL {stats.level}", 13.5, "700", accent),
         ("·", 13.5, "700", sep),
         (xp_short, 12.5, "500", text_c)],
        [(f"LVL {stats.level}", 13.5, "700", accent)],
    ]
    for parts in candidates:
        stat_line, line_w = _layout(parts, TEXT_X, gap=5.0)
        if TEXT_X + line_w <= text_limit:
            break

    avatar_x, avatar_y = PAD_X, (H - AVATAR) / 2
    avatar_src = stats.avatar_b64 or _esc(stats.avatar_url)
    avatar = (
        f'<image href="{avatar_src}" x="{avatar_x}" y="{avatar_y}" '
        f'width="{AVATAR}" height="{AVATAR}" preserveAspectRatio="xMidYMid slice" '
        f'clip-path="url(#avatarClip)"/>'
    ) if avatar_src else ""

    rank_label = (
        f'\n  <text x="{rank_x:.1f}" y="{rank_y}" font-family="{FONT}" '
        f'font-size="{rank_size}" font-weight="600" letter-spacing="0.4" '
        f'fill="{theme.dim}">{rank}</text>'
    ) if show_rank else ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{name}: {stats.rank}, level {stats.level}, {_num(stats.xp_total)} XP, {stats.machines_owned} machines owned">
  <title>{name} on Hack The Box</title>
  <defs>
    <clipPath id="avatarClip">
      <rect x="{avatar_x}" y="{avatar_y}" width="{AVATAR}" height="{AVATAR}" rx="8"/>
    </clipPath>
  </defs>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="8" fill="{theme.bg}" stroke="{theme.border}"/>
  {avatar}
  <rect x="{avatar_x + 0.5}" y="{avatar_y + 0.5}" width="{AVATAR - 1}" height="{AVATAR - 1}" rx="8" fill="none" stroke="{theme.sep}"/>
  <text x="{name_x}" y="{name_y}" font-family="{FONT}" font-size="{name_size}" font-weight="700" fill="{theme.text}">{name}</text>{rank_label}
  <text y="53.5" font-family="{FONT}">{stat_line}</text>
  <text x="{name_x}" y="73" font-family="{FONT}" font-size="9.5" font-weight="700" letter-spacing="0.3" fill="{theme.accent}">hackthebox.com</text>
  <g transform="translate({cube_x:.1f} {cube_y:.1f}) scale({CUBE_SCALE})">
    <path fill-rule="evenodd" clip-rule="evenodd" fill="{theme.accent}" d="{CUBE_PATH}"/>
  </g>
</svg>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a minimal Hack The Box profile badge as SVG.",
        epilog="Examples:\n"
               "  htb_badge.py 1965095\n"
               "  htb_badge.py 1965095 -o assets/htb_badge.svg --theme light",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("profile", help="numeric Hack The Box profile id")
    parser.add_argument("-o", "--out", default="htb_badge.svg",
                        help="output path (default: htb_badge.svg)")
    parser.add_argument("--theme", choices=sorted(THEMES), default="dark",
                        help="colour theme (default: dark)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile_id = parse_profile_id(args.profile)
        stats = fetch_stats(profile_id)
    except BadgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    svg = render_svg(stats, THEMES[args.theme])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({len(svg):,} bytes) — {stats.name}, level {stats.level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
