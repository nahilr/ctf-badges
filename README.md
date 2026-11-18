# Security Profile Badges

One GitHub Action that renders **both** badges from public profile data and
commits them to your repo — plus the two standalone scripts if you'd rather run
them yourself.

| Provider | Script | Output | Stats |
|---|---|---|---|
| TryHackMe | `thm/badge.py` | `329x88` SVG | Level, rooms, badges, streak, global rank, points, top % |
| Hack The Box | `htb/badge.py` | `329x88` SVG | Level, XP, pwned, ranking, points, respect |

Everything is read from public endpoints. No API key, no login, no secrets.

```
.
├── action.yml                # composite action: renders both badges (root-only)
├── requirements.txt          # curl_cffi + pillow
├── thm/
│   ├── badge.py              # TryHackMe → SVG
│   ├── find_user_id.py       # optional numeric TryHackMe ID lookup
│   ├── glyphs.json           # Ubuntu text outlines
│   └── icons.json            # Font Awesome icon outlines
├── htb/
│   └── badge.py              # Hack The Box → SVG
└── examples/
    └── profile-badges.yml    # sample workflow (copy to .github/workflows)
```

## Setup

Star this repo and give me a follow :)

1. **Create a `.github/workflows` directory** in your username repo — the one named `<your-username>/<your-username>`, where your README is located.

2. **Create a file** named `profile-badges.yml` inside of that folder.

3. **Place the following code** inside of it:

```yaml
name: Profile Badges

on:
  schedule:
    - cron: '0 0 * * *'   # run every 24 hours
  workflow_dispatch:       # or run it manually from the Actions tab

permissions:
  contents: write

jobs:
  update-badges:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: nahilr/ctf-badges@main
        with:
          thm_username: "<YOUR_THM_USERNAME>"
          htb_profile_id: "<YOUR_HTB_PROFILE_ID>"
```

> GitHub Actions runs from your repo, so you get `GITHUB_TOKEN` automatically — no secrets needed.

Your **TryHackMe username** is all THM needs. **Hack The Box is id-only**: use
the number from your profile URL, `app.hackthebox.com/users/1965095` →
`htb_profile_id: "1965095"`. HTB's public API rejects usernames, so there's
nothing to look up. Your HTB profile also has to be public (Profile → Settings →
Privacy).

4. **Add both badges** to your README:

```markdown
![tryhackme stats](https://raw.githubusercontent.com/<SET_USERNAME_HERE>/<SET_USERNAME_HERE>/main/assets/thm_badge.svg)
![hackthebox stats](https://raw.githubusercontent.com/<SET_USERNAME_HERE>/<SET_USERNAME_HERE>/main/assets/htb_badge.svg)
```

Want them to link to your profiles when clicked? Use this HTML instead (replace
`<SET_USERNAME_HERE>` with your GitHub username, `<SET_THM_USERNAME>` with your
TryHackMe username, and `<SET_HTB_PROFILE_ID>` with the numeric id):

```html
<a href="https://tryhackme.com/p/<SET_THM_USERNAME>" target="_blank">
  <img src="https://raw.githubusercontent.com/<SET_USERNAME_HERE>/<SET_USERNAME_HERE>/main/assets/thm_badge.svg" alt="tryhackme stats">
</a>
<a href="https://app.hackthebox.com/users/<SET_HTB_PROFILE_ID>" target="_blank">
  <img src="https://raw.githubusercontent.com/<SET_USERNAME_HERE>/<SET_USERNAME_HERE>/main/assets/htb_badge.svg" alt="hackthebox stats">
</a>
```

5. **Run the action** — go to your repo's **Actions** tab → **Profile Badges** → **Run workflow**. After the first run, both badges show in your README and refresh every 24 hours.

## Inputs

