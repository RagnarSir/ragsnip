#!/usr/bin/env python3
"""Capture a screen region, upload, copy URL to clipboard.

Two modes:
  snip          one-shot capture & upload (suitable for hotkeys / terminal)
  snip --gui    floating window with Take-Snip button and thumbnail history
"""

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

DEFAULT_CLIENT_ID = "313baf0c7b4d3ff"  # Flameshot's public shared ID (rate-limited)
DEFAULT_HOST = "catbox"
DEFAULT_HISTORY_LIMIT = 20
CONFIG_PATH = Path.home() / ".config" / "ragsnip" / "config"
HISTORY_PATH = Path.home() / ".config" / "ragsnip" / "history.json"
THUMB_DIR = Path.home() / ".cache" / "ragsnip" / "thumbs"
THUMB_SIZE = 72

USER_AGENT = "ragsnip/1.0 (linux mint cinnamon)"


# ---------------------------- config & utilities ----------------------------

def _bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")


def load_config() -> dict:
    cfg = {
        "host": DEFAULT_HOST,
        "client_id": DEFAULT_CLIENT_ID,
        "keep_local": False,
        "always_on_top": True,
        "history_size": DEFAULT_HISTORY_LIMIT,
    }
    if not CONFIG_PATH.exists():
        return cfg
    for raw in CONFIG_PATH.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key == "host" and value:
            cfg["host"] = value.lower()
        elif key == "client_id" and value:
            cfg["client_id"] = value
        elif key == "keep_local":
            cfg["keep_local"] = _bool(value)
        elif key == "always_on_top":
            cfg["always_on_top"] = _bool(value)
        elif key == "history_size":
            try:
                cfg["history_size"] = max(1, min(200, int(value)))
            except ValueError:
                pass
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# snip configuration (managed by the GUI; manual edits preserved on next save)\n"
        "\n"
        "# Upload host: catbox | 0x0 | imgur\n"
        f"host={cfg.get('host', DEFAULT_HOST)}\n"
        "\n"
        "# Imgur Client-ID (only used when host=imgur). Empty = built-in shared default.\n"
        f"client_id={cfg.get('client_id', '') if cfg.get('client_id') != DEFAULT_CLIENT_ID else ''}\n"
        "\n"
        "# Keep the local screenshot file in /tmp after upload (debugging).\n"
        f"keep_local={'true' if cfg.get('keep_local') else 'false'}\n"
        "\n"
        "# Keep the GUI window above other windows.\n"
        f"always_on_top={'true' if cfg.get('always_on_top', True) else 'false'}\n"
        "\n"
        "# Number of recent snips to remember in history (1-200).\n"
        f"history_size={int(cfg.get('history_size', DEFAULT_HISTORY_LIMIT))}\n"
    )
    CONFIG_PATH.write_text(body)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def notify(summary: str, body: str = "", critical: bool = False) -> None:
    if not shutil.which("notify-send"):
        return
    args = ["notify-send", "-i", "image-x-generic"]
    if critical:
        args += ["-u", "critical"]
    args += [summary, body]
    subprocess.run(args, check=False)


def fail(reason: str) -> None:
    notify("RagSnip failed", reason, critical=True)
    print(f"snip: {reason}", file=sys.stderr)
    sys.exit(1)


def require_tool(name: str) -> None:
    if not shutil.which(name):
        fail(f"required tool '{name}' is not installed")


# ---------------------------- capture & upload ----------------------------

def capture_region(target: Path) -> bool:
    require_tool("gnome-screenshot")
    result = subprocess.run(
        ["gnome-screenshot", "-a", "-f", str(target)],
        check=False,
    )
    if result.returncode != 0:
        return False
    return target.exists() and target.stat().st_size > 0


