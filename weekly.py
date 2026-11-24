"""Weekly specials for the WGN Instagram/Facebook bot.

  Thursday  World Golf Player of the Week  (best performance of the previous Mon-Sun week, all data tours)
  Monday    Rankings overview carousel       (world rankings + season races of the tours that played)

Both are OFF until switched on in config.json ("weekly" -> enabled: true). They never count towards the
3 article posts per day. Visual style = the article posts (fairway green, gold, Fraunces + Figtree).

  python weekly.py demo     render concept visuals with SAMPLE data into preview/
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw

import bot
from bot import (CFG, MARGIN, ON_DARK, ON_DARK_2, ON_GOLD, PETROL, PETROL_DEEP, PETROL_LINE, PETROL_MID, RED,
                 RED_BRIGHT, RED_SOFT, ROOT, TZ, WHITE, W, H, draw_chevrons, draw_footer, font, gh_output, log)

WCFG = CFG.get("weekly", {})
STATE = ROOT / "state" / "weekly.json"
POSTS = ROOT / "posts"

# ESPN tours with free data (same feeds as the site). weight = how much a win there counts.
TOURS = [
    {"key": "pga", "espn": "pga", "label": "PGA TOUR", "weight": 1.00, "cat": "pga-tour"},
    {"key": "liv", "espn": "liv", "label": "LIV GOLF", "weight": 0.90, "cat": "liv-golf"},
    {"key": "dpwt", "espn": "eur", "label": "DP WORLD TOUR", "weight": 0.90, "cat": "dp-world-tour"},
    {"key": "lpga", "espn": "lpga", "label": "LPGA", "weight": 0.90, "cat": "lpga-tour"},
    {"key": "kft", "espn": "ntw", "label": "KORN FERRY", "weight": 0.65, "cat": "korn-ferry-tour"},
    {"key": "champions", "espn": "champions-tour", "label": "CHAMPIONS", "weight": 0.55, "cat": "pga-tour-champions"},
]
SB = "https://site.api.espn.com/apis/site/v2/sports/golf/{slug}/scoreboard"
LB = "https://site.web.api.espn.com/apis/site/v2/sports/golf/leaderboard?league={slug}&event={id}"
HEADSHOT = "https://a.espncdn.com/i/headshots/golf/players/full/{id}.png"


# ----------------------------------------------------------------------------- state & timing
def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"posted": {}}


def save_state(s: dict):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def week_key(kind: str, now: datetime) -> str:
    y, w, _ = now.isocalendar()
    return f"{kind}-{y}-w{w:02d}"


def is_due(kind: str, now: datetime) -> bool:
    c = WCFG.get(kind, {})
    if not c.get("enabled"):
        return False
    if now.weekday() != c["post_weekday"] or now.strftime("%H:%M") < c["post_after"]:
        return False
    return week_key(kind, now) not in load_state()["posted"]


def mark_posted(key: str, media_id: str):
    s = load_state()
    s["posted"][key] = {"media_id": media_id, "at": datetime.now(TZ).isoformat(timespec="seconds")}
    save_state(s)


def queue(key: str, url: str, headline: str, files: list[str], caption: str, caption_fb: str | None = None):
    pending = {"url": url, "slot": "weekly", "headline": headline, "title_on_image": headline,
               "image_file": f"posts/{files[0]}", "image_url": CFG["image_base_url"] + files[0],
               "extra_images": files[1:], "caption": caption, "caption_facebook": caption_fb or caption,
               "tag_context": "", "collaborators": [], "weekly": key}
    bot.PENDING_FILE.write_text(json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8")
    gh_output("has_post", "true")


def prepare_due(force: str | None = None) -> bool:
    """Called by bot.py prepare every run. Returns True when a weekly post was queued."""
    now = datetime.now(TZ)
    if force == "potw" or is_due("player_of_the_week", now):
        return prepare_potw(now)
    if force == "rankings" or is_due("rankings", now):
        return prepare_rankings(now)
    return False


# ----------------------------------------------------------------------------- data: Player of the Week
def _json(url: str):
    r = requests.get(url, headers=bot.UA, timeout=30)
    r.raise_for_status()
    return r.json()


def week_window(now: datetime) -> tuple[datetime, datetime]:
    """Previous full week, Monday 00:00 to Monday 00:00 (NL time)."""
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return this_monday - timedelta(days=7), this_monday


def finished_events(tour: dict, start: datetime, end: datetime) -> list[dict]:
    cal = (_json(SB.format(slug=tour["espn"])).get("leagues") or [{}])[0].get("calendar") or []
    out = []
    for c in cal:
        try:
            e_end = datetime.fromisoformat(c["endDate"].replace("Z", "+00:00"))
        except Exception:
            continue
        if start.astimezone(timezone.utc) <= e_end < end.astimezone(timezone.utc) + timedelta(hours=12):
            lb = _json(LB.format(slug=tour["espn"], id=c["id"]))
            if lb.get("events"):
                out.append(lb["events"][0])
    return out


def potw_candidates(now: datetime) -> list[dict]:
    start, end = week_window(now)
    cands = []
    for t in TOURS:
        try:
            events = finished_events(t, start, end)
        except Exception as e:
            log(f"  {t['key']}: no data ({e})")
            continue
        for ev in events:
            comp = (ev.get("competitions") or [{}])[0]
            players = sorted(comp.get("competitors") or [], key=lambda c: c.get("sortOrder", 999))
            if not players or (ev.get("status", {}).get("type", {}).get("state") != "post"):
                continue
            win = players[0]
            ath = win.get("athlete") or {}
            rounds = [l.get("value") for l in win.get("linescores") or [] if l.get("value") and not l.get("isPlayoff")]
            to_par = win["score"]["displayValue"] if isinstance(win.get("score"), dict) else win.get("score")
            runner = players[1] if len(players) > 1 else {}
            r_val = runner.get("score", {}).get("value") if isinstance(runner.get("score"), dict) else None
            w_val = win.get("score", {}).get("value") if isinstance(win.get("score"), dict) else None
            margin = (r_val - w_val) if (r_val is not None and w_val is not None) else 0
            major = bool((ev.get("tournament") or {}).get("major"))
            score = 100 * t["weight"] * (1.5 if major else 1.0)
            notes = []
            if margin >= 3:
                score += min(15, 3 * margin)
                notes.append(f"won by {margin:g}")
            if margin == 0:
                notes.append("won in a playoff")
            if rounds and min(rounds) <= 62:
                score += 8
                notes.append(f"shot {min(rounds):g}")
            cands.append({"name": ath.get("displayName", ""), "id": ath.get("id") or win.get("id"),
                          "country": (ath.get("flag") or {}).get("alt", ""), "tour": t, "event": ev.get("name", ""),
                          "major": major, "to_par": to_par, "rounds": rounds, "margin": margin,
                          "score": round(score, 1), "notes": notes})
    return sorted(cands, key=lambda c: c["score"], reverse=True)


def verified_headshot(pid) -> Image.Image | None:
    """Official ESPN headshot of exactly this player id; None if missing or the generic silhouette."""
    try:
        r = requests.get(HEADSHOT.format(id=pid), headers=bot.UA, timeout=20)
        if r.status_code != 200 or len(r.content) < 15000:
            return None
        return Image.open(BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None


def prepare_potw(now: datetime) -> bool:
    key = week_key("player_of_the_week", now)
    for c in potw_candidates(now):
        photo = verified_headshot(c["id"])
        if photo is None:
            log(f"  POTW: no verified photo for {c['name']}, next candidate")
            continue
        start, end = week_window(now)
        files = render_potw(c, photo, start, end - timedelta(days=1), key)
        cap = potw_caption(c)
        queue(key, f"custom:{key}", f"Player of the Week: {c['name']}", files, cap)
        return True
    log("  POTW: no candidate with a verified photo this week")
    return False


def potw_caption(c: dict) -> str:
    rounds = "-".join(f"{r:g}" for r in c["rounds"])
    why = f" ({', '.join(c['notes'])})" if c["notes"] else ""
    return "\n\n".join([
        f"🏆 World Golf Player of the Week: {c['name']}",
        f"{c['name']} won the {c['event']} on the {c['tour']['label'].title()} at {c['to_par']}{why}. Rounds: {rounds}.",
        "👉 Full results and leaderboards via the link in our bio.",
        CFG["follow_line"],
        " ".join(CFG["league_hashtags"].get(c["tour"]["cat"], []) + CFG["base_hashtags"] + ["#PlayerOfTheWeek"]),
    ])


def prepare_rankings(now: datetime) -> bool:
    # Data sources are chosen after Finn approves the proposal (see README "Wekelijkse posts").
    log("  Rankings: not configured yet")
    return False


# ----------------------------------------------------------------------------- visuals
def kicker(draw, y, chip, eyebrow):
    x = draw_chevrons(draw, MARGIN, y + 6, RED_BRIGHT)
    f_chip = font("figtree-800", 28)
    lw = draw.textlength(chip, font=f_chip)
    draw.rounded_rectangle([x + 8, y - 6, x + 8 + lw + 32, y + 40], radius=8, fill=RED)
    draw.text((x + 24, y + 17), chip, font=f_chip, fill=ON_GOLD, anchor="lm")
    draw.text((x + 8 + lw + 32 + 18, y + 17), eyebrow, font=font("figtree-700", 26), fill=ON_DARK_2, anchor="lm")


def green_backdrop() -> Image.Image:
    """Deep green with the site's subtle dot texture and a soft light from the top."""
    img = Image.new("RGBA", (W, H), PETROL_DEEP + (255,))
    d = ImageDraw.Draw(img)
    for yy in range(0, H, 28):
        for xx in range(14 if (yy // 28) % 2 else 0, W, 28):
            d.ellipse([xx - 1.4, yy - 1.4, xx + 1.4, yy + 1.4], fill=(47, 122, 96, 60))
    img.alpha_composite(bot.vertical_gradient(W, 700, PETROL, 255, 0, ease=1.2), (0, 0))
    return img


def flag_dot(draw, x, y, country: str):
    draw.text((x, y), country.upper()[:3], font=font("figtree-800", 22), fill=ON_DARK_2, anchor="lm")


def render_potw(c: dict, photo: Image.Image, start: datetime, end: datetime, key: str,
                out_dir: Path = POSTS, sample: bool = False) -> list[str]:
    img = green_backdrop()
    d = ImageDraw.Draw(img)
    kicker(d, 84, c["tour"]["label"], f"{start.strftime('%b %-d').upper()} – {end.strftime('%b %-d, %Y').upper()}")
    # big serif title
    d.text((MARGIN, 150), "Player", font=font("fraunces-800", 132), fill=WHITE)
    d.text((MARGIN, 280), "of the Week", font=font("fraunces-800", 132), fill=RED)
    # headshot, bottom-right, centre-top aligned, fading into the panel
    ph = photo.copy()
    ph.thumbnail((760, 760), Image.LANCZOS)
    px = W - ph.width + 60
    py = 1350 - 132 - 330 - ph.height + 40
    img.alpha_composite(ph, (px, max(380, py)))
    img.alpha_composite(bot.vertical_gradient(W, 200, PETROL_DEEP, 0, 255, ease=1.3), (0, 1350 - 132 - 330 - 160))
    d = ImageDraw.Draw(img)
    # stat panel
    top = 1350 - 132 - 330
    d.rectangle([0, top + 40, W, 1350], fill=PETROL_DEEP)
    d.text((MARGIN, top + 40), c["name"], font=font("fraunces-700", 82), fill=WHITE, anchor="lt")
    sub = f"Won the {c['event']}" + (" · MAJOR" if c["major"] else "")
    d.text((MARGIN, top + 150), sub, font=font("figtree-700", 32), fill=ON_DARK)
    stats = [("TO PAR", str(c["to_par"])), ("ROUNDS", "-".join(f"{r:g}" for r in c["rounds"])),
             ("MARGIN", "Playoff" if c["margin"] == 0 else f"{c['margin']:g} shots")]
    cols = [MARGIN, MARGIN + 240, MARGIN + 640]
    for i, (lbl, val) in enumerate(stats):
        x = cols[i]
        d.text((x, top + 220), lbl, font=font("figtree-800", 22), fill=RED_SOFT)
        d.text((x, top + 254), val, font=font("fraunces-700", 50 if len(val) < 12 else 38), fill=WHITE)
    draw_footer(d, H - 132, "FULL RESULTS · LINK IN BIO", canvas=img)
    if sample:
        sample_tag(d)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{key}.jpg"
    img.convert("RGB").save(out_dir / name, "JPEG", quality=90, optimize=True)
    return [name]


def render_ranking_slide(title: str, chip: str, eyebrow: str, rows: list[dict], name: str,
                         out_dir: Path = POSTS, sample: bool = False, cta="FULL RANKINGS · LINK IN BIO"):
    """rows: {rank, move (+n/-n/0/None), name, country, value}"""
    img = green_backdrop()
    d = ImageDraw.Draw(img)
    kicker(d, 84, chip, eyebrow)
    d.text((MARGIN, 150), title, font=font("fraunces-800", 84), fill=WHITE)
    top, bottom = 300, H - 132 - 30
    row_h = (bottom - top) / max(len(rows), 1)
    for i, r in enumerate(rows):
        y = top + i * row_h
        if i == 0:
            d.rounded_rectangle([MARGIN - 20, y + 4, W - MARGIN + 20, y + row_h - 4], radius=12, fill=RED)
        elif i % 2 == 1:
            d.rounded_rectangle([MARGIN - 20, y + 4, W - MARGIN + 20, y + row_h - 4], radius=12, fill=PETROL_MID)
        cy = y + row_h / 2
        on = ON_GOLD if i == 0 else WHITE
        d.text((MARGIN + 30, cy), str(r["rank"]), font=font("fraunces-800", 46), fill=on, anchor="mm")
        mv = r.get("move")
        if mv:
            up = mv > 0
            col = (ON_GOLD if i == 0 else (120, 214, 160)) if up else (ON_GOLD if i == 0 else (240, 140, 120))
            ax, ay = MARGIN + 82, cy
            d.polygon([(ax - 9, ay + 6), (ax + 9, ay + 6), (ax, ay - 8)] if up else [(ax - 9, ay - 6), (ax + 9, ay - 6), (ax, ay + 8)], fill=col)
            d.text((ax + 14, cy), str(abs(mv)), font=font("figtree-800", 20), fill=col, anchor="lm")
        elif mv == 0:
            d.text((MARGIN + 82, cy), "–", font=font("figtree-800", 24), fill=ON_GOLD if i == 0 else ON_DARK_2, anchor="mm")
        d.text((MARGIN + 140, cy), r["name"], font=font("fraunces-700", 40), fill=on, anchor="lm")
        nw = d.textlength(r["name"], font=font("fraunces-700", 40))
        d.text((MARGIN + 140 + nw + 16, cy + 2), r.get("country", ""), font=font("figtree-800", 20),
               fill=ON_GOLD if i == 0 else ON_DARK_2, anchor="lm")
        d.text((W - MARGIN, cy), r["value"], font=font("figtree-700", 28), fill=on, anchor="rm")
    draw_footer(d, H - 132, cta, canvas=img)
    if sample:
        sample_tag(d)
    out_dir.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_dir / name, "JPEG", quality=90, optimize=True)
    return name


def render_rankings_cover(week: str, items: list[str], name: str, out_dir: Path = POSTS, sample: bool = False):
    img = green_backdrop()
    d = ImageDraw.Draw(img)
    kicker(d, 84, "RANKINGS", week)
    d.text((MARGIN, 200), "The world", font=font("fraunces-800", 140), fill=WHITE)
    d.text((MARGIN, 350), "rankings", font=font("fraunces-800", 140), fill=RED)
    d.text((MARGIN, 520), "Who moved this week, from the world ranking\nto every season race.",
           font=font("figtree-700", 36), fill=ON_DARK, spacing=12)
    y = 680
    for i, it in enumerate(items):
        d.line([(MARGIN, y), (W - MARGIN, y)], fill=PETROL_LINE, width=2)
        d.text((MARGIN, y + 38), f"{i + 2:02d}", font=font("figtree-800", 24), fill=RED)
        d.text((MARGIN + 70, y + 38), it, font=font("fraunces-700", 40), fill=WHITE, anchor="lm")
        y += 76
    ax, ay = W - MARGIN, y + 34
    d.polygon([(ax - 18, ay - 11), (ax, ay), (ax - 18, ay + 11)], fill=RED)
    d.text((ax - 30, ay), "SWIPE", font=font("figtree-800", 26), fill=RED, anchor="rm")
    draw_footer(d, H - 132, "ALL RANKINGS · LINK IN BIO", canvas=img)
    if sample:
        sample_tag(d)
    out_dir.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_dir / name, "JPEG", quality=90, optimize=True)
    return name


