# TryHackMe Profile Badge Workflow

A lightweight GitHub Action that renders a live TryHackMe profile badge from your username (or `userPublicId`) and commits the PNG to your repo — so your README always shows your current stats.

## What the badge looks like

![TryHackMe](https://raw.githubusercontent.com/nahilr/nahilr/main/assets/thm_badge.png)

## Setup

Star this repo and give me a follow :)

1. **Create a `.github/workflows` directory** in your username repo — the one named `<your-username>/<your-username>`, where your README is located.

2. **Create a file** named `tryhackme-badge.yml` inside of that folder.

3. **Place the following code** inside of the previously created file:

```yaml
name: TryHackMe Update Badge

on:
  schedule:
    - cron: '0 0 * * *'   # run every 24 hours
  workflow_dispatch:       # or run it manually from the Actions tab

permissions:
  contents: write

jobs:
  tryhackme-badge-update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: nahilr/tryhackme-profile-badge-workflow@main
        with:
          # Replace with your TryHackMe username
          username: "<YOUR_THM_USERNAME>"
```

> GitHub Actions runs from your repo, so you get `GITHUB_TOKEN` automatically — no secrets needed.

4. **Prefer a numeric ID?** `user_public_id` works too — the action accepts either input, and the ID is no longer shown in the TryHackMe UI. You can find it with `find_user_id.py`:

```bash
pip install curl_cffi
curl -O https://raw.githubusercontent.com/nahilr/tryhackme-profile-badge-workflow/main/find_user_id.py
python3 find_user_id.py <your_tryhackme_username>
```

Put the number it prints in place of `username` above, as `user_public_id: "<ID>"`.

5. **Add the following markdown** in your README and add your username:

```markdown
![tryhackme stats](https://raw.githubusercontent.com/<SET_USERNAME_HERE>/<SET_USERNAME_HERE>/main/assets/thm_badge.png)
```

Want the badge to link to your TryHackMe profile when clicked? Use this HTML instead (replace `<SET_USERNAME_HERE>` with your GitHub username and `<SET_THM_USERNAME>` with your TryHackMe username):

```html
<a href="https://tryhackme.com/p/<SET_THM_USERNAME>" target="_blank">
  <img src="https://raw.githubusercontent.com/<SET_USERNAME_HERE>/<SET_USERNAME_HERE>/main/assets/thm_badge.png" alt="tryhackme stats">
</a>
```

6. **Run the action** — go to your repo's **Actions** tab → **TryHackMe Update Badge** → **Run workflow**. After the first run, the badge shows in your README and auto-updates every 24 hours.

## Inputs

| Name | Description | Default |
|---|---|---|
| `username` | TryHackMe username (one of `username` / `user_public_id` is required) | — |
| `user_public_id` | TryHackMe user public ID (alternative to `username`) | — |
| `image_path` | Where the badge PNG is saved | `assets/thm_badge.png` |
| `committer_username` | Git username for the commit | `github-actions[bot]` |
| `committer_email` | Git email for the commit | `41898282+github-actions[bot]@users.noreply.github.com` |
| `commit_message` | Commit message | `chore: update tryhackme badge` |

Set these options under the action's `with:` block. Provide either `username` or `user_public_id`; the other values can be left out to use their defaults.

```yaml
- uses: nahilr/tryhackme-profile-badge-workflow@main
  with:
    username: '<YOUR_THM_USERNAME>'
    # user_public_id: '<YOUR_PUBLIC_ID>'   # alternative to username
    image_path: 'assets/custom_thm_badge.png'
    committer_username: 'github-actions[bot]'
    committer_email: '41898282+github-actions[bot]@users.noreply.github.com'
    commit_message: 'chore: update TryHackMe badge'
```

For example, if you change `image_path`, use the same path in the image URL in your README.

## How it works

The action renders a `329x88` PNG badge that mirrors TryHackMe's official design, then commits it to your repo on every run. It can use two public TryHackMe endpoints:

- **Profile JSON** — `https://tryhackme.com/api/v2/public-profile?username=<you>` returns your stats as JSON: rank, rooms, badges, points, level, top percentage, avatar, and league tier.
- **Badge HTML** — `https://tryhackme.com/api/v2/badges/public-profile?userPublicId=<ID>` returns the HTML for the badge shown on your TryHackMe profile. Only needed when you supply `user_public_id`, to map the ID back to a username.

