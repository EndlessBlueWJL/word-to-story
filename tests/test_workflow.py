import copy
import csv
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from wordstory import workflow
from wordstory.common import ROOT, read_json, write_json
from wordstory.extract import parse_numbered_text
from wordstory.validation import contains, validate


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.data = self.home / "profile"
        workflow.init(self.data, ROOT / "examples" / "vocabulary.csv", 332)
        self.next_request()
        # Isolate state/receipt tests from graphics/network. Real fonts/rendering
        # are exercised separately by the end-to-end demo in CI.
        def renderer(request, content, destination):
            for s in content["stories"]:
                (destination / f"story-{s['id']:02d}.png").write_bytes(b"test-image")
            return [{"file": "story-01.png", "size": [1080, 1920]}]
        self.render_patch = patch("wordstory.render.render", side_effect=renderer)
        self.render_patch.start()
        self.addCleanup(self.render_patch.stop)

    def next_request(self, start=None):
        self.prepared = workflow.prepare(self.data, start=start, date="2026-11-05")
        self.request = read_json(self.prepared["request"])
        self.content = read_json(ROOT / "examples" / "content.json")
        self.content["batch_id"] = self.request["batch_id"]
        write_json(self.prepared["content"], self.content)

    def build(self, advance=False):
        return workflow.build(self.data, self.prepared["request"], self.prepared["content"], advance)

    def test_accepted_content_covers_all_words(self):
        result = validate(self.request, self.content)
        self.assertEqual(result["coverage"], "35/35")
        self.assertEqual([s["words"] for s in result["stories"]], [85, 88, 81, 81])

    def test_whole_headword_and_phrases(self):
        self.assertFalse(contains("a massive map", "mass"))
        self.assertTrue(contains("I want ice cream.", "ice cream"))
        self.assertTrue(contains("It's five o’clock.", "o'clock"))

    def test_reject_missing_headword(self):
        self.content["stories"][0]["paragraphs"][0] = self.content["stories"][0]["paragraphs"][0].replace("massive", "big")
        with self.assertRaisesRegex(ValueError, "missing exact headword"):
            validate(self.request, self.content)

    def test_reject_invented_chunk(self):
        self.content["details"]["massive"]["chunk"] = "a massive elephant"
        with self.assertRaisesRegex(ValueError, "verbatim"):
            validate(self.request, self.content)

    def test_reject_unrelated_grammar_example(self):
        self.content["stories"][0]["grammar"][0]["example"] = "I like music."
        with self.assertRaisesRegex(ValueError, "not in the story"):
            validate(self.request, self.content)

    def test_cannot_skip_language_review(self):
        self.content["editorial_review"]["simple_other_words"] = False
        with self.assertRaisesRegex(ValueError, "review language quality"):
            validate(self.request, self.content)

    def test_request_cannot_be_edited_to_change_words(self):
        self.request["vocabulary"][0]["word"] = "easy"
        with self.assertRaisesRegex(ValueError, "request.json changed"):
            validate(self.request, self.content)

    def test_build_only_does_not_advance(self):
        self.assertFalse(self.build()["progress_advanced"])
        self.assertEqual(read_json(self.data / "state.json")["next_number"], 332)

    def test_advance_only_once_after_complete_build(self):
        first, second = self.build(True), self.build(True)
        self.assertTrue(first["progress_advanced"])
        self.assertFalse(second["progress_advanced"])
        state = read_json(self.data / "state.json")
        self.assertEqual(state["next_number"], 367)
        self.assertEqual(len(state["history"]), 1)
        with zipfile.ZipFile(Path(first["output"]) / "learning-pack.zip") as archive:
            self.assertIsNone(archive.testzip())

    def test_corrupted_image_blocks_advance(self):
        out = Path(self.build()["output"])
        (out / "story-02.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed or missing"):
            self.build(True)
        self.assertEqual(read_json(self.data / "state.json")["next_number"], 332)

    def test_review_can_never_advance(self):
        self.next_request(start=332)
        with self.assertRaisesRegex(ValueError, "never advance"):
            self.build(True)

    def test_stale_parallel_request_cannot_advance(self):
        stale = copy.deepcopy(self.prepared)
        self.next_request()
        self.build(True)
        with self.assertRaisesRegex(ValueError, "Stale request"):
            workflow.build(self.data, stale["request"], stale["content"], True)

    def test_render_failure_leaves_progress_intact(self):
        with patch("wordstory.render.render", side_effect=ValueError("overflow")):
            with self.assertRaisesRegex(ValueError, "overflow"):
                self.build(True)
        self.assertEqual(read_json(self.data / "state.json")["next_number"], 332)

    def test_backup_restore_and_no_overwrite(self):
        self.build(True)
        archive = self.home / "backup.zip"
        workflow.backup(self.data, archive)
        recovered = self.home / "recovered"
        workflow.restore(archive, recovered)
        self.assertEqual(read_json(self.data / "state.json"), read_json(recovered / "state.json"))
        with self.assertRaisesRegex(ValueError, "empty/new"):
            workflow.restore(archive, recovered)

    def test_zip_traversal_is_rejected(self):
        archive = self.home / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.write(self.data / "state.json", "state.json")
            z.write(self.data / "vocabulary.csv", "vocabulary.csv")
            z.writestr("../escape.txt", "bad")
        with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
            workflow.restore(archive, self.home / "unsafe")
        self.assertFalse((self.home / "escape.txt").exists())

    def test_lock_prevents_concurrent_writes(self):
        with workflow.locked(self.data):
            with self.assertRaisesRegex(ValueError, "Another write"):
                workflow.prepare(self.data)

    def test_tail_does_not_wrap_or_shrink_batch(self):
        self.build(True)
        with self.assertRaisesRegex(ValueError, "Only 0 words remain"):
            workflow.prepare(self.data)

    def test_init_never_resets_existing_progress(self):
        self.build(True)
        with self.assertRaisesRegex(ValueError, "never resets"):
            workflow.init(self.data, ROOT / "examples" / "vocabulary.csv", 332)
        self.assertEqual(read_json(self.data / "state.json")["next_number"], 367)

    def test_pdf_line_wrap_apostrophe_and_phrase(self):
        text = "Word\nMeaning\n1\nair-\nconditioning\n2 o'clock\n3 ice cream\n共 3 词"
        self.assertEqual(parse_numbered_text(text), [(1, "air-conditioning"), (2, "o'clock"), (3, "ice cream")])


if __name__ == "__main__":
    unittest.main()