def _multipart_body(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = "----snip" + uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        parts.append(value.encode() + b"\r\n")
    for name, (filename, data, mime) in files.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
        parts.append(data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _post(url: str, *, data: bytes, headers: dict, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error contacting {url}: {e.reason}") from None


def upload_catbox(path: Path, _cfg: dict) -> str:
    body, ctype = _multipart_body(
        {"reqtype": "fileupload"},
        {"fileToUpload": (path.name, path.read_bytes(), "image/png")},
    )
    raw = _post(
        "https://catbox.moe/user/api.php",
        data=body,
        headers={"Content-Type": ctype, "User-Agent": USER_AGENT},
    )
    link = raw.decode("utf-8", errors="replace").strip()
    if not link.startswith("https://"):
        raise RuntimeError(f"Unexpected catbox response: {link[:200]}")
    return link


def upload_0x0(path: Path, _cfg: dict) -> str:
    body, ctype = _multipart_body(
        {},
        {"file": (path.name, path.read_bytes(), "image/png")},
    )
    raw = _post(
        "https://0x0.st",
        data=body,
        headers={"Content-Type": ctype, "User-Agent": USER_AGENT},
    )
    link = raw.decode("utf-8", errors="replace").strip()
    if not link.startswith("https://"):
        raise RuntimeError(f"Unexpected 0x0.st response: {link[:200]}")
    return link


def upload_imgur(path: Path, cfg: dict) -> str:
    encoded = base64.standard_b64encode(path.read_bytes())
    body = urllib.parse.urlencode(
        {"image": encoded, "type": "base64", "name": path.name}
    ).encode("ascii")
    raw = _post(
        "https://api.imgur.com/3/image",
        data=body,
        headers={
            "Authorization": f"Client-ID {cfg['client_id']}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
    )
    payload = json.loads(raw.decode("utf-8"))
    if not payload.get("success") or "data" not in payload:
        raise RuntimeError(f"Unexpected Imgur response: {payload}")
    link = payload["data"].get("link")
    if not link:
        raise RuntimeError("Imgur response missing link")
    return link


HOSTS = {
    "catbox": upload_catbox,
    "0x0": upload_0x0,
    "imgur": upload_imgur,
}


def copy_to_clipboard(text: str) -> None:
    require_tool("xclip")
    subprocess.run(
        ["xclip", "-selection", "clipboard"],
        input=text.encode("utf-8"),
        check=True,
    )


# ---------------------------- history & thumbnails ----------------------------

def _thumb_path_for(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return THUMB_DIR / f"{digest}.png"


def make_thumb(image_path: Path, url: str) -> Path | None:
    """Create a square thumbnail PNG. Returns the path, or None on failure."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail((THUMB_SIZE, THUMB_SIZE))
            out = _thumb_path_for(url)
            img.save(out, format="PNG")
            return out
    except Exception:
        return None


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text())
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict) and "url" in e]
    except (OSError, json.JSONDecodeError):
        pass
    return []


def save_history(items: list[dict]) -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps(items, indent=2))
    except OSError:
        pass


# ---------------------------- one-shot mode ----------------------------

def do_oneshot(cfg: dict) -> int:
    uploader = HOSTS.get(cfg["host"])
    if uploader is None:
        fail(f"unknown host '{cfg['host']}' (valid: {', '.join(HOSTS)})")

    tmp = Path(tempfile.NamedTemporaryFile(suffix=".png", delete=False).name)
    try:
        if not capture_region(tmp):
            return 0
        try:
            link = uploader(tmp, cfg)
        except RuntimeError as e:
            fail(str(e))
        copy_to_clipboard(link)
        notify("RagSnip uploaded", link)
        # one-shot mode also records history so the GUI sees it
        thumb = make_thumb(tmp, link)
        history = load_history()
        history.insert(0, {
            "url": link,
            "thumb": str(thumb) if thumb else None,
            "ts": time.time(),
        })
        save_history(history[:cfg.get("history_size", DEFAULT_HISTORY_LIMIT)])
        print(link)
        return 0
    finally:
        if not cfg["keep_local"]:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------- GUI mode ----------------------------

# Color palette — soft, readable, works on Mint's default light theme.
COLORS = {
    "bg":          "#fafafa",
    "panel":       "#ffffff",
    "card":        "#ffffff",
    "card_hover":  "#eef4fb",
    "accent":      "#3b82f6",
    "accent_hov":  "#2563eb",
    "accent_text": "#ffffff",
    "text":        "#1f2937",
    "muted":       "#6b7280",
    "subtle":      "#9ca3af",
    "divider":     "#e5e7eb",
    "header":      "#f3f4f6",
    "danger":      "#dc2626",
}


def fmt_relative(ts: float) -> str:
    delta = max(0.0, time.time() - ts)
    if delta < 45:
        return "just now"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    if delta < 86400 * 7:
        return f"{int(delta / 86400)}d ago"
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _apply_style(root) -> None:
    from tkinter import ttk
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    base_font = ("Ubuntu", 10) if "Ubuntu" in root.tk.call("font", "families") else ("Sans", 10)
    bold_font = (base_font[0], base_font[1], "bold")
    big_font = (base_font[0], 13, "bold")
    small_font = (base_font[0], 9)

    root.configure(bg=COLORS["bg"])

    style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=base_font)
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("Card.TFrame", background=COLORS["card"])
    style.configure("CardHover.TFrame", background=COLORS["card_hover"])
    style.configure("Header.TFrame", background=COLORS["header"])

    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Card.TLabel", background=COLORS["card"], foreground=COLORS["text"])
    style.configure("CardHover.TLabel", background=COLORS["card_hover"], foreground=COLORS["text"])
    style.configure("Header.TLabel", background=COLORS["header"], foreground=COLORS["text"], font=bold_font)
    style.configure("Title.TLabel", background=COLORS["header"], foreground=COLORS["text"], font=big_font)
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=small_font)
    style.configure("Hint.TLabel", background=COLORS["header"], foreground=COLORS["muted"], font=small_font)
    style.configure("CardMuted.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=small_font)
    style.configure("CardHoverMuted.TLabel", background=COLORS["card_hover"], foreground=COLORS["muted"], font=small_font)

    style.configure("Accent.TButton",
                    background=COLORS["accent"], foreground=COLORS["accent_text"],
                    font=bold_font, padding=(14, 10), borderwidth=0)
    style.map("Accent.TButton",
              background=[("active", COLORS["accent_hov"]), ("disabled", "#9ca3af")],
              foreground=[("disabled", "#f3f4f6")])

    style.configure("Ghost.TButton",
                    background=COLORS["header"], foreground=COLORS["muted"],
                    padding=(8, 4), borderwidth=0, font=base_font)
    style.map("Ghost.TButton",
              background=[("active", COLORS["divider"])],
              foreground=[("active", COLORS["text"])])

    style.configure("TSeparator", background=COLORS["divider"])

    return base_font, bold_font, small_font


def open_settings(parent, current: dict, on_save) -> None:
    import tkinter as tk
    from tkinter import ttk, messagebox

    win = tk.Toplevel(parent)
    win.title("RagSnip — Settings")
    win.transient(parent)
    win.grab_set()
    win.configure(bg=COLORS["bg"])
    win.geometry("520x560")
    win.minsize(440, 500)
    win.resizable(True, True)

    outer = ttk.Frame(win, padding=18)
    outer.pack(fill="both", expand=True)

    # Form section (top, expands with window)
    form = ttk.Frame(outer)
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)

    title_lbl = ttk.Label(form, text="Settings", font=("Sans", 14, "bold"))
    title_lbl.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

    # Host
    ttk.Label(form, text="Upload host").grid(row=1, column=0, sticky="w", pady=(0, 4))
    host_var = tk.StringVar(value=current.get("host", DEFAULT_HOST))
    host_combo = ttk.Combobox(
        form, textvariable=host_var, values=list(HOSTS.keys()),
        state="readonly",
    )
    host_combo.grid(row=1, column=1, sticky="ew", pady=(0, 4), padx=(10, 0))

    host_help = ttk.Label(
        form, text="catbox: no auth · 0x0: no auth · imgur: needs Client-ID",
        style="Muted.TLabel",
    )
    host_help.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 14))

    # Imgur Client-ID
    ttk.Label(form, text="Imgur Client-ID").grid(row=3, column=0, sticky="w", pady=(0, 4))
    cid = current.get("client_id", "")
    cid_display = "" if cid == DEFAULT_CLIENT_ID else cid
    cid_var = tk.StringVar(value=cid_display)
    cid_entry = ttk.Entry(form, textvariable=cid_var)
    cid_entry.grid(row=3, column=1, sticky="ew", pady=(0, 4), padx=(10, 0))

    cid_help = ttk.Label(
        form, text="Leave blank to use the built-in shared default.",
        style="Muted.TLabel",
    )
    cid_help.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 14))

    def _toggle_cid(*_):
        is_imgur = host_var.get() == "imgur"
        cid_entry.configure(state=("normal" if is_imgur else "disabled"))
    host_var.trace_add("write", _toggle_cid)
    _toggle_cid()

    # Checkboxes
    keep_var = tk.BooleanVar(value=bool(current.get("keep_local", False)))
    aot_var = tk.BooleanVar(value=bool(current.get("always_on_top", True)))

    ttk.Checkbutton(form, text="Keep the local screenshot file (debug)",
                    variable=keep_var).grid(row=5, column=0, columnspan=2, sticky="w", pady=2)
    ttk.Checkbutton(form, text="Always on top",
                    variable=aot_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=2)

    # History size
    ttk.Label(form, text="History size").grid(row=7, column=0, sticky="w", pady=(14, 4))
    size_var = tk.StringVar(value=str(current.get("history_size", DEFAULT_HISTORY_LIMIT)))
    ttk.Spinbox(form, from_=1, to=200, textvariable=size_var, width=6).grid(
        row=7, column=1, sticky="w", pady=(14, 4), padx=(10, 0)
    )

    # Clear history
    def _clear_history():
        if messagebox.askyesno(
            "Clear history",
            "Remove all history entries and cached thumbnails?",
            parent=win,
        ):
            try:
                if HISTORY_PATH.exists():
                    HISTORY_PATH.unlink()
                if THUMB_DIR.exists():
                    for f in THUMB_DIR.iterdir():
                        try:
                            f.unlink()
                        except OSError:
                            pass
            except OSError:
                pass
            on_save({"_cleared_history": True})
            win.destroy()

    ttk.Button(form, text="Clear history", command=_clear_history,
               style="Ghost.TButton").grid(row=8, column=0, sticky="w", pady=(16, 0))

    # Spacer row absorbs extra vertical space when the window is enlarged
    form.rowconfigure(9, weight=1)

    # Action buttons (bottom, fixed)
    btns = ttk.Frame(outer)
    btns.pack(fill="x", side="bottom", pady=(16, 0))

    def _cancel():
        win.destroy()

    def _save():
        try:
            new_size = max(1, min(200, int(size_var.get())))
        except ValueError:
            messagebox.showerror("Invalid", "History size must be a number 1–200.", parent=win)
            return
        new_cid = cid_var.get().strip() or DEFAULT_CLIENT_ID
        new_cfg = {
            "host": host_var.get(),
            "client_id": new_cid,
            "keep_local": bool(keep_var.get()),
            "always_on_top": bool(aot_var.get()),
            "history_size": new_size,
        }
        try:
            save_config(new_cfg)
        except OSError as e:
            messagebox.showerror("Save failed", f"Could not write config: {e}", parent=win)
            return
        on_save(new_cfg)
        win.destroy()

    ttk.Button(btns, text="Cancel", command=_cancel, style="Ghost.TButton").pack(side="right", padx=(8, 0))
    ttk.Button(btns, text="Save", command=_save, style="Accent.TButton").pack(side="right")

    # Wrap help labels to current width so they line-break when narrow
    def _rewrap(_e=None):
        wrap = max(200, form.winfo_width() - 20)
        host_help.configure(wraplength=wrap)
        cid_help.configure(wraplength=wrap)
    form.bind("<Configure>", _rewrap)

    win.update_idletasks()
    # center over parent
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    ww, wh = win.winfo_width(), win.winfo_height()
    win.geometry(f"+{px + (pw - ww) // 2}+{py + (ph - wh) // 2}")


def run_gui(cfg: dict) -> int:
    import tkinter as tk
    from tkinter import ttk

    if cfg["host"] not in HOSTS:
        fail(f"unknown host '{cfg['host']}' (valid: {', '.join(HOSTS)})")

    root = tk.Tk(className="RagSnip")
    root.title("RagSnip")
    root.geometry("500x720")
    root.minsize(440, 560)

    base_font, bold_font, small_font = _apply_style(root)
    root.attributes("-topmost", bool(cfg.get("always_on_top", True)))

    state = {
        "cfg": dict(cfg),
        "history": load_history(),
        "thumb_refs": [],
        "busy": False,
    }

    # === Header bar ==========================================================
    header = ttk.Frame(root, style="Header.TFrame", padding=(14, 10))
    header.pack(fill="x")

    ttk.Label(header, text="RagSnip", style="Title.TLabel").pack(side="left")
    host_label_var = tk.StringVar()
    ttk.Label(header, textvariable=host_label_var, style="Hint.TLabel").pack(
        side="left", padx=(10, 0), pady=(4, 0)
    )

    settings_btn = ttk.Button(header, text="⚙  Settings", style="Ghost.TButton")
    settings_btn.pack(side="right")

    ttk.Separator(root, orient="horizontal").pack(fill="x")

    # === Action panel ========================================================
    action = ttk.Frame(root, padding=(14, 14))
    action.pack(fill="x")

    btn = ttk.Button(action, text="📷   Take Snip", style="Accent.TButton")
    btn.pack(fill="x", ipady=4)

    status_var = tk.StringVar(value="Ready — click Take Snip to capture a region.")
    ttk.Label(action, textvariable=status_var, style="Muted.TLabel",
              wraplength=380, justify="left").pack(fill="x", pady=(8, 0), anchor="w")

    ttk.Separator(root, orient="horizontal").pack(fill="x")

    # === History header ======================================================
    hist_head = ttk.Frame(root, padding=(14, 8))
    hist_head.pack(fill="x")
    ttk.Label(hist_head, text="Recent snips", style="Header.TLabel",
              background=COLORS["bg"]).pack(side="left")
    count_var = tk.StringVar()
    ttk.Label(hist_head, textvariable=count_var, style="Muted.TLabel").pack(side="right")

    # === Scrollable history list =============================================
    list_wrap = ttk.Frame(root)
    list_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    canvas = tk.Canvas(list_wrap, highlightthickness=0,
                       bg=COLORS["bg"], bd=0)
    scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    list_frame = ttk.Frame(canvas, style="TFrame")
    list_window = canvas.create_window((0, 0), window=list_frame, anchor="nw")

    list_frame.bind("<Configure>",
                    lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfigure(list_window, width=e.width))

    def _on_wheel(e):
        delta = -1 if (e.num == 4 or getattr(e, "delta", 0) > 0) else 1
        canvas.yview_scroll(delta, "units")
    canvas.bind_all("<Button-4>", _on_wheel)
    canvas.bind_all("<Button-5>", _on_wheel)
    canvas.bind_all("<MouseWheel>", _on_wheel)

    # === Helpers =============================================================

    def set_status(msg: str) -> None:
        status_var.set(msg[:140])

    def update_chrome():
        host_label_var.set(f"· {state['cfg']['host']}")
        n = len(state["history"])
        count_var.set(f"{n} item{'s' if n != 1 else ''}")
        root.attributes("-topmost", bool(state["cfg"].get("always_on_top", True)))

    def render_history():
        for w in list_frame.winfo_children():
            w.destroy()
        state["thumb_refs"].clear()
        update_chrome()

        if not state["history"]:
            empty = ttk.Frame(list_frame, padding=(20, 30))
            empty.pack(fill="x")
            ttk.Label(
                empty,
                text="No snips yet.\nClick Take Snip to capture your first region.",
                style="Muted.TLabel", justify="center", anchor="center",
            ).pack(fill="x")
            return

        for entry in state["history"]:
            _render_card(entry)

    def _render_card(entry: dict):
        url = entry["url"]
        ts = entry.get("ts", time.time())

        card = tk.Frame(list_frame, bg=COLORS["card"],
                        highlightbackground=COLORS["divider"],
                        highlightthickness=1, bd=0, cursor="hand2")
        card.pack(fill="x", pady=4, padx=2)

        inner = tk.Frame(card, bg=COLORS["card"], padx=10, pady=8)
        inner.pack(fill="x")

        # thumbnail — fall back to recomputed path if stored one is stale
        thumb_path = entry.get("thumb")
        thumb = Path(thumb_path) if thumb_path else None
        if not (thumb and thumb.exists()):
            recomputed = _thumb_path_for(url)
            thumb = recomputed if recomputed.exists() else None
        if thumb is not None:
            try:
                img = tk.PhotoImage(file=str(thumb))
                state["thumb_refs"].append(img)
                img_lbl = tk.Label(inner, image=img, bg=COLORS["card"], bd=0)
            except tk.TclError:
                img_lbl = tk.Label(inner, text="?", width=8, height=4,
                                   bg=COLORS["divider"], fg=COLORS["muted"])
        else:
            img_lbl = tk.Label(inner, text="(no\npreview)", width=8, height=4,
                               bg=COLORS["divider"], fg=COLORS["muted"],
                               font=small_font, justify="center")
        img_lbl.pack(side="left", padx=(0, 10))

        text_box = tk.Frame(inner, bg=COLORS["card"])
        text_box.pack(side="left", fill="both", expand=True)

        url_lbl = tk.Label(
            text_box, text=url, anchor="w", justify="left",
            wraplength=240, bg=COLORS["card"], fg=COLORS["text"],
            font=base_font,
        )
        url_lbl.pack(fill="x", anchor="w")

        meta_lbl = tk.Label(
            text_box, text=fmt_relative(ts),
            anchor="w", bg=COLORS["card"], fg=COLORS["muted"],
            font=small_font,
        )
        meta_lbl.pack(fill="x", anchor="w", pady=(2, 0))

        widgets = [card, inner, text_box, img_lbl, url_lbl, meta_lbl]

        def _enter(_e):
            for w in widgets:
                try:
                    w.configure(bg=COLORS["card_hover"])
                except tk.TclError:
                    pass
            try:
                meta_lbl.configure(fg=COLORS["muted"])
            except tk.TclError:
                pass

        def _leave(_e):
            for w in widgets:
                try:
                    w.configure(bg=COLORS["card"])
                except tk.TclError:
                    pass

        def _click(_e):
            try:
                copy_to_clipboard(url)
                set_status(f"Copied: {url}")
            except Exception as ex:
                set_status(f"Copy failed: {ex}")

        for w in widgets:
            w.bind("<Button-1>", _click)
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

    # === Snip workflow =======================================================

    def snip_worker():
        cfg_now = state["cfg"]
        uploader = HOSTS[cfg_now["host"]]
        tmp = Path(tempfile.NamedTemporaryFile(suffix=".png", delete=False).name)
        result = {"link": None, "thumb": None, "error": None, "cancelled": False}
        try:
            if not capture_region(tmp):
                result["cancelled"] = True
                return
            try:
                link = uploader(tmp, cfg_now)
            except RuntimeError as e:
                result["error"] = str(e)
                return
            try:
                copy_to_clipboard(link)
            except Exception as e:
                result["error"] = f"Clipboard failed: {e}"
                return
            thumb = make_thumb(tmp, link)
            result["link"] = link
            result["thumb"] = str(thumb) if thumb else None
        finally:
            if not cfg_now.get("keep_local"):
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            root.after(0, snip_done, result)

    def snip_done(result: dict):
        root.deiconify()
        root.attributes("-topmost", bool(state["cfg"].get("always_on_top", True)))
        root.lift()
        btn.configure(state="normal")
        state["busy"] = False

        if result["cancelled"]:
            set_status("Cancelled")
            return
        if result["error"]:
            set_status(result["error"])
            notify("RagSnip failed", result["error"], critical=True)
            return

        link = result["link"]
        state["history"].insert(0, {
            "url": link,
            "thumb": result["thumb"],
            "ts": time.time(),
        })
        limit = state["cfg"].get("history_size", DEFAULT_HISTORY_LIMIT)
        state["history"][:] = state["history"][:limit]
        save_history(state["history"])
        render_history()
        set_status(f"Uploaded · URL on clipboard · {link}")
        notify("RagSnip uploaded", link)

    def on_snip():
        if state["busy"]:
            return
        state["busy"] = True
        btn.configure(state="disabled")
        set_status("Selecting region…")
        root.withdraw()
        root.update_idletasks()
        root.after(180, lambda: threading.Thread(target=snip_worker, daemon=True).start())

    btn.configure(command=on_snip)

    # === Settings integration ================================================

    def on_settings_saved(new_cfg: dict):
        if new_cfg.get("_cleared_history"):
            state["history"] = []
            save_history(state["history"])
            render_history()
            set_status("History cleared.")
            return
        state["cfg"] = new_cfg
        update_chrome()
        # if history limit shrank, trim and persist
        limit = new_cfg.get("history_size", DEFAULT_HISTORY_LIMIT)
        if len(state["history"]) > limit:
            state["history"][:] = state["history"][:limit]
            save_history(state["history"])
            render_history()
        set_status(f"Settings saved · host={new_cfg['host']}")

    def on_settings_click():
        open_settings(root, state["cfg"], on_settings_saved)

    settings_btn.configure(command=on_settings_click)

    render_history()
    root.mainloop()
    return 0


# ---------------------------- entry ----------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a region and upload.")
    parser.add_argument("--gui", action="store_true",
                        help="open the persistent app window instead of one-shot capture")
    args = parser.parse_args()

    cfg = load_config()
    if args.gui:
        return run_gui(cfg)
    return do_oneshot(cfg)


if __name__ == "__main__":
    sys.exit(main())