Both endpoints sit behind Vercel's anti-bot challenge, which serves a JavaScript checkpoint page to any non-browser TLS fingerprint — plain `requests` or `urllib` get blocked instantly. Every fetch therefore goes through a `curl_cffi` helper that reproduces a real Chrome TLS handshake, which the checkpoint accepts.

Here's what happens on each run:

1. **Resolve your username.** With `username` this step is skipped entirely. With `user_public_id`, the badge HTML is fetched only to read the username and level; it is no longer trusted for stat values.
2. **Fetch the live profile JSON** and take every displayed stat from it: rank, streak, badges, rooms, total points, top percentage, and avatar. The badge API's own counters lag (its room count can trail the profile by several rooms). Your rank title (e.g. `0xA`) is looked up from a hex-to-name map, since the profile API doesn't return a readable rank name.
3. **Embed your avatar as a base64 data URI.** The avatar is downloaded once and inlined into the HTML page, so rendering makes zero external requests — fully self-contained.
4. **Render the badge to PNG** with headless Chromium — the action builds a self-contained HTML page, injects the avatar and extra stats, then screenshots it at `329x88`.
5. **Commit the PNG back to your repo.** The action checks via `git diff` whether the badge actually changed; if it did, it commits `image_path` and pushes. If nothing changed, it skips the commit to avoid cluttering your history.

On top of what TryHackMe's own badge shows (level, rooms, badges, streak, global rank), this badge adds **total points** and your **top-percentage bracket** (e.g. `top 2%`) — both live only in the profile JSON and never appear on THM's own badge image. The bracket comes from the `topPercentage` field and is left out automatically if the API doesn't return one.

## Finding your `userPublicId` (optional)

`username` is the simpler input, so this is only needed if you'd rather use the numeric ID. TryHackMe no longer shows the ID anywhere in its UI. The included `find_user_id.py` script finds it by binary search: it probes the badge API, reads each candidate user's join date from the profile API, and compares it to your username's join date to home in on your ID.

```bash
pip install curl_cffi
python3 find_user_id.py <your_tryhackme_username>
```

It assumes IDs are assigned incrementally at signup time. The default search range is `1 8600000`. You can pass a custom range if needed:

```bash
python3 find_user_id.py <your_tryhackme_username> 100000 4000000
```

It ends by printing your found ID and the command to render your badge with it.

## Embed your TryHackMe badge

Once you know your `userPublicId`, you can also embed your TryHackMe badge anywhere that supports HTML or iframes:

```html
<script src="https://tryhackme.com/badge/<userPublicId>"></script>
```

Or embed the public badge HTML in an iframe:

```html
<iframe src="https://tryhackme.com/api/v2/badges/public-profile?userPublicId=<userPublicId>"></iframe>
```

## Project Background

This project is inspired by and intended as a successor to [`p4p1/tryhackme-badge-workflow`](https://github.com/p4p1/tryhackme-badge-workflow). It keeps the same core idea: automatically update a TryHackMe badge in your GitHub profile README.

The original action was archived on 2026-04-19. Its dynamic mode used the TryHackMe badge API, which now blocks plain HTTP clients with an anti-bot challenge. Its static mode depended on `https://tryhackme-badges.s3.amazonaws.com/<username>.png`, a bucket that has been frozen since 2024.

This version uses `curl_cffi` to fetch the current badge HTML and profile data with a Chrome-like TLS handshake. It then renders the badge with headless Chromium and commits the resulting PNG to your repository. In addition to the official badge stats, it adds total points from the public profile API.

## Running locally

Two scripts are included in this repository:

- `thm_badge.py` — renders the badge PNG from a username or `userPublicId`
- `find_user_id.py` — converts a username to a `userPublicId` (optional)

```bash
git clone https://github.com/nahilr/tryhackme-profile-badge-workflow.git
cd tryhackme-profile-badge-workflow

pip install curl_cffi

# Render your badge — username works directly (one API call)
python3 thm_badge.py <your_username> [output.png]

# Or use the numeric ID (two API calls)
python3 find_user_id.py <your_username>
python3 thm_badge.py <userPublicId> [output.png]
```

Requires `google-chrome`, `chromium`, or `chromium-browser` on PATH (GitHub Actions runners have Chrome preinstalled).

## AI Disclosure

This project was created with assistance from AI tools. The code and documentation were reviewed and tested by the maintainer.

## License

MIT
