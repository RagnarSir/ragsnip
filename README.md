# RagSnip

A tiny snipping tool for **Linux** and **Windows**. Drag a region → it uploads → the URL lands on your clipboard.

- **Linux** — Mint/Cinnamon, any X11 desktop with `gnome-screenshot`, `xclip`, and Python 3.
- **Windows** — 10 or 11. Wraps the built-in Snip & Sketch overlay; ships as a single-file installer (`.exe`).

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

## Windows

> Download. Double-click. Done.

1. Go to the [Releases page](https://github.com/RagnarSir/ragsnip/releases).
2. Download `RagSnip-Setup-<version>.exe`.
3. Double-click it. The wizard installs RagSnip per-user (no admin / UAC) under `%LOCALAPPDATA%\Programs\RagSnip\` and adds a Start Menu shortcut.
4. Launch **RagSnip** from the Start Menu.

The installer auto-registers an uninstaller that shows up in Settings → Apps → RagSnip; running a newer installer over an existing install upgrades in place.

> **First-launch note:** unsigned installers trigger Windows SmartScreen with "Windows protected your PC". Click *More info* → *Run anyway*. Code-signing certificates are not free, so the installer will stay unsigned for now.

### Usage on Windows

The Start Menu shortcut launches the GUI. Click **Take Snip** → the Windows **Snip & Sketch** overlay opens → drag a region → the window returns with the URL on your clipboard and a thumbnail in the history list. Click any history row to re-copy that URL.

To run a one-shot capture without opening the GUI (useful for hotkeys), call `RagSnip.exe --cli`.

### Keyboard shortcut on Windows

Right-click the Start Menu entry (or copy it to the Desktop) → **Properties** → click in **Shortcut key** → press your desired combo (e.g. `Ctrl + Alt + S`) → **OK**. Pressing the combo launches RagSnip.

For an instant hotkey snip with no GUI, edit the shortcut's **Target** field to read `"…\RagSnip.exe" --cli`.

### Limitations on Windows

- **No toast notifications** — the GUI status label and the URL on your clipboard are the feedback channel.
- **Clipboard briefly holds the captured image** before RagSnip replaces it with the URL. The contents your clipboard had before the snip are not preserved.
- The Snip & Sketch overlay is the native Windows region selector — its UX comes from Windows, not RagSnip.

### Building from source (maintainers)

The Windows installer is built by chaining PyInstaller and Inno Setup. To reproduce a release:

1. Install the prerequisites on a Windows machine:
   - Python 3.9+ (from [python.org](https://www.python.org/downloads/) or the Microsoft Store; tick *Add to PATH* during install)
   - Inno Setup 6 ([jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php) or `choco install innosetup`)

2. From a PowerShell prompt in the repo root:
   ```powershell
   cd windows
   powershell -ExecutionPolicy Bypass -File .\build.ps1
   ```

3. The output is `windows\Output\RagSnip-Setup-<version>.exe`. Upload it as a release asset on GitHub.

To bump the version, edit `MyAppVersion` in `windows\RagSnip.iss` and re-run `build.ps1`.

## Hosts

| Host                | Auth needed   | Notes                                                          |
|---------------------|---------------|----------------------------------------------------------------|
| `catbox` *(default)*| none          | catbox.moe — persistent, no rate limits, forum-friendly         |
| `0x0`               | none          | 0x0.st — retention shrinks with file size and age              |
| `imgur`             | Client-ID     | Built-in shared ID is rate-limited; paste your own in Settings |

Hattrick.org embeds catbox URLs via `[image=URL]` — that's why it's the default.

## Configuration

The GUI Settings dialog rewrites the config file on save; you can also edit by hand. Format is the same on both platforms:

```ini
host=catbox
client_id=             # only consulted when host=imgur
keep_local=false       # keep the temp screenshot for debugging
always_on_top=true
history_size=20        # 1–200
```

| Platform | Config file                            | History                                  | Thumbnails                                 |
|----------|----------------------------------------|------------------------------------------|--------------------------------------------|
| Linux    | `~/.config/ragsnip/config`             | `~/.config/ragsnip/history.json`         | `~/.cache/ragsnip/thumbs/`                 |
| Windows  | `%APPDATA%\RagSnip\config`             | `%APPDATA%\RagSnip\history.json`         | `%LOCALAPPDATA%\RagSnip\Cache\thumbs\`     |

## Files in this repo

| File                          | Purpose                                       |
|-------------------------------|-----------------------------------------------|
| `ragsnip.py`                  | Linux app (single file, CLI + Tk GUI)         |
| `ragsnip.desktop`             | Cinnamon / freedesktop menu entry             |
| `install.sh`                  | Linux installer + legacy-path migration       |
| `windows/ragsnip.py`          | Windows app (single file, GUI-default)        |
| `windows/RagSnip.iss`         | Inno Setup script for the installer           |
| `windows/build.ps1`           | PyInstaller → Inno Setup chain (maintainer)   |

## Why "RagSnip"?

It snips. By Ragnar.
