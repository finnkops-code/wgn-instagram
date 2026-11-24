"""Render concept designs (article post in variant A and B + weekly specials) into preview/concepts/.
Uses a drawn stand-in photo and fictional headlines: for design approval only, never posted."""
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402
import weekly  # noqa: E402

OUT = ROOT / "preview" / "concepts"
OUT.mkdir(parents=True, exist_ok=True)


def stand_in_photo(w, h, seed=3) -> Path:
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    horizon = int(h * 0.42)
    for y in range(horizon):  # sky
        t = y / horizon
        d.line([(0, y), (w, y)], fill=(int(120 + 100 * t), int(170 + 70 * t), int(220 + 25 * t)))
    for i in range(70):  # tree line
        x = rnd.randint(-60, w + 60)
        r = rnd.randint(40, 110)
        d.ellipse([x - r, horizon - r * 1.3, x + r, horizon + 30], fill=(rnd.randint(20, 40), rnd.randint(70, 95), rnd.randint(40, 55)))
    for y in range(horizon, h):  # fairway with mowing stripes
        t = (y - horizon) / (h - horizon)
        g = int(150 - 60 * t)
        d.line([(0, y), (w, y)], fill=(int(70 - 30 * t), g, int(55 - 20 * t)))
    for k in range(8):
        x0 = int(w * (k / 8))
        d.polygon([(w / 2 + (x0 - w / 2) * 0.15, horizon), (w / 2 + (x0 + w / 16 - w / 2) * 0.15, horizon),
                   (x0 + w / 16, h), (x0, h)], fill=(80, 160, 70) if k % 2 else (66, 142, 60))
    gx, gy = int(w * 0.58), int(h * 0.6)
    d.ellipse([gx - 330, gy - 90, gx + 330, gy + 90], fill=(98, 178, 82))
    d.ellipse([gx - 9, gy - 5, gx + 9, gy + 5], fill=(25, 40, 25))
    d.rectangle([gx - 3, gy - 300, gx + 3, gy], fill=(240, 240, 235))
    d.polygon([(gx + 3, gy - 300), (gx + 120, gy - 262), (gx + 3, gy - 224)], fill=(226, 179, 60))
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    p = OUT / f"_stand-in-{w}x{h}.jpg"
    im.save(p, quality=92)
    return p


land = stand_in_photo(1600, 1000)
arts = [
    {"url": "https://worldgolfnews.org/news/pga-tour/concept-a/", "image_path": land,
     "headline": "Calloway seals four-shot win at Coastal Pines for first PGA Tour title",
     "published": "2026-11-23T20:00:00Z"},
    {"url": "https://worldgolfnews.org/news/dp-world-tour/concept-b/", "image_path": land,
     "headline": "Ferraro storms to Race to Dubai crown with closing 63 in season finale",
     "published": "2026-11-23T16:00:00Z"},
]
for variant in ("A", "B"):
    bot.CFG["design_variant"] = variant
    bot._mark_cache.clear()
    for i, a in enumerate(arts):
        t = bot.render(a, OUT / f"concept-article-{variant}{i + 1}.jpg")
        print(variant, i + 1, t)
    print(bot.build_caption(arts[0]))
    print("---- facebook")
    print(bot.build_caption(arts[0], "facebook"))
bot.CFG["design_variant"] = "A"
weekly.demo(OUT)
