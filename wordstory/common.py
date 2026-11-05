import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
RULES_VERSION = "vocabulary-first-speaking-v1"
DELIVERY_VERSION = "mobile-images-paired-v2"


def today():
    try:
        return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except ZoneInfoNotFoundError:
        from datetime import timedelta, timezone
        return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def default_data():
    if os.environ.get("WORDSTORY_DATA_DIR"):
        return Path(os.environ["WORDSTORY_DATA_DIR"]).expanduser().resolve()
    if os.name == "nt":
        return Path("D:/AI application/codex data/英语单词故事/word-to-story-data")
    return ROOT / "data"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()
