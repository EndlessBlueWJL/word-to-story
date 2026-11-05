"""Import the user's numbered PDF locally; never add the PDF or full CSV to Git."""
import csv
import re
from pathlib import Path


def parse_numbered_text(text):
    text = re.sub(r"([A-Za-z]-)\n(?=[a-z])", r"\1", text)
    pairs = [(int(n), w.strip().lower().replace("’", "'")) for n, w in
             re.findall(r"(?m)^(\d+)[ \t]*\n?([A-Za-z][A-Za-z'’ -]*)[ \t]*$", text)]
    if not pairs or [n for n, _ in pairs] != list(range(1, len(pairs) + 1)):
        raise ValueError("PDF numbering could not be extracted continuously; inspect the source instead of guessing")
    # Source footer supplies a useful independent total for this book.
    total = re.search(r"共\s*(\d+)\s*词", text)
    if total and len(pairs) != int(total[1]):
        raise ValueError(f"Extracted {len(pairs)} rows; source says {total[1]}")
    return pairs


def extract(pdf, destination):
    import fitz
    from .workflow import load_vocab
    with fitz.open(pdf) as document:
        text = "\n".join(page.get_text() for page in document)
    pairs = parse_numbered_text(text)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Output exists; choose a new CSV path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["number", "word", "meaning"])
        writer.writerows((n, w, "") for n, w in pairs)
    load_vocab(temporary)
    temporary.replace(destination)
    return {"csv": str(destination), "rows": len(pairs), "meanings": "not present in source; agent supplies context meanings"}
