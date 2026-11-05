import re
from pathlib import Path

from PIL import Image, ImageDraw

from .fonts import font

W, H = 1080, 1920
BG, INK, MUTED, LINE = "#F7F5F0", "#24322F", "#52625A", "#DEDCD3"
PALETTE = [("#B35E43", "#FBECE4"), ("#24766C", "#E7F3ED"),
           ("#496BA0", "#EAF0FA"), ("#8C668D", "#F3EBF4")]


def text(draw, xy, value, size, color=INK, bold=False, face="ui"):
    draw.text(xy, value, font=font(face, size, bold), fill=color, anchor="lt")


def wrapped(draw, value, x, y, width, size, leading, color=INK, bold=False):
    ft = font("ui", size, bold)
    tokens = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+|\s+|.", value)
    lines, line = [], ""
    for token in tokens:
        if draw.textlength(token, font=ft) > width:
            raise ValueError(f"Text token is too wide: {token}")
        if line and draw.textlength(line + token, font=ft) > width:
            if token in "，。；：？！、）】》”’.,!?":
                tail = line[-1:]
                lines.append(line[:-1].rstrip())
                line = tail + token
            else:
                lines.append(line.rstrip())
                line = token.lstrip()
        else:
            line += token
    if line.strip():
        lines.append(line.rstrip())
    for line in lines:
        text(draw, (x, y), line, size, color, bold)
        y += leading
    return y


def rich(draw, paragraph, x, y, width, targets, vocab, accent, tint, masked=False):
    # Keep punctuation with each word; exact headwords receive original numbers.
    x0 = x
    paragraph = paragraph.replace("’", "'")
    pattern = r"(?<![A-Za-z])(?:" + "|".join(re.escape(w) for w in sorted(targets, key=len, reverse=True)) + r")(?![A-Za-z])"
    units, last = [], 0
    for match in re.finditer(pattern, paragraph, re.I):
        units.extend((t, False) for t in re.findall(r"\s+|\S+", paragraph[last:match.start()]))
        units.append((match[0], True))
        last = match.end()
    units.extend((t, False) for t in re.findall(r"\s+|\S+", paragraph[last:]))
    for token, is_target in units:
        if token.isspace():
            if x != x0:
                x += draw.textlength(" ", font=font("body", 42))
            continue
        segments, total = [], 0
        # Apostrophes and hyphens belong to a headword (including o'clock).
        for part in [token]:
            key = part.lower().replace("’", "'")
            target = is_target
            ft = font("body", 42, target)
            display = "______" if target and masked else part
            sw = draw.textlength(display, font=ft)
            number = str(vocab[key]["number"]) if target else ""
            nw = draw.textlength(number, font=font("ui", 17, True)) + 5 if target else 0
            segments.append((display, ft, sw, number, nw))
            total += sw + nw
        if total > width:
            raise ValueError(f"Body token too wide: {token}")
        if x > x0 and x + total > x0 + width:
            x, y = x0, y + 56
        for part, ft, sw, number, nw in segments:
            if number:
                draw.rounded_rectangle((x - 2, y - 1, x + sw + 2, y + 46), radius=6, fill=tint)
                if masked:
                    draw.line((x, y + 43, x + sw, y + 43), fill=accent, width=2)
                else:
                    draw.text((x, y), part, font=ft, fill=accent, anchor="lt")
                text(draw, (x + sw + 2, y), number, 17, accent, True)
            else:
                draw.text((x, y), part, font=ft, fill=INK, anchor="lt")
            x += sw + nw
    return y + 56