| Name | Description | Default |
|---|---|---|
| `thm_username` | TryHackMe username | required |
| `htb_profile_id` | Hack The Box numeric profile id | required |
| `thm_image_path` | Where the TryHackMe SVG is saved | `assets/thm_badge.svg` |
| `htb_image_path` | Where the Hack The Box SVG is saved | `assets/htb_badge.svg` |
| `committer_username` | Git username for the commit | `github-actions[bot]` |
| `committer_email` | Git email for the commit | `41898282+github-actions[bot]@users.noreply.github.com` |
| `commit_message` | Commit message | `chore: update profile badges` |

```yaml
- uses: nahilr/ctf-badges@main
  with:
    thm_username: '<YOUR_THM_USERNAME>'
    htb_profile_id: '<YOUR_HTB_PROFILE_ID>'
    thm_image_path: 'assets/custom_thm_badge.svg'
    htb_image_path: 'assets/custom_htb_badge.svg'
    committer_username: 'github-actions[bot]'
    committer_email: '41898282+github-actions[bot]@users.noreply.github.com'
    commit_message: 'chore: update profile badges'
```

If you change an image path, use the same path in the image URL in your README.

## How it works

Each run renders both badges and commits them together. The commit step uses
`git diff` to check whether either image actually changed; if neither did, it
skips the commit so your history stays clean.

### TryHackMe badge

The action renders a `329x88` SVG that mirrors TryHackMe's official design. Stats
come from the public profile JSON:

- **Profile JSON** — `https://tryhackme.com/api/v2/public-profile?username=<you>` returns your stats as JSON: rank, rooms, badges, points, level, top percentage, avatar, and league tier. This is the only endpoint the action calls.
- **Badge HTML** — `https://tryhackme.com/api/v2/badges/public-profile?userPublicId=<ID>` returns the HTML for the badge shown on your TryHackMe profile. Only used when rendering from a numeric ID locally, to map it back to a username.

Both sit behind Vercel's anti-bot challenge, which serves a JavaScript checkpoint
page to any non-browser TLS fingerprint — plain `requests` or `urllib` get
blocked instantly. Every fetch therefore goes through a `curl_cffi` helper that
reproduces a real Chrome TLS handshake, which the checkpoint accepts.

Here's what happens on each run:

1. **Fetch the live profile JSON** and take every displayed stat from it: rank, streak, badges, rooms, total points, top percentage, and avatar. The badge API's counters lag (its room count can trail the profile by several rooms). Your rank title (e.g. `0xA`) is looked up from a hex-to-name map, since the profile API doesn't return a readable rank name.
2. **Draw the card in SVG.** The official background artwork is fetched once and inlined; the avatar is reduced to one 180×180 frame and embedded as a base64 PNG. Text is rendered as vector outlines (Ubuntu), and the seven icons are Font Awesome outlines, so the badge needs no fonts or network when displayed.
3. **Write the SVG.** No browser, no screenshot: the file is pure markup, sharp at any DPI and ~150 KB (mostly the two inlined images).

On top of what TryHackMe's own badge shows (level, rooms, badges, streak, global
rank), this badge adds **total points** and your **top-percentage bracket** (e.g.
`top 2%`) — both live only in the profile JSON and never appear on THM's own
badge image. The bracket comes from the `topPercentage` field and is left out
automatically if the API doesn't return one.

### Hack The Box badge

A dependency-free Python generator that renders a minimal **329×88** SVG — the
same canvas as the TryHackMe badge, so the two line up exactly when stacked in a
README. It runs on the standard library alone, so the action needs nothing extra
for it.

HTB already serves a badge at `hackthebox.com/badge/image/<id>`. It is 220×50,
auto-updating, and shows the global ranking (once you have one) plus **points**
and **respect** — the `0`s it renders early on are those two, not machine owns.
It ignores level, XP, and machines owned.

This generator keeps the name / rank / avatar / branding and shows the same
points and respect on the footer, with the global ranking beside the rank title —
in the TryHackMe badge's dimensions:

```
0xnhl  NOOB  #45548
LVL 9 · 1,980 XP · 0 pwned
hackthebox.com   ✛ 120  ★ 32
```

Data comes from these public endpoints under `https://labs.hackthebox.com`:

