#!/usr/bin/env python3
"""Local web UI for translating baked-text game PNGs.

Scans patch/to_translate/, flattens nested folders into one work queue,
previews each image, and lets you upload an English replacement that
overwrites the original file in place.

Star (flag) the images that need a replacement. Done and todo are separate:
most files in the folder can stay as they are.

  python3 tools/image_workspace.py
  # open http://127.0.0.1:8765

Voice files are never touched — this tool only handles PNGs under
patch/to_translate/ (the image translation workspace).
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "patch" / "to_translate"
DEFAULT_MANIFEST = DEFAULT_WORKSPACE / "manifest.csv"
DEFAULT_STATUS = DEFAULT_WORKSPACE / ".workspace_status.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# Bound after parse_args
WORKSPACE: Path = DEFAULT_WORKSPACE
MANIFEST_PATH: Path = DEFAULT_MANIFEST
STATUS_PATH: Path = DEFAULT_STATUS


def load_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST_PATH.exists():
        return {}
    by_png: dict[str, dict[str, str]] = {}
    with MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for png in (row.get("png_files") or "").split(";"):
                png = png.strip()
                if png:
                    by_png[png] = row
            # also index stem path
            rel = row.get("relative_path", "")
            if rel:
                stem_png = str(Path(rel).with_suffix(".png"))
                by_png.setdefault(stem_png, row)
    return by_png


def load_status() -> dict[str, dict]:
    if not STATUS_PATH.exists():
        return {}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_status(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_rel_path(raw: str) -> Path | None:
    """Resolve a relative path under WORKSPACE; reject escapes."""
    if not raw or "\x00" in raw:
        return None
    raw = urllib.parse.unquote(raw).replace("\\", "/").lstrip("/")
    if ".." in Path(raw).parts:
        return None
    candidate = (WORKSPACE / raw).resolve()
    try:
        candidate.relative_to(WORKSPACE.resolve())
    except ValueError:
        return None
    return candidate


def list_images() -> list[dict]:
    manifest = load_manifest()
    status = load_status()
    images: list[dict] = []
    if not WORKSPACE.exists():
        return images

    for path in sorted(WORKSPACE.rglob("*.png")):
        rel = str(path.relative_to(WORKSPACE)).replace("\\", "/")
        meta = manifest.get(rel, {})
        st = status.get(rel, {})
        try:
            from PIL import Image

            with Image.open(path) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0

        images.append(
            {
                "path": rel,
                "name": path.name,
                "folder": str(Path(rel).parent).replace("\\", "/"),
                "size": path.stat().st_size,
                "mtime": int(path.stat().st_mtime),
                "width": width,
                "height": height,
                "category": meta.get("category", ""),
                "priority": meta.get("priority", ""),
                "status": meta.get("status", ""),
                "english_hint": meta.get("english_hint", ""),
                "notes": meta.get("notes", ""),
                "done": bool(st.get("done")),
                "flagged": bool(st.get("flagged")),
                "note": st.get("note", ""),
            }
        )
    return images


def parse_multipart(body: bytes, content_type: str) -> dict[str, tuple[str | None, bytes]]:
    """Parse multipart/form-data into {name: (filename, data)}."""
    match = re.search(r"boundary=([^;]+)", content_type, re.I)
    if not match:
        raise ValueError("missing boundary")
    boundary = match.group(1).strip().strip('"').encode("ascii", "ignore")
    if not boundary:
        raise ValueError("empty boundary")

    parts: dict[str, tuple[str | None, bytes]] = {}
    delimiter = b"--" + boundary
    for chunk in body.split(delimiter):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        if chunk.startswith(b"--"):
            continue
        header_blob, _, data = chunk.partition(b"\r\n\r\n")
        if data.endswith(b"\r\n"):
            data = data[:-2]
        headers = header_blob.decode("utf-8", "replace")
        name_m = re.search(r'name="([^"]+)"', headers)
        if not name_m:
            continue
        name = name_m.group(1)
        file_m = re.search(r'filename="([^"]*)"', headers)
        filename = file_m.group(1) if file_m else None
        parts[name] = (filename, data)
    return parts


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Švejk Image Workspace</title>
<style>
  :root {
    --bg: #0f1218;
    --panel: #171b24;
    --panel2: #1e2430;
    --border: #2a3344;
    --text: #e8ecf4;
    --muted: #8b95a8;
    --accent: #c9a227;
    --accent2: #3d8bfd;
    --ok: #3dba7a;
    --danger: #e35d6a;
    --font: "Segoe UI", system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    display: grid;
    grid-template-rows: auto 1fr;
  }
  header {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
  }
  header h1 {
    font-size: 1.05rem;
    font-weight: 600;
    margin: 0;
    color: var(--accent);
    letter-spacing: 0.02em;
  }
  header .stats { color: var(--muted); font-size: 0.9rem; }
  header .stats strong { color: var(--ok); }
  header .stats strong.flagged { color: var(--accent); }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-left: auto;
  }
  input[type="search"], select, button, label.btn {
    font: inherit;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--panel2);
    color: var(--text);
    padding: 7px 12px;
  }
  input[type="search"] { min-width: 200px; }
  button, label.btn {
    cursor: pointer;
    user-select: none;
  }
  button:hover, label.btn:hover { border-color: var(--accent); }
  button.primary { background: #2a3a1e; border-color: #4a7a2e; color: #c8f0a8; }
  button.primary:hover { border-color: var(--ok); }
  button.danger { background: #2a181a; border-color: #6a3038; }
  button:disabled { opacity: 0.45; cursor: not-allowed; }
  label.btn input { display: none; }
  main {
    display: grid;
    grid-template-columns: 320px 1fr;
    min-height: 0;
  }
  @media (max-width: 900px) {
    main { grid-template-columns: 1fr; grid-template-rows: 40vh 1fr; }
  }
  #list {
    overflow: auto;
    overflow-x: hidden;
    border-right: 1px solid var(--border);
    background: var(--panel);
  }
  .item {
    display: grid;
    grid-template-columns: 32px 56px minmax(0, 1fr);
    gap: 8px;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    align-items: center;
  }
  .item:hover { background: var(--panel2); }
  .item.active { background: #243044; outline: 1px solid var(--accent2); }
  .item.flagged { box-shadow: inset 3px 0 0 var(--accent); }
  .item.done { opacity: 0.55; }
  #list button.star {
    width: 28px;
    height: 28px;
    padding: 0;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--panel2);
    color: var(--text);
    font-size: 14px;
    line-height: 1;
  }
  #list button.star:hover { border-color: var(--accent); }
  #list button.star.on,
  #btn-flag.flag-on {
    border-color: var(--accent);
    color: var(--accent);
  }
  .meta { min-width: 0; }
  .item.done .name::after {
    content: " ✓";
    color: var(--ok);
  }
  .thumb {
    width: 56px;
    height: 42px;
    object-fit: contain;
    background: #000;
    border-radius: 3px;
    border: 1px solid var(--border);
  }
  .meta .name {
    font-size: 0.82rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .meta .sub {
    font-size: 0.72rem;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #detail {
    display: grid;
    grid-template-rows: auto 1fr auto;
    min-height: 0;
    background: var(--bg);
  }
  .detail-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: flex-start;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
  }
  .detail-bar .info { flex: 1; min-width: 200px; }
  .detail-bar .path {
    font-family: ui-monospace, monospace;
    font-size: 0.85rem;
    word-break: break-all;
  }
  .detail-bar .hint { color: var(--muted); font-size: 0.88rem; margin-top: 4px; }
  .detail-bar .actions { display: flex; flex-wrap: wrap; gap: 8px; }
  .preview-wrap {
    overflow: auto;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    background:
      linear-gradient(45deg, #1a1f28 25%, transparent 25%),
      linear-gradient(-45deg, #1a1f28 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #1a1f28 75%),
      linear-gradient(-45deg, transparent 75%, #1a1f28 75%);
    background-size: 20px 20px;
    background-position: 0 0, 0 10px, 10px -10px, -10px 0;
    background-color: #12161e;
  }
  #preview {
    max-width: 100%;
    max-height: calc(100vh - 220px);
    image-rendering: pixelated;
    border: 1px solid var(--border);
    background: #000;
    box-shadow: 0 8px 32px rgba(0,0,0,0.45);
  }
  .dropzone {
    margin: 0 16px 16px;
    padding: 18px;
    border: 2px dashed var(--border);
    border-radius: 10px;
    text-align: center;
    color: var(--muted);
    background: var(--panel);
    transition: border-color 0.15s, background 0.15s;
  }
  .dropzone.drag {
    border-color: var(--accent);
    background: #2a2410;
    color: var(--text);
  }
  .dropzone strong { color: var(--accent); }
  .toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #1e3a28;
    border: 1px solid var(--ok);
    color: #d4f5e0;
    padding: 10px 16px;
    border-radius: 8px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
    z-index: 50;
  }
  .toast.show { opacity: 1; }
  .empty {
    padding: 40px 20px;
    text-align: center;
    color: var(--muted);
  }
  kbd {
    font-size: 0.75rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 5px;
    background: var(--panel2);
  }
</style>
</head>
<body>
<header>
  <h1>Švejk Image Workspace</h1>
  <div class="stats" id="stats">Loading…</div>
  <div class="controls">
    <input type="search" id="search" placeholder="Filter path / hint…" />
    <select id="filter">
      <option value="todo">Todo only</option>
      <option value="flagged">Flagged only</option>
      <option value="all">All</option>
      <option value="done">Done only</option>
    </select>
    <select id="category">
      <option value="">All categories</option>
    </select>
    <button type="button" id="btn-refresh" title="Rescan folder">↻ Refresh</button>
  </div>
</header>
<main>
  <aside id="list"><div class="empty">Loading images…</div></aside>
  <section id="detail">
    <div class="detail-bar">
      <div class="info">
        <div class="path" id="path">Select an image</div>
        <div class="hint" id="hint">← → move · f flags for replacement · d done · u todo</div>
      </div>
      <div class="actions">
        <button type="button" id="btn-flag" disabled>★ Flag</button>
        <button type="button" id="btn-prev">← Prev</button>
        <button type="button" id="btn-next">Next →</button>
        <button type="button" id="btn-download" class="primary" disabled>Download</button>
        <label class="btn primary" id="lbl-upload">
          Upload / overwrite
          <input type="file" id="file-input" accept="image/png,image/*" disabled />
        </label>
        <button type="button" id="btn-done" disabled>Mark done</button>
        <button type="button" id="btn-undone" disabled>Mark todo</button>
      </div>
    </div>
    <div class="preview-wrap" id="preview-wrap">
      <img id="preview" alt="" style="display:none" />
      <div class="empty" id="preview-empty">Pick a file from the list</div>
    </div>
    <div class="dropzone" id="dropzone">
      Drop an English PNG here to <strong>overwrite</strong> the selected file<br />
      <span style="font-size:0.85rem">Same canvas size recommended · Voices are never touched</span>
    </div>
  </section>
</main>
<div class="toast" id="toast"></div>
<script>
const state = {
  images: [],
  filtered: [],
  index: 0,
  bust: Date.now(),
};

const $ = (id) => document.getElementById(id);

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function imgUrl(path) {
  return "/api/image?path=" + encodeURIComponent(path) + "&t=" + state.bust;
}

function applyFilter() {
  const q = $("search").value.trim().toLowerCase();
  const f = $("filter").value;
  const cat = $("category").value;
  state.filtered = state.images.filter((img) => {
    if (f === "todo" && img.done) return false;
    if (f === "done" && !img.done) return false;
    if (f === "flagged" && !img.flagged) return false;
    if (cat && img.category !== cat) return false;
    if (!q) return true;
    const hay = (img.path + " " + img.english_hint + " " + img.folder).toLowerCase();
    return hay.includes(q);
  });
  renderList();
  if (state.filtered.length === 0) {
    clearDetail();
    return;
  }
  if (state.index >= state.filtered.length) state.index = 0;
  selectIndex(state.index, false);
}

function renderList() {
  const list = $("list");
  if (!state.filtered.length) {
    list.innerHTML = '<div class="empty">No images match</div>';
    return;
  }
  list.innerHTML = "";
  state.filtered.forEach((img, i) => {
    const div = document.createElement("div");
    div.className = "item"
      + (img.done ? " done" : "")
      + (img.flagged ? " flagged" : "")
      + (i === state.index ? " active" : "");
    div.dataset.index = i;
    div.innerHTML =
      '<button type="button" class="star' + (img.flagged ? " on" : "") + '" title="Flag for replacement">' +
      (img.flagged ? "★" : "☆") + "</button>" +
      '<img class="thumb" loading="lazy" src="' + imgUrl(img.path) + '" alt="" />' +
      '<div class="meta">' +
      '<div class="name" title="' + escapeHtml(img.path) + '">' + escapeHtml(img.name) + "</div>" +
      '<div class="sub">' + escapeHtml(img.folder) +
      (img.english_hint ? " · " + escapeHtml(img.english_hint.slice(0, 60)) : "") +
      "</div></div>";
    div.addEventListener("click", () => selectIndex(i, true));
    div.querySelector(".star").addEventListener("click", (e) => {
      e.stopPropagation();
      setFlag(img, !img.flagged);
    });
    list.appendChild(div);
  });
  const active = list.querySelector(".item.active");
  if (active) active.scrollIntoView({ block: "nearest" });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function clearDetail() {
  $("path").textContent = "No selection";
  $("hint").textContent = "";
  $("preview").style.display = "none";
  $("preview-empty").style.display = "block";
  $("btn-download").disabled = true;
  $("file-input").disabled = true;
  $("btn-flag").disabled = true;
  $("btn-flag").textContent = "★ Flag";
  $("btn-flag").classList.remove("flag-on");
  $("btn-done").disabled = true;
  $("btn-undone").disabled = true;
}

function selectIndex(i, scrollList) {
  if (!state.filtered.length) return;
  state.index = Math.max(0, Math.min(i, state.filtered.length - 1));
  const img = state.filtered[state.index];
  $("path").textContent = img.path;
  const bits = [
    img.width && img.height ? img.width + "×" + img.height : null,
    img.category || null,
    img.priority || null,
    img.english_hint || null,
  ].filter(Boolean);
  $("hint").textContent = bits.join(" · ");
  const prev = $("preview");
  prev.src = imgUrl(img.path);
  prev.style.display = "block";
  $("preview-empty").style.display = "none";
  $("btn-download").disabled = false;
  $("file-input").disabled = false;
  $("btn-flag").disabled = false;
  $("btn-flag").textContent = img.flagged ? "★ Flagged" : "★ Flag";
  $("btn-flag").classList.toggle("flag-on", !!img.flagged);
  $("btn-done").disabled = false;
  $("btn-undone").disabled = false;
  $("btn-done").textContent = img.done ? "Done ✓" : "Mark done";
  renderList();
  if (scrollList) {
    const active = $("list").querySelector(".item.active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }
  updateStats();
}

function updateStats() {
  const total = state.images.length;
  const done = state.images.filter((i) => i.done).length;
  const flagged = state.images.filter((i) => i.flagged).length;
  const shown = state.filtered.length;
  const cur = state.filtered.length ? state.index + 1 : 0;
  $("stats").innerHTML =
    '<strong class="flagged">' + flagged + "</strong> flagged · " +
    done + "/" + total + " done · showing " + shown +
    (cur ? " · #" + cur : "");
}

async function loadImages() {
  const res = await fetch("/api/list");
  const data = await res.json();
  state.images = data.images || [];
  state.bust = Date.now();
  const cats = [...new Set(state.images.map((i) => i.category).filter(Boolean))].sort();
  const sel = $("category");
  const cur = sel.value;
  sel.innerHTML = '<option value="">All categories</option>';
  cats.forEach((c) => {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    sel.appendChild(o);
  });
  if (cats.includes(cur)) sel.value = cur;
  applyFilter();
  updateStats();
}

async function setFlag(img, flagged) {
  if (!img) return;
  const res = await fetch("/api/status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: img.path, flagged }),
  });
  if (!res.ok) {
    toast("Failed to update flag");
    return;
  }
  img.flagged = flagged;
  applyFilter();
  toast(flagged ? "Flagged for replacement" : "Flag cleared");
}

async function setDone(done) {
  const img = state.filtered[state.index];
  if (!img) return;
  const res = await fetch("/api/status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: img.path, done }),
  });
  if (!res.ok) {
    toast("Failed to update status");
    return;
  }
  img.done = done;
  const master = state.images.find((i) => i.path === img.path);
  if (master) master.done = done;
  applyFilter();
  toast(done ? "Marked done" : "Marked todo");
}

async function uploadFile(file) {
  const img = state.filtered[state.index];
  if (!img || !file) return;
  const fd = new FormData();
  fd.append("path", img.path);
  fd.append("file", file, file.name || "upload.png");
  const res = await fetch("/api/upload", { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    toast(data.error || "Upload failed");
    return;
  }
  state.bust = Date.now();
  img.done = true;
  const master = state.images.find((i) => i.path === img.path);
  if (master) {
    master.done = true;
    master.size = data.size || master.size;
    master.width = data.width || master.width;
    master.height = data.height || master.height;
    master.mtime = data.mtime || master.mtime;
  }
  applyFilter();
  selectIndex(state.index, false);
  toast("Overwritten · marked done");
}

function downloadCurrent() {
  const img = state.filtered[state.index];
  if (!img) return;
  const a = document.createElement("a");
  a.href = imgUrl(img.path);
  a.download = img.name;
  a.click();
}

$("search").addEventListener("input", applyFilter);
$("filter").addEventListener("change", applyFilter);
$("category").addEventListener("change", applyFilter);
$("btn-refresh").addEventListener("click", loadImages);
$("btn-prev").addEventListener("click", () => selectIndex(state.index - 1, true));
$("btn-next").addEventListener("click", () => selectIndex(state.index + 1, true));
$("btn-download").addEventListener("click", downloadCurrent);
$("btn-flag").addEventListener("click", () => {
  const img = state.filtered[state.index];
  if (img) setFlag(img, !img.flagged);
});
$("btn-done").addEventListener("click", () => setDone(true));
$("btn-undone").addEventListener("click", () => setDone(false));
$("file-input").addEventListener("change", (e) => {
  const f = e.target.files && e.target.files[0];
  if (f) uploadFile(f);
  e.target.value = "";
});

const dz = $("dropzone");
["dragenter", "dragover"].forEach((ev) => {
  dz.addEventListener(ev, (e) => {
    e.preventDefault();
    dz.classList.add("drag");
  });
});
["dragleave", "drop"].forEach((ev) => {
  dz.addEventListener(ev, (e) => {
    e.preventDefault();
    dz.classList.remove("drag");
  });
});
dz.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) uploadFile(f);
});

document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea, select")) return;
  if (e.key === "ArrowRight" || e.key === "j") {
    e.preventDefault();
    selectIndex(state.index + 1, true);
  } else if (e.key === "ArrowLeft" || e.key === "k") {
    e.preventDefault();
    selectIndex(state.index - 1, true);
  } else if (e.key === "f") {
    e.preventDefault();
    const img = state.filtered[state.index];
    if (img) setFlag(img, !img.flagged);
  } else if (e.key === "d") {
    e.preventDefault();
    setDone(true);
  } else if (e.key === "u") {
    e.preventDefault();
    setDone(false);
  } else if (e.key === "s" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    downloadCurrent();
  }
});

loadImages();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ImageWorkspace/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str, *, headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send(200, HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/list":
            images = list_images()
            self._json(
                200,
                {
                    "workspace": str(WORKSPACE.relative_to(ROOT)),
                    "count": len(images),
                    "done": sum(1 for img in images if img["done"]),
                    "images": images,
                },
            )
            return

        if path == "/api/image":
            rel = (qs.get("path") or [""])[0]
            target = safe_rel_path(rel)
            if target is None or not target.is_file():
                self._json(404, {"error": "not found"})
                return
            data = target.read_bytes()
            ctype = mimetypes.guess_type(target.name)[0] or "image/png"
            self._send(200, data, ctype)
            return

        self._json(404, {"error": "unknown path"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            rel = payload.get("path", "")
            target = safe_rel_path(rel)
            if target is None or not target.is_file():
                self._json(404, {"error": "not found"})
                return
            status = load_status()
            entry = status.get(rel, {})
            if "done" in payload:
                entry["done"] = bool(payload.get("done"))
            if "flagged" in payload:
                entry["flagged"] = bool(payload.get("flagged"))
            if "note" in payload:
                entry["note"] = str(payload.get("note") or "")
            status[rel] = entry
            save_status(status)
            self._json(
                200,
                {
                    "ok": True,
                    "path": rel,
                    "done": bool(entry.get("done")),
                    "flagged": bool(entry.get("flagged")),
                },
            )
            return

        if path == "/api/upload":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._json(400, {"error": "expected multipart/form-data"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 80 * 1024 * 1024:
                self._json(400, {"error": "invalid content length"})
                return
            body = self.rfile.read(length)
            try:
                parts = parse_multipart(body, content_type)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return

            rel_blob = parts.get("path", (None, b""))[1]
            rel = rel_blob.decode("utf-8", "replace")
            target = safe_rel_path(rel)
            if target is None:
                self._json(400, {"error": "invalid path"})
                return
            if not target.parent.exists():
                self._json(404, {"error": "parent folder missing"})
                return

            filename, data = parts.get("file", (None, b""))
            if not data:
                self._json(400, {"error": "missing file"})
                return

            out_data = data
            try:
                from PIL import Image

                image = Image.open(BytesIO(data)).convert("RGBA")
                width, height = image.size
                buf = BytesIO()
                image.save(buf, format="PNG")
                out_data = buf.getvalue()
            except Exception as exc:
                self._json(400, {"error": f"not a readable image: {exc}"})
                return

            target.write_bytes(out_data)

            status = load_status()
            entry = status.get(rel, {})
            entry["done"] = True
            entry.setdefault("note", "")
            status[rel] = entry
            save_status(status)

            self._json(
                200,
                {
                    "ok": True,
                    "path": rel,
                    "filename": filename or target.name,
                    "size": len(out_data),
                    "width": width,
                    "height": height,
                    "mtime": int(target.stat().st_mtime),
                },
            )
            return

        self._json(404, {"error": "unknown path"})


def main() -> None:
    global WORKSPACE, MANIFEST_PATH, STATUS_PATH

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    WORKSPACE = args.workspace.resolve()
    MANIFEST_PATH = WORKSPACE / "manifest.csv"
    STATUS_PATH = WORKSPACE / ".workspace_status.json"

    if not WORKSPACE.exists():
        raise SystemExit(
            f"Missing {WORKSPACE}\n"
            "Run: python3 tools/export_translate_workspace.py export"
        )

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Image workspace: {WORKSPACE}")
    print(f"Open http://{args.host}:{args.port}/")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
