import csv
import json
import os
import random
import re
import shutil
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

from .common import ROOT, RULES_VERSION, canonical_hash, digest, read_json, today, write_json
from .validation import contains, seal_request, validate, validate_request


@contextmanager
def locked(data):
    data = Path(data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    lock = data / ".write-lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("Another write is active. If a process crashed, verify it has stopped before removing .write-lock") from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def load_vocab(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not {"number", "word"}.issubset(rows[0]):
        raise ValueError("CSV requires number,word columns; meaning is optional")
    result = []
    for row in rows:
        word = row["word"].strip().lower().replace("’", "'")
        if not re.fullmatch(r"[a-z]+(?:[-'][a-z]+)*(?: [a-z]+(?:[-'][a-z]+)*)*", word):
            raise ValueError(f"Unresolved headword spelling: {word!r}")
        result.append({"number": int(row["number"]), "word": word, "meaning": row.get("meaning", "").strip()})
    numbers = [r["number"] for r in result]
    if numbers != sorted(set(numbers)) or numbers != list(range(numbers[0], numbers[-1] + 1)):
        raise ValueError("CSV numbers must be unique, consecutive, and already in source order")
    return result


def init(data, vocabulary, start=332):
    data = Path(data).resolve()
    rows = load_vocab(vocabulary)
    if start not in {r["number"] for r in rows}:
        raise ValueError("Start number is not in this vocabulary")
    with locked(data):
        if (data / "state.json").exists():
            raise ValueError("State already exists; init never resets learning progress")
        with (data / "vocabulary.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["number", "word", "meaning"])
            writer.writeheader()
            writer.writerows(rows)
        state = {"version": 1, "rules_version": RULES_VERSION, "next_number": start,
                 "batch_size": 35, "vocabulary_sha256": digest(data / "vocabulary.csv"), "history": []}
        write_json(data / "state.json", state)
    return {"data": str(data), "vocabulary_count": len(rows), "next_number": start}


def prepare(data, start=None, date=None):
    data = Path(data).resolve()
    with locked(data):
        state = read_json(data / "state.json")
        if digest(data / "vocabulary.csv") != state["vocabulary_sha256"]:
            raise ValueError("Vocabulary has changed; resolve the source before continuing")
        first = state["next_number"] if start is None else start
        rows = [r for r in load_vocab(data / "vocabulary.csv") if first <= r["number"] < first + 35]
        if len(rows) != 35:
            raise ValueError(f"Only {len(rows)} words remain at {first}; do not skip, wrap, or silently make a smaller batch")
        date = date or today()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("Date must be YYYY-MM-DD")
        batch = f"{date}_{first:04d}-{first+34:04d}_{uuid.uuid4().hex[:8]}"
        request = {"batch_id": batch, "rules_version": RULES_VERSION, "date": date,
                   "mode": "next" if start is None else "review", "start": first, "end": first + 34,
                   "expected_next": state["next_number"], "vocabulary_sha256": state["vocabulary_sha256"],
                   "vocabulary": rows}
        request["request_hash"] = seal_request(request)
        validate_request(request)
        run = data / "runs" / batch
        write_json(run / "request.json", request)
        draft = {"batch_id": batch, "rules_version": RULES_VERSION, "stories": [], "details": {},
                 "editorial_review": {k: False for k in ("simple_other_words", "natural_speech", "ielts_topics", "exam_grammar", "meaning_and_collocations")}}
        draft["editorial_review"]["notes"] = "Complete an actual language review; do not change these flags just to pass."
        write_json(run / "content.json", draft)
    return {"request": str(run / "request.json"), "content": str(run / "content.json"),
            "range": [first, first + 34], "progress_advanced": False}


def export_text(request, content, output):
    vocab = {r["word"]: r for r in request["vocabulary"]}
    md = [f"# 第{request['start']}—{request['end']}词 · 背词＋口语", "",
          "读顺正文 → 看中文回忆英文 → 看词块复述 → 换成自己的情况。", ""]
    practice = ["# 遮词回忆与35词抽查", "", "先读熟正文，再看中文回忆英文、复述场景。", ""]
    for s in content["stories"]:
        md += [f"## {s['id']}. {s['title']} / {s['en_title']}", "", f"{s['topic']} · {s['kind']}", ""]
        practice += [f"## {s['id']}. {s['title']}", ""]
        pattern = r"(?<![A-Za-z])(" + "|".join(re.escape(w) for w in sorted(s["words"], key=len, reverse=True)) + r")(?![A-Za-z])"
        for p in s["paragraphs"]:
            p = p.replace("’", "'")
            md += [re.sub(pattern, lambda m: f"**{m[0]}**[{vocab[m[0].lower()]['number']}]", p, flags=re.I), ""]
            practice += [re.sub(pattern, lambda m: f"______[{vocab[m[0].lower()]['number']}]", p, flags=re.I), ""]
        md += ["中文大意：" + s["gist"], "", "| 编号 | 单词 | 本文用义 | 正文词块 |", "|---|---|---|---|"]
        for w in sorted(s["words"], key=lambda w: vocab[w]["number"]):
            detail = content["details"][w]
            md.append(f"| {vocab[w]['number']} | {w} | {detail['meaning']} | {detail['chunk']} |")
        note = s["grammar"][0]
        md += ["", "句式：" + note["label"], "", note["example"], "", note["explanation"], ""]
        for lines in (md, practice):
            lines += ["复述提示：" + s["retell"], "", "换成自己的话：" + s["rewrite"], ""]
    rows = list(request["vocabulary"])
    random.Random(request["batch_id"]).shuffle(rows)
    practice += ["## 看中文说英文，再说出正文词块", ""]
    for i, row in enumerate(rows, 1):
        practice.append(f"{i}. {content['details'][row['word']]['meaning']}（{row['number']}）：________")
    practice += ["", "## 答案", ""]
    for i, row in enumerate(rows, 1):
        practice.append(f"{i}. {row['word']} — {content['details'][row['word']]['chunk']}")
    (output / "reading.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (output / "practice.md").write_text("\n".join(practice) + "\n", encoding="utf-8")
    with (output / "vocabulary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["number", "word", "context_meaning", "chunk"])
        for row in request["vocabulary"]:
            detail = content["details"][row["word"]]
            writer.writerow([row["number"], row["word"], detail["meaning"], detail["chunk"]])


def verify_manifest(output):
    output = Path(output)
    manifest = read_json(output / "manifest.json")
    if not manifest.get("files"):
        raise ValueError("Empty output manifest")
    for name, expected in manifest["files"].items():
        if Path(name).name != name or digest(output / name) != expected:
            raise ValueError(f"Output changed or missing: {name}")
    return manifest


def build(data, request_path, content_path, advance=False):
    from .mobile import render_package, verify_delivery
    data = Path(data).resolve()
    request, content = read_json(request_path), read_json(content_path)
    report = validate(request, content)
    fingerprint = canonical_hash(content)
    engine_hash = canonical_hash({p: digest(ROOT / p) for p in (
        "wordstory/render.py", "wordstory/fonts.py", "wordstory/validation.py",
        "wordstory/workflow.py", "wordstory/mobile.py", "assets/fonts/manifest.json", "docs/CONTENT_RULES.md")})
    # All files stay in this profile, even if the content was uploaded elsewhere.
    run = data / "runs" / request["batch_id"]
    if Path(request["batch_id"]).name != request["batch_id"] or ":" in request["batch_id"]:
        raise ValueError("Invalid batch id")
    final = run / ("build-" + fingerprint[:8] + "-" + engine_hash[:6])
    with locked(data):
        state = read_json(data / "state.json")
        if state["vocabulary_sha256"] != request["vocabulary_sha256"] or digest(data / "vocabulary.csv") != request["vocabulary_sha256"]:
            raise ValueError("Request does not match this profile's source vocabulary")
        source = [r for r in load_vocab(data / "vocabulary.csv") if request["start"] <= r["number"] <= request["end"]]
        if source != request["vocabulary"]:
            raise ValueError("Request words differ from the source vocabulary")
        previous = next((h for h in state["history"] if h["batch_id"] == request["batch_id"]), None)
        if advance and request["mode"] != "next":
            raise ValueError("Review/rewrite requests never advance progress")
        if advance and previous and previous["content_hash"] != fingerprint:
            raise ValueError("This batch already advanced; save a rewrite without --advance")
        if advance and not previous and (state["next_number"] != request["expected_next"] or request["start"] != state["next_number"]):
            raise ValueError("Stale request: progress changed; prepare a new batch")
        if final.exists():
            manifest = verify_manifest(final)
            delivery = verify_delivery(final, request)
            if manifest["content_hash"] != fingerprint or manifest["request_hash"] != request["request_hash"] or manifest["engine_hash"] != engine_hash:
                raise ValueError("Output identity mismatch")
        else:
            stage = run / (".pending-" + uuid.uuid4().hex[:8])
            stage.mkdir(parents=True)
            write_json(stage / "request.json", request)
            write_json(stage / "content.json", content)
            delivery = render_package(request, content, stage)
            verify_delivery(stage, request)
            report["images"] = [card for group in delivery["groups"] for card in group["images"]]
            export_text(request, content, stage)
            write_json(stage / "validation.json", report)
            files = {p.name: digest(p) for p in sorted(stage.iterdir()) if p.is_file()}
            manifest = {"batch_id": request["batch_id"], "request_hash": request["request_hash"],
                        "content_hash": fingerprint, "engine_hash": engine_hash, "files": files}
            write_json(stage / "manifest.json", manifest)
            with zipfile.ZipFile(stage / "learning-pack.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for p in sorted(stage.iterdir()):
                    if p.is_file() and p.name != "learning-pack.zip":
                        archive.write(p, p.name)
            # Include the downloadable ZIP in the final on-disk integrity receipt.
            manifest["files"]["learning-pack.zip"] = digest(stage / "learning-pack.zip")
            write_json(stage / "manifest.json", manifest)
            stage.rename(final)
            verify_manifest(final)
            verify_delivery(final, request)
        changed = False
        if advance and not previous:
            state["next_number"] = request["end"] + 1
            state["history"].append({"batch_id": request["batch_id"], "start": request["start"], "end": request["end"],
                                     "date": request["date"], "content_hash": fingerprint, "output": final.relative_to(data).as_posix()})
            write_json(data / "state.json", state)
            changed = True
    return {"output": str(final), "coverage": "35/35", "images": delivery["total_images"],
            "image_groups": [{"title": g["title"], "count": g["count"]} for g in delivery["groups"]],
            "delivery_manifest": str(final / "delivery.json"),
            "progress_advanced": changed, "next_number": state["next_number"]}


def backup(data, destination):
    data, destination = Path(data).resolve(), Path(destination).resolve()
    if destination.is_relative_to(data):
        raise ValueError("Save the backup outside the data directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError("Backup exists; choose a new filename")
    with locked(data):
        read_json(data / "state.json")
        temp = destination.with_suffix(destination.suffix + ".part")
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(data.rglob("*")):
                if path.is_file() and not path.is_symlink() and not any(p.startswith(".") for p in path.relative_to(data).parts):
                    archive.write(path, path.relative_to(data).as_posix())
        temp.replace(destination)
    return {"private_backup": str(destination), "sha256": digest(destination)}


def restore(source, data):
    data = Path(data).resolve()
    if data.exists() and any(data.iterdir()):
        raise ValueError("Restore only into an empty/new directory; never overwrite progress")
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if sum(m.file_size for m in members) > 1024 * 1024 * 1024:
            raise ValueError("Backup is too large")
        names = {m.filename for m in members}
        if not {"state.json", "vocabulary.csv"}.issubset(names):
            raise ValueError("Not a word-to-story profile backup")
        for item in members:
            target = (data / item.filename).resolve()
            if "\\" in item.filename or ":" in item.filename or not target.is_relative_to(data) or item.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError("Unsafe archive path")
        state = json.loads(archive.read("state.json"))
        import hashlib
        if hashlib.sha256(archive.read("vocabulary.csv")).hexdigest() != state["vocabulary_sha256"]:
            raise ValueError("Backup vocabulary checksum mismatch")
        archive.extractall(data)
    load_vocab(data / "vocabulary.csv")
    return {"data": str(data), "next_number": state["next_number"]}
