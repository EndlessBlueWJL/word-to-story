import hashlib
import json
import urllib.request
from functools import lru_cache

from PIL import ImageFont

from .common import ROOT

FONT_DIR = ROOT / "assets" / "fonts"


def install():
    manifest = json.loads((FONT_DIR / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest:
        path = FONT_DIR / entry["file"]
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]:
            continue
        req = urllib.request.Request(entry["url"], headers={"User-Agent": "word-to-story/0.1"})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Font checksum mismatch: {entry['file']}")
        temp = path.with_suffix(".part")
        temp.write_bytes(data)
        temp.replace(path)
    return [entry["file"] for entry in manifest]


@lru_cache(maxsize=100)
def font(face, size, bold=False):
    name = "NotoSerif.ttf" if face == "body" else "NotoSansSC.ttf"
    path = FONT_DIR / name
    if not path.exists():
        raise ValueError("Fonts missing: run python -m wordstory fonts")
    ft = ImageFont.truetype(str(path), size)
    axes = ft.get_variation_axes()
    values = [(700 if bold else 400) if b"weight" in a["name"].lower() else a["default"] for a in axes]
    ft.set_variation_by_axes(values)
    return ft
