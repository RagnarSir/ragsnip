# RagSnip

A tiny snipping tool for Linux. Drag a region → it uploads → the URL lands on your clipboard.

Built for Linux Mint Cinnamon (X11). Works on any X11 desktop with `gnome-screenshot`, `xclip`, and Python 3.

```
┌──────────────────────────────────────┐
│ RagSnip  · catbox        ⚙ Settings │
├──────────────────────────────────────┤
│                                      │
│        📷    Take Snip               │
│                                      │
│  Ready                               │
├──────────────────────────────────────┤
│  Recent snips              3 items   │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ ▦  https://files.catbox.moe/…  │  │
│  │    2m ago                      │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │ ▦  https://files.catbox.moe/…  │  │
│  │    15m ago                     │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

## Features

- **One-drag capture** via `gnome-screenshot -a`
- **Auto-upload** to catbox.moe (default), 0x0.st, or Imgur
- **URL on clipboard** the instant the upload finishes
- **Desktop notification** with the link
- **Persistent GUI** with a thumbnail history (click any row to re-copy)
- **Settings dialog** — host, Imgur Client-ID, "always on top", history size, clear history
- **One-shot CLI** for keyboard shortcuts (`ragsnip` / `snip`)

## Requirements

| Tool              | Used for       | Install on Ubuntu/Mint                  |
|-------------------|----------------|-----------------------------------------|
| `gnome-screenshot`| Region capture | `sudo apt install gnome-screenshot`     |
| `xclip`           | Clipboard      | `sudo apt install xclip`                |
| `notify-send`     | Notifications  | usually preinstalled (`libnotify-bin`)  |
| Python 3 + Pillow | Script + thumbs| `sudo apt install python3 python3-pil`  |

No `pip` install, no virtualenv, no extra dependencies — script is stdlib only apart from Pillow for the 72×72 thumbnails.

## Install

```bash
git clone https://github.com/RagnarSir/ragsnip.git
cd ragsnip
./install.sh
```

The installer drops:

| Path                                              | What                              |
|---------------------------------------------------|-----------------------------------|
| `~/.local/bin/ragsnip`                            | Main executable                   |
| `~/.local/bin/snip`                               | Symlink → `ragsnip` (compat alias)|
| `~/.local/share/applications/ragsnip.desktop`     | Menu entry                        |
| `~/.config/ragsnip/config`                        | Default config (only if missing)  |

It's idempotent — re-running upgrades the binary in place. If you previously installed under `~/.config/snip/` and `~/.cache/snip/`, those are migrated automatically.

## Usage

```bash
ragsnip --gui     # open the persistent window
ragsnip           # one-shot capture (cancels silently if you press Esc)
snip              # same as `ragsnip`
```

The GUI also gets launched by clicking **RagSnip** in the Cinnamon application menu.

### Keyboard shortcut

*Menu → Preferences → Keyboard → Shortcuts → Custom Shortcuts → Add custom shortcut*

- **Name**: RagSnip
- **Command**: `ragsnip`

Then bind any key (e.g. `Ctrl+PrintScreen`).

## Hosts

| Host                | Auth needed   | Notes                                                          |
|---------------------|---------------|----------------------------------------------------------------|
| `catbox` *(default)*| none          | catbox.moe — persistent, no rate limits, forum-friendly         |
| `0x0`               | none          | 0x0.st — retention shrinks with file size and age              |
| `imgur`             | Client-ID     | Built-in shared ID is rate-limited; paste your own in Settings |

Hattrick.org embeds catbox URLs via `[image=URL]` — that's why it's the default.

## Configuration

`~/.config/ragsnip/config` — the GUI Settings dialog rewrites this file on save, but you can also edit by hand:

```ini
host=catbox
client_id=             # only consulted when host=imgur
keep_local=false       # keep the /tmp screenshot for debugging
always_on_top=true
history_size=20        # 1–200
```

History lives at `~/.config/ragsnip/history.json`; thumbnails are cached at `~/.cache/ragsnip/thumbs/`.

## Files in this repo

| File                | Purpose                                       |
|---------------------|-----------------------------------------------|
| `ragsnip.py`        | Single-file app (CLI + Tk GUI)                |
| `ragsnip.desktop`   | Cinnamon/freedesktop menu entry               |
| `install.sh`        | Idempotent installer + legacy-path migration  |

## Why "RagSnip"?

It snips. By Ragnar.