| Badge element | Endpoint |
|---|---|
| Name, rank, ranking, points, respect, avatar, `account_id` | `/api/v4/profile/{id}` |
| Level, total XP | `/api/experience/v1/account/{account_id}` |
| Machines owned | `/api/v4/profile/progress/machines/{id}` |
| Challenges owned | `/api/v4/profile/progress/challenges/{id}` |

The experience endpoint takes the UUID `account_id` rather than the numeric
profile id — the script chains that lookup for you.

## Numeric TryHackMe IDs (optional)

The action never needs a TryHackMe ID — usernames are enough. The numeric
`userPublicId` only matters for TryHackMe's own embed badge, which is keyed on
it, and for rendering locally from an ID. `thm/find_user_id.py` recovers it.

TryHackMe's public API is username-only and the ID is no longer shown in its
UI, but IDs are assigned incrementally at signup. The script binary-searches the
ID space: probe an ID, read that account's join date from the public profile
API, compare it with your username's join date, halve the range. A couple of
minutes on a cold run.

```bash
pip install curl_cffi
python3 thm/find_user_id.py <your_tryhackme_username>                 # range 1 … 8600000
python3 thm/find_user_id.py <your_tryhackme_username> 100000 4000000  # custom range
```

It prints the ID and the command to render a badge with it. With the ID you can
also embed TryHackMe's official badge without rendering anything:

```html
<script src="https://tryhackme.com/badge/<userPublicId>"></script>
<iframe src="https://tryhackme.com/api/v2/badges/public-profile?userPublicId=<userPublicId>"></iframe>
```

---

## Running locally

```bash
git clone https://github.com/nahilr/ctf-badges.git
cd ctf-badges

# TryHackMe — needs curl_cffi + pillow
pip install curl_cffi pillow
python3 thm/badge.py <your_thm_username> -o assets/thm_badge.svg

# Hack The Box — standard library only
python3 htb/badge.py <your_htb_profile_id> -o assets/htb_badge.svg

# Optional: numeric TryHackMe ID (same curl_cffi install)
python3 thm/find_user_id.py <your_thm_username>
```

The TryHackMe renderer needs `curl_cffi` and `Pillow`. No browser is involved.
The HTB generator has no dependencies beyond Python 3.9+.

### Script options

Both scripts take the profile as the first argument and `-o` / `--out` for the
output path:

| Script | First argument | Default output | Extra |
|---|---|---|---|
| `thm/badge.py` | TryHackMe username (or numeric ID) | `thm_badge.svg` | — |
| `htb/badge.py` | Hack The Box numeric profile id | `htb_badge.svg` | `--theme dark\|light` |

## Project Background

The TryHackMe action is inspired by and intended as a successor to
[`p4p1/tryhackme-badge-workflow`](https://github.com/p4p1/tryhackme-badge-workflow).
It keeps the same core idea: automatically update a TryHackMe badge in your
GitHub profile README.

The original action was archived on 2026-04-19. Its dynamic mode used the
TryHackMe badge API, which now blocks plain HTTP clients with an anti-bot
challenge. Its static mode depended on
`https://tryhackme-badges.s3.amazonaws.com/<username>.png`, a bucket that has
been frozen since 2024.

This version uses `curl_cffi` to fetch the current badge HTML and profile data
with a Chrome-like TLS handshake, then renders the badge as SVG from committed
glyph outlines. In addition to the official badge stats, it adds total points
from the public profile API.

The Hack The Box generator was added alongside it and takes the same approach:
no browser, just a handful of public JSON endpoints rendered into SVG. One
action now updates both.

## Credits

- TryHackMe background artwork and marks belong to TryHackMe; this project is unofficial.
- Text outlines in `thm/glyphs.json` are derived from the **Ubuntu** font (Ubuntu Font Licence).
- Icon outlines in `thm/icons.json` are from **Font Awesome Free 6.5.0** (icons CC BY 4.0, fonts SIL OFL 1.1).

## AI Disclosure

This project was created with assistance from AI tools. The code and documentation were reviewed and tested by the maintainer.

## License

MIT
