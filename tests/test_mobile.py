import tempfile
import unittest
from pathlib import Path

from wordstory import workflow
from wordstory.common import ROOT, read_json, write_json
from wordstory.mobile import mask_text, quiz_rows, verify_delivery


class MobileTests(unittest.TestCase):
    def test_cloze_does_not_reveal_heads_or_partial_match(self):
        self.assertEqual(mask_text("A massive map is part of it.", ["massive", "part"]), "A ______ map is ______ of it.")
        self.assertEqual(mask_text("A massive map.", ["mass"]), "A massive map.")
        self.assertEqual(mask_text("It's five o’clock.", ["o'clock"]), "It's five ______.")

    def test_quiz_order_is_reproducible_and_complete(self):
        request = {"batch_id": "test", "vocabulary": [{"number": i} for i in range(332, 367)]}
        first = quiz_rows(request)
        self.assertEqual(first, quiz_rows(request))
        self.assertEqual(sorted(r["number"] for r in first), list(range(332, 367)))
        self.assertNotEqual(first, request["vocabulary"])

    @unittest.skipUnless((ROOT / "assets/fonts/NotoSansSC.ttf").exists(), "Run python -m wordstory fonts for image integration")
    def test_complete_mobile_pack_and_missing_exercise_blocks_advance(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "profile"
            workflow.init(data, ROOT / "examples/vocabulary.csv", 332)
            prepared = workflow.prepare(data, date="2026-11-05")
            request = read_json(prepared["request"])
            content = read_json(ROOT / "examples/content.json")
            content["batch_id"] = request["batch_id"]
            write_json(prepared["content"], content)
            result = workflow.build(data, prepared["request"], prepared["content"])
            delivery = verify_delivery(result["output"], request)
            self.assertEqual([g["id"] for g in delivery["groups"]], ["reading", "cloze", "quiz", "answers"])
            self.assertEqual([g["count"] for g in delivery["groups"]], [4, 4, 2, 2])
            self.assertEqual(result["images"], 12)
            self.assertFalse(delivery["presentation"]["file_download_required"])
            self.assertTrue(all(card["file"].endswith(".png") for group in delivery["groups"] for card in group["images"]))
            (Path(result["output"]) / "cloze-01.png").unlink()
            with self.assertRaises((FileNotFoundError, ValueError)):
                workflow.build(data, prepared["request"], prepared["content"], advance=True)
            self.assertEqual(read_json(data / "state.json")["next_number"], 332)


if __name__ == "__main__":
    unittest.main()
