"""Raster regressions for readable inline English, independent of delivery checks."""
import unittest

from PIL import Image, ImageDraw

from wordstory.common import ROOT
from wordstory.fonts import font
from wordstory.render import BG, rich


@unittest.skipUnless((ROOT / "assets/fonts/NotoSerif.ttf").exists(), "Run python -m wordstory fonts")
class InlineTypographyTests(unittest.TestCase):
    def test_lowercase_capitals_targets_and_punctuation_share_baseline(self):
        # These words end on the same baseline; only bridge has a descender.
        # Looking at raster ink catches the old per-token top alignment even
        # though the PNG size, coverage, and overflow checks all still passed.
        for masked in (False, True):
            with self.subTest(masked=masked):
                image = Image.new("RGB", (1000, 160), BG)
                draw = ImageDraw.Draw(image)
                words = ["I", "we", "a", "mass", "we", "a", "bridge", "."]
                rich(draw, "I we a mass we a bridge .", 20, 40, 960,
                     {"mass"}, {"mass": {"number": 333}}, "#496BA0", "#EAF0FA", masked=masked)
                x, bottoms = 20, []
                for word in words:
                    target = word == "mass"
                    display = "______" if target and masked else word
                    width = draw.textlength(display, font=font("body", 42, target))
                    # Leave the superscript outside the word crop.
                    crop = image.crop((int(x) - 1, 20, int(x + width) + 1, 130))
                    ink = crop.convert("L").point(lambda p: 255 if p < 190 else 0)
                    bounds = ink.getbbox()
                    self.assertIsNotNone(bounds, word)
                    if not (target and masked):
                        bottoms.append((word, bounds[3] + 20))
                    x += width
                    if target:
                        x += draw.textlength("333", font=font("ui", 17, True)) + 5
                    x += draw.textlength(" ", font=font("body", 42))
                baseline_bottoms = [bottom for word, bottom in bottoms if word != "bridge"]
                self.assertLessEqual(max(baseline_bottoms) - min(baseline_bottoms), 1, bottoms)
                descender_bottom = next(bottom for word, bottom in bottoms if word == "bridge")
                self.assertGreaterEqual(descender_bottom - max(baseline_bottoms), 8)


if __name__ == "__main__":
    unittest.main()
