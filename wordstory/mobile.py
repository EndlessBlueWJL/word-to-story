"""All learning material as ordered, mobile-sized portrait images."""
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw

from .common import DELIVERY_VERSION, read_json, write_json
from .fonts import font
from .render import BG, H, INK, LINE, MUTED, PALETTE, W, render, rich, text, wrapped

GROUPS = [
    ("reading", "① 朗读与背词", "先读顺故事/对话，记住高亮词和正文词块。"),
    ("cloze", "② 遮词回忆与复述", "按原编号补全空格，再看中文线索复述；与上一组逐篇对应。"),
    ("quiz", "③ 35词打乱抽查", "先看中文说英文、拼写和词块，做完后再向下看答案。"),
    ("answers", "④ 抽查答案与词块", "题号、顺序与上一组一致，用来对照检查。"),
]


def quiz_rows(request):
    rows = list(request["vocabulary"])
    random.Random(request["batch_id"]).shuffle(rows)
    return rows


def mask_text(value, targets):
    pattern = r"(?<![A-Za-z])(?:" + "|".join(re.escape(w) for w in sorted(targets, key=len, reverse=True)) + r")(?![A-Za-z])"
    return re.sub(pattern, "______", value.replace("’", "'"), flags=re.I)


def page_header(draw, request, group, title, subtitle, page, total, accent):
    draw.rectangle((0, 0, W, 9), fill=accent)
    text(draw, (33, 28), f"{group} · {request['start']}–{request['end']}", 24, MUTED)
    label = f"{page:02d}/{total:02d}"
    text(draw, (1048 - draw.textlength(label, font=font("ui", 24, True)), 28), label, 24, accent, True)
    if draw.textlength(title, font=font("ui", 46, True)) > 1014:
        raise ValueError("Shorten the mobile card title")
    text(draw, (33, 77), title, 46, bold=True)
    return wrapped(draw, subtitle, 33, 144, 1014, 32, 45, MUTED) + 25


def page_footer(draw, instruction, accent):
    draw.line((33, 1863, 1047, 1863), fill=LINE, width=2)
    text(draw, (33, 1883), instruction, 23, MUTED)
    text(draw, (898, 1883), "9:16 竖版", 23, accent, True)