def sample_tag(d):
    t = "CONCEPT · VOORBEELDDATA"
    f = font("figtree-800", 20)
    tw = d.textlength(t, font=f)
    d.rounded_rectangle([W - MARGIN - tw - 28, 70, W - MARGIN, 108], radius=19, fill=(180, 40, 40))
    d.text((W - MARGIN - tw / 2 - 14, 89), t, font=f, fill=WHITE, anchor="mm")


# ----------------------------------------------------------------------------- demo
def demo(out_dir: Path):
    """Concept visuals with made-up sample data (fictional players), for design approval only."""
    from PIL import ImageFilter
    # stand-in headshot: neutral silhouette (real posts use the player's official ESPN headshot)
    sil = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sil)
    sd.ellipse([230, 90, 470, 350], fill=(196, 210, 201, 255))
    sd.rounded_rectangle([110, 360, 590, 760], radius=200, fill=(196, 210, 201, 255))
    sd.polygon([(300, 360), (400, 360), (350, 470)], fill=(226, 179, 60, 255))
    sil = sil.filter(ImageFilter.GaussianBlur(1))
    c = {"name": "Sam Calloway", "country": "USA", "tour": TOURS[0], "event": "Coastal Pines Classic", "major": False,
         "to_par": "-21", "rounds": [66, 65, 68, 64], "margin": 4, "notes": ["won by 4"]}
    mon = datetime(2026, 11, 16, tzinfo=TZ)
    render_potw(c, sil, mon, mon + timedelta(days=6), "concept-potw", out_dir, sample=True)
    names = ["Sam Calloway", "Luca Ferraro", "Kenji Arai", "Tom Whitfield", "Mateo Ruiz", "Oskar Lindqvist",
             "Ryan Doherty", "Jae-won Park", "Pieter de Wit", "Callum Reid"]
    ctry = ["USA", "ITA", "JPN", "ENG", "ESP", "SWE", "IRL", "KOR", "NED", "SCO"]
    moves = [0, 1, -1, 2, 0, -2, 5, 0, -1, 3]
    rows = [{"rank": i + 1, "move": moves[i], "name": names[i], "country": ctry[i], "value": f"{14.8 - i * 0.9:.2f}"}
            for i in range(10)]
    render_rankings_cover("WEEK 48 · NOV 23, 2026", ["Official World Golf Ranking", "Women's World Golf Rankings",
                          "FedExCup", "Race to Dubai", "LPGA Race to CME Globe"], "concept-rankings-1.jpg", out_dir, True)
    render_ranking_slide("World Golf Ranking", "OWGR", "TOP 10 · AVG. POINTS", rows, "concept-rankings-2.jpg", out_dir, True)
    wn = ["Mia Sorensen", "Ji-ho Han", "Lena Brandt", "Aiko Mori", "Grace Tull", "Camila Vega", "Nora Quinn",
          "Yuna Seo", "Elise Martin", "Hannah Cole"]
    wrows = [{"rank": i + 1, "move": [0, 0, 2, -1, 1, -2, 0, 4, -1, 0][i], "name": wn[i],
              "country": ["DEN", "KOR", "GER", "JPN", "AUS", "MEX", "USA", "KOR", "FRA", "ENG"][i],
              "value": f"{11.2 - i * 0.7:.2f}"} for i in range(10)]
    render_ranking_slide("Women's World Ranking", "ROLEX RANKINGS", "TOP 10 · AVG. POINTS", wrows,
                         "concept-rankings-3.jpg", out_dir, True)
    mrows = [{"rank": i + 1, "move": None, "name": names[(i * 3) % 10], "country": ctry[(i * 3) % 10],
              "value": f"{3120 - i * 240:,} pts"} for i in range(10)]
    render_ranking_slide("Race to Dubai", "DP WORLD TOUR", "SEASON RACE", mrows, "concept-rankings-4.jpg",
                         out_dir, True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo(ROOT / "preview")
    elif len(sys.argv) > 1 and sys.argv[1] == "candidates":
        for c in potw_candidates(datetime.now(TZ)):
            print(c["score"], c["name"], c["tour"]["key"], c["event"], c["to_par"], c["notes"])
    else:
        sys.exit(__doc__)
