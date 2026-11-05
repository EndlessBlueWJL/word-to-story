import re
from collections import Counter

from .common import RULES_VERSION, canonical_hash


def normalize(text):
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip().lower()


def contains(text, phrase):
    return bool(re.search(r"(?<![a-z])" + re.escape(normalize(phrase)) + r"(?![a-z])", normalize(text)))


def seal_request(request):
    return canonical_hash({k: v for k, v in request.items() if k != "request_hash"})


def validate_request(request):
    if request.get("request_hash") != seal_request(request):
        raise ValueError("request.json changed: prepare a new request instead of editing it")
    if request.get("rules_version") != RULES_VERSION:
        raise ValueError("Unknown rules version")
    rows = request.get("vocabulary", [])
    if len(rows) != 35:
        raise ValueError("A batch must contain exactly 35 words")
    numbers = [r["number"] for r in rows]
    if numbers != list(range(numbers[0], numbers[0] + 35)):
        raise ValueError("Vocabulary numbers must be consecutive")
    words = [r["word"].lower() for r in rows]
    if len(set(words)) != 35:
        raise ValueError("Repeated headwords in this batch need human resolution")


def validate(request, content):
    validate_request(request)
    if content.get("batch_id") != request["batch_id"]:
        raise ValueError("Content belongs to a different batch")
    if content.get("rules_version") != RULES_VERSION:
        raise ValueError("Content rules_version does not match the final requirements")
    stories = content.get("stories", [])
    if not 1 <= len(stories) <= 4:
        raise ValueError("Use 1 to 4 stories/dialogues, one complete story per image")
    vocab = {r["word"].lower(): r for r in request["vocabulary"]}
    details = content.get("details", {})
    if set(details) != set(vocab):
        raise ValueError("details must contain all and only the 35 selected words")
    allocated = Counter(w for s in stories for w in s.get("words", []))
    if allocated != Counter(vocab.keys()):
        raise ValueError("Assign each selected word to exactly one story")
    counts = []
    for i, story in enumerate(stories, 1):
        if story.get("id") != i:
            raise ValueError("Story ids must be 1, 2, ... in reading order")
        for field in ("title", "en_title", "topic", "kind", "gist", "retell", "rewrite"):
            if not isinstance(story.get(field), str) or not story[field].strip():
                raise ValueError(f"Story {i}: missing {field}")
        if story["kind"] not in ("小故事", "日常对话"):
            raise ValueError("kind must be 小故事 or 日常对话")
        paragraphs = story.get("paragraphs", [])
        if not paragraphs or not all(isinstance(p, str) and p.strip() for p in paragraphs):
            raise ValueError(f"Story {i}: empty paragraphs")
        body = "\n".join(paragraphs)
        count = len(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", body))
        if count > 110 or count < 35:
            raise ValueError(f"Story {i}: {count} words; use 35–110, normally 80–110 for four stories")
        for word in story["words"]:
            if not contains(body, word):
                raise ValueError(f"Story {i}: missing exact headword {word}")
            detail = details[word]
            if not isinstance(detail.get("meaning"), str) or not detail["meaning"].strip():
                raise ValueError(f"Missing context meaning: {word}")
            chunk = detail.get("chunk", "")
            if not chunk or not contains(chunk, word) or not contains(body, chunk):
                raise ValueError(f"Chunk must contain {word} and occur verbatim in its story")
        grammar = story.get("grammar", [])
        if len(grammar) != 1:
            raise ValueError(f"Story {i}: use one short grammar note")
        note = grammar[0]
        if not all(isinstance(note.get(k), str) and note[k].strip() for k in ("label", "example", "explanation")):
            raise ValueError(f"Story {i}: incomplete grammar note")
        if normalize(note["example"]) not in normalize(body):
            raise ValueError(f"Story {i}: grammar example is not in the story")
        if "___" not in story["rewrite"]:
            raise ValueError(f"Story {i}: rewrite must have a blank for a personal answer")
        counts.append({"id": i, "words": count, "targets": len(story["words"])})
    review = content.get("editorial_review", {})
    fields = ("simple_other_words", "natural_speech", "ielts_topics", "exam_grammar", "meaning_and_collocations")
    if any(review.get(k) is not True for k in fields) or not review.get("notes"):
        raise ValueError("Agent must review language quality and record notes before rendering")
    return {"coverage": "35/35", "chunks_present": True, "grammar_examples_present": True,
            "stories": counts, "language_quality": "agent self-review; human review recommended"}
