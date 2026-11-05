import argparse
import json
import sys
from pathlib import Path

from . import workflow
from .common import ROOT, default_data, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description="35 words → agent-authored reading → complete portrait cards")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "prepare", "build", "status", "backup", "restore", "demo"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--data", type=Path, default=default_data())
        if name == "init":
            cmd.add_argument("--vocab", type=Path, required=True)
            cmd.add_argument("--start", type=int, default=332)
        if name == "prepare":
            cmd.add_argument("--start", type=int, help="Explicit range = review mode; never advances")
            cmd.add_argument("--date")
        if name == "build":
            cmd.add_argument("--request", type=Path, required=True)
            cmd.add_argument("--content", type=Path, required=True)
            cmd.add_argument("--advance", action="store_true")
        if name == "backup":
            cmd.add_argument("--out", type=Path, required=True)
        if name == "restore":
            cmd.add_argument("--archive", type=Path, required=True)
    check = sub.add_parser("validate")
    check.add_argument("--request", type=Path, required=True)
    check.add_argument("--content", type=Path, required=True)
    sub.add_parser("fonts")
    pdf = sub.add_parser("import-pdf")
    pdf.add_argument("--pdf", type=Path, required=True)
    pdf.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "import-pdf":
        from .extract import extract
        result = extract(args.pdf, args.out)
    elif args.command == "fonts":
        from .fonts import install
        result = {"fonts": install()}
    elif args.command == "validate":
        from .validation import validate
        result = validate(read_json(args.request), read_json(args.content))
    elif args.command == "init":
        result = workflow.init(args.data, args.vocab, args.start)
    elif args.command == "prepare":
        result = workflow.prepare(args.data, args.start, args.date)
    elif args.command == "build":
        result = workflow.build(args.data, args.request, args.content, args.advance)
    elif args.command == "status":
        state = read_json(args.data / "state.json")
        result = {"next_number": state["next_number"], "completed_batches": len(state["history"]), "data": str(args.data.resolve())}
    elif args.command == "backup":
        result = workflow.backup(args.data, args.out)
    elif args.command == "restore":
        result = workflow.restore(args.archive, args.data)
    elif args.command == "demo":
        # Isolated demo state: never touches this user's formal learning cursor.
        import uuid
        data = args.data / "demos" / uuid.uuid4().hex[:8]
        workflow.init(data, ROOT / "examples" / "vocabulary.csv", 332)
        prepared = workflow.prepare(data, start=332)
        content = read_json(ROOT / "examples" / "content.json")
        content["batch_id"] = read_json(prepared["request"])["batch_id"]
        write_json(prepared["content"], content)
        result = workflow.build(data, prepared["request"], prepared["content"])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, FileNotFoundError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
