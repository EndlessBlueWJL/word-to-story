"""Check the actual Git publication surface; report paths, never secret values."""
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main():
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--worktree", action="store_true")
    args = p.parse_args()
    listing = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z") if args.staged else git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    names = sorted(set(n.decode("utf-8") for n in listing.split(b"\0") if n))
    failures = []
    secret = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{24,}|sk-[A-Za-z0-9_-]{25,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)")
    for name in names:
        path = Path(name)
        if any(part in ("data", "runs", "private", "__pycache__", ".venv") for part in path.parts) or path.suffix.lower() in (".pdf", ".zip", ".ttf", ".ttc") or path.name.startswith(".env"):
            failures.append((name, "private/runtime file"))
        if path.suffix.lower() == ".csv" and name != "examples/vocabulary.csv":
            failures.append((name, "only the 35-word public example CSV is allowed"))
        if path.suffix.lower() in (".png", ".jpg", ".jpeg") and name != "docs/preview.png":
            failures.append((name, "unapproved image"))
        content = git("show", ":" + name) if args.staged else (ROOT / name).read_bytes()
        if secret.search(content):
            failures.append((name, "credential-like content"))
        if re.search(rb"[A-Za-z]:[\\/]+Users[\\/]+(?!Public|Default)[A-Za-z0-9_.-]+", content):
            failures.append((name, "local personal path"))
        if name == "examples/vocabulary.csv" and len(content.decode("utf-8-sig").splitlines()) != 36:
            failures.append((name, "example must contain exactly 35 rows"))
    for name, reason in failures:
        print(f"BLOCKED {name}: {reason}")
    if failures:
        raise SystemExit(1)
    print(f"Public-file check passed: {len(names)} files")


if __name__ == "__main__":
    main()