def render(request, content, destination):
    destination = Path(destination)
    vocab = {r["word"].lower(): r for r in request["vocabulary"]}
    reports = []
    for s in content["stories"]:
        accent, tint = PALETTE[(s["id"] - 1) % 4]
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        td = ImageDraw.Draw(Image.new("RGB", (W, H), BG))
        d.rectangle((0, 0, W, 9), fill=accent)
        label = f"① 朗读背词 · {request['start']}–{request['end']}"
        text(d, (32, 28), label, 24, MUTED)
        right = f"{s['id']:02d}/{len(content['stories']):02d} · {s['topic']} · {len(s['words'])}词"
        if d.textlength(right, font=font("ui", 24, True)) > 570:
            raise ValueError("Shorten the topic label")
        text(d, (1048 - d.textlength(right, font=font("ui", 24, True)), 28), right, 24, accent, True)
        for value, size in ((s["title"], 46), (s["en_title"], 28)):
            if d.textlength(value, font=font("ui", size, size == 46)) > 1014:
                raise ValueError("Shorten the story title")
        text(d, (32, 74), s["title"], 46, bold=True)
        text(d, (33, 133), s["en_title"], 28, MUTED)

        def body(draw):
            yy = 190
            for p in s["paragraphs"]:
                yy = rich(draw, p, 46, yy, 988, set(s["words"]), vocab, accent, tint) + 9
            return yy + 8

        body_end = body(td)
        d.rounded_rectangle((30, 172, 1050, body_end), radius=20, fill="#FFFEFA", outline="#E5E2D8", width=2)
        body(d)
        y = body_end + 15
        text(d, (33, y), "大意", 27, accent, True)
        y = wrapped(d, s["gist"], 104, y, 942, 26, 36, MUTED) + 13
        d.line((33, y, 1047, y), fill=LINE, width=2)
        y += 16
        text(d, (33, y), "目标词＋背诵词块", 29, accent, True)
        text(d, (799, y + 4), "词块均出自正文", 23, MUTED)
        y += 44
        word_top = y
        for i, word in enumerate(sorted(s["words"], key=lambda w: vocab[w]["number"])):
            x = 33 + (i % 2) * 519
            yy = y + (i // 2) * 83
            detail = content["details"][word]
            text(d, (x, yy + 5), str(vocab[word]["number"]), 21, MUTED)
            text(d, (x + 48, yy), word, 33, accent, True)
            gx = x + 48 + d.textlength(word, font=font("ui", 33, True)) + 15
            if gx + d.textlength(detail["meaning"], font=font("ui", 29)) > x + 495:
                raise ValueError(f"Shorten the context meaning for {word}; keep large type")
            text(d, (gx, yy + 3), detail["meaning"], 29)
            if d.textlength(detail["chunk"], font=font("ui", 29)) > 447:
                raise ValueError(f"Choose a shorter verbatim chunk for {word}")
            text(d, (x + 48, yy + 44), detail["chunk"], 29, MUTED)
        y += ((len(s["words"]) + 1) // 2) * 83 + 10
        note = s["grammar"][0]

        def grammar(draw, yy):
            yy = wrapped(draw, note["label"], 45, yy + 12, 990, 28, 39, accent, True)
            yy = wrapped(draw, note["example"], 45, yy + 3, 990, 31, 41)
            return wrapped(draw, note["explanation"], 45, yy + 2, 990, 27, 37, MUTED) + 12

        end = grammar(td, y)
        d.rounded_rectangle((30, y, 1050, end), radius=19, fill=tint)
        grammar(d, y)
        y = wrapped(d, "开口：" + s["retell"] + "。看词栏复述，再补全这句：", 33, end + 14, 1014, 26, 36, MUTED)
        y = wrapped(d, s["rewrite"], 33, y + 2, 1014, 30, 41)
        if y >= 1854:
            raise ValueError(f"Story {s['id']} overflows ({y}px). Shorten content or regroup into at most 4 stories; never shrink or split a story")
        d.line((33, 1863, 1047, 1863), fill=LINE, width=2)
        text(d, (33, 1883), "读顺 → 回忆 → 复述 · 背词优先", 23, MUTED)
        text(d, (898, 1883), "9:16 竖版", 23, accent, True)
        name = f"story-{s['id']:02d}.png"
        im.save(destination / name, optimize=True)
        reports.append({"file": name, "size": [W, H], "content_bottom": y,
                        "body_end": body_end, "word_top": word_top})
    return reports