def render_cloze(request, content, destination):
    vocab = {r["word"]: r for r in request["vocabulary"]}
    reports = []
    for story in content["stories"]:
        accent, tint = PALETTE[(story["id"] - 1) % 4]
        im = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(im)
        scratch = ImageDraw.Draw(Image.new("RGB", (W, H), BG))
        y0 = page_header(draw, request, "② 遮词回忆", story["title"],
                         "先补出空格中的词，再试着读完整段。", story["id"], len(content["stories"]), accent)

        def body(d):
            yy = y0 + 16
            for paragraph in story["paragraphs"]:
                yy = rich(d, paragraph, 46, yy, 988, set(story["words"]), vocab, accent, tint, masked=True) + 9
            return yy + 10

        end = body(scratch)
        draw.rounded_rectangle((30, y0, 1050, end), radius=20, fill="#FFFEFA", outline="#E5E2D8", width=2)
        body(draw)
        y = end + 22
        text(draw, (33, y), "中文提示 · 按原编号找回单词", 32, accent, True)
        y += 55
        for i, word in enumerate(sorted(story["words"], key=lambda w: vocab[w]["number"])):
            x, yy = 33 + i % 2 * 519, y + i // 2 * 66
            text(draw, (x, yy + 5), str(vocab[word]["number"]), 27, MUTED)
            meaning = content["details"][word]["meaning"]
            if draw.textlength(meaning, font=font("ui", 36)) > 425:
                raise ValueError(f"Shorten the cloze context meaning: {word}")
            text(draw, (x + 65, yy), meaning, 36)
        y += ((len(story["words"]) + 1) // 2) * 66 + 22
        y = wrapped(draw, "复述线索：" + story["retell"], 33, y, 1014, 34, 47)
        y = wrapped(draw, "再换成自己的情况：", 33, y + 15, 1014, 32, 44, accent, True)
        y = wrapped(draw, mask_text(story["rewrite"], story["words"]), 33, y + 5, 1014, 36, 48)
        if y >= 1854:
            raise ValueError(f"Cloze {story['id']} overflows: shorten the source content; never shrink or split")
        page_footer(draw, "先填词 → 读顺 → 看线索复述", accent)
        name = f"cloze-{story['id']:02d}.png"
        im.save(destination / name, optimize=True)
        reports.append({"file": name, "size": [W, H], "content_bottom": y, "story_id": story["id"]})
    return reports


def answer_cell(draw, row, detail, index, x, y, width, draw_it):
    # Measure and draw use the same fonts/widths; a word/chunk is never split between cards.
    f = draw if draw_it else ImageDraw.Draw(Image.new("RGB", (W, H), BG))
    text(f, (x, y + 9), f"{index:02d}", 27, "#24766C", True)
    if f.textlength(row["word"], font=font("ui", 42, True)) > width - 55:
        raise ValueError("Headword too wide for this answer column")
    text(f, (x + 55, y), row["word"], 42, "#24766C", True)
    yy = wrapped(f, f"{row['number']} · {detail['meaning']}", x, y + 58, width, 36, 47)
    return wrapped(f, detail["chunk"], x, yy + 4, width, 34, 44, MUTED) + 18


def plan_quiz(request, content):
    rows = quiz_rows(request)
    measure = ImageDraw.Draw(Image.new("RGB", (W, H), BG))
    columns = 1 if any(measure.textlength(r["word"], font=font("ui", 42, True)) > 431 for r in rows) else 2
    width = 1014 if columns == 1 else 486
    pages, current, y = [], [], 260
    for first in range(0, len(rows), columns):
        pair = rows[first:first + columns]
        height = max(164, *(answer_cell(measure, row, content["details"][row["word"]], first + j + 1,
                                       0, 0, width, False) for j, row in enumerate(pair)))
        if y + height > 1835 and current:
            pages.append(current)
            current, y = [], 260
        if y + height > 1835:
            raise ValueError("A complete quiz entry cannot fit at the required font size")
        current.append({"rows": pair, "first_index": first + 1, "height": height})
        y += height
    if current:
        pages.append(current)
    return pages, columns


def render_quiz(request, content, destination):
    pages, columns = plan_quiz(request, content)
    groups = {"quiz": [], "answers": []}
    width = 1014 if columns == 1 else 486
    for kind in ("quiz", "answers"):
        for page, blocks in enumerate(pages, 1):
            im = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(im)
            start = blocks[0]["first_index"]
            end = blocks[-1]["first_index"] + len(blocks[-1]["rows"]) - 1
            answer = kind == "answers"
            page_header(d, request, "④ 对照答案" if answer else "③ 单词抽查",
                        "答案与正文词块" if answer else "看中文，说英文",
                        f"第{start}—{end}题 · " + ("按同样题号核对，再读一遍词块。" if answer else "先说英文、拼写和词块，做完再看答案。"),
                        page, len(pages), "#24766C")
            y = 260
            for block in blocks:
                for j, row in enumerate(block["rows"]):
                    x = 33 + j * 528
                    index = block["first_index"] + j
                    detail = content["details"][row["word"]]
                    if answer:
                        answer_cell(d, row, detail, index, x, y, width, True)
                    else:
                        text(d, (x, y + 3), f"{index:02d} · 原编号{row['number']}", 27, "#24766C", True)
                        yy = wrapped(d, detail["meaning"], x, y + 48, width, 46, 59)
                        if yy > y + 107:
                            raise ValueError("Shorten the quiz meaning to one line for large type")
                        text(d, (x, yy + 9), "____________", 38, MUTED)
                y += block["height"]
            page_footer(d, "核对单词 → 读词块 → 回到故事" if answer else "说英文 → 检查拼写 → 回忆词块", "#24766C")
            name = f"{kind}-{page:02d}.png"
            im.save(destination / name, optimize=True)
            groups[kind].append({"file": name, "size": [W, H], "content_bottom": y,
                                 "question_range": [start, end], "columns": columns})
    return groups


def make_delivery(request, content, reports):
    groups = []
    for key, title, purpose in GROUPS:
        cards = reports[key]
        groups.append({"id": key, "title": title, "purpose": purpose, "count": len(cards),
                       "images": [dict(card, caption=f"{title} {i}/{len(cards)}" +
                                        (f" · 第{card['question_range'][0]}—{card['question_range'][1]}题" if "question_range" in card else ""))
                                  for i, card in enumerate(cards, 1)]})
    return {"version": DELIVERY_VERSION, "batch_id": request["batch_id"], "range": [request["start"], request["end"]],
            "total_images": sum(g["count"] for g in groups), "groups": groups,
            "quiz_order": [{"question": i, "number": r["number"]} for i, r in enumerate(quiz_rows(request), 1)],
            "presentation": {"inline_images": True, "one_image_per_line": True,
                             "visible_caption_before_every_image": True, "text_between_images": True, "answers_last": True,
                             "file_download_required": False, "default_non_image_attachments": False}}


def render_package(request, content, destination):
    destination = Path(destination)
    reports = {"reading": render(request, content, destination),
               "cloze": render_cloze(request, content, destination)}
    reports.update(render_quiz(request, content, destination))
    delivery = make_delivery(request, content, reports)
    write_json(destination / "delivery.json", delivery)
    return delivery


def write_image_reply(output, delivery, final_directory):
    """An exact, caption-separated reply; the agent must not retype file paths."""
    lines = [f"第{delivery['range'][0]}—{delivery['range'][1]}词 · 共{delivery['total_images']}张图片", ""]
    for group in delivery["groups"]:
        lines += [f"{group['title']}：下面{group['count']}张。{group['purpose']}", ""]
        for card in group["images"]:
            actual = Path(final_directory) / card["file"]
            lines += [card["caption"], "", f"![{card['caption']}](<{actual.as_posix()}>)", ""]
    (Path(output) / "image-reply.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_delivery(output, request):
    output = Path(output)
    delivery = read_json(output / "delivery.json")
    if delivery["version"] != DELIVERY_VERSION or [g["id"] for g in delivery["groups"]] != [g[0] for g in GROUPS]:
        raise ValueError("Missing/reordered mobile image groups")
    files = []
    for group in delivery["groups"]:
        if not group["count"] or group["count"] != len(group["images"]):
            raise ValueError("Empty/incomplete mobile image group")
        for card in group["images"]:
            name = card["file"]
            if Path(name).name != name or not name.endswith(".png"):
                raise ValueError("Invalid image path")
            with Image.open(output / name) as im:
                if im.size != (W, H):
                    raise ValueError("Mobile image dimensions changed")
                im.verify()
            files.append(name)
    groups = {g["id"]: g for g in delivery["groups"]}
    if groups["reading"]["count"] != groups["cloze"]["count"]:
        raise ValueError("Cloze cards must match complete story cards")
    if groups["quiz"]["count"] != groups["answers"]["count"]:
        raise ValueError("Quiz and answers must have matching pages")
    if len(set(files)) != len(files) or delivery["total_images"] != len(files):
        raise ValueError("Mobile image count mismatch")
    if sorted(r["number"] for r in delivery["quiz_order"]) != [r["number"] for r in request["vocabulary"]]:
        raise ValueError("Quiz must cover all 35 words exactly once")
    for key in ("quiz", "answers"):
        ranges = [c["question_range"] for c in groups[key]["images"]]
        if [i for first, last in ranges for i in range(first, last + 1)] != list(range(1, 36)):
            raise ValueError("Quiz/answer pages skip or repeat a question")
    if [c["question_range"] for c in groups["quiz"]["images"]] != [c["question_range"] for c in groups["answers"]["images"]]:
        raise ValueError("Answer page order differs from quiz")
    return delivery
