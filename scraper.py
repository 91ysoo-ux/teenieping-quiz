"""티니핑 데이터 수집기.

Catch! Teenieping 팬 위키(catchteenieping.fandom.com)에서 티니핑 목록과
대표 이미지 주소를 가져와 pings.json(게임 데이터베이스)에 저장한다.
(이미지 서버가 프로그램 다운로드를 막아서, 사진은 브라우저가 위키에서 직접 불러온다)
GitHub Actions가 매주 실행해서 새 핑을 자동으로 추가한다.

    python scraper.py
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://catchteenieping.fandom.com/api.php"
UA = "TeeniepingQuizForMyKid/1.0 (personal use)"
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "pings.json"

# 이 페이지/카테고리에 걸린 문서들 중 티니핑 캐릭터 문서만 골라낸다
LIST_PAGES = ["List of Teeniepings", "Teeniepings"]
ROOT_CATEGORY = "Category:Teeniepings"
PLACEHOLDER = "No screenshot"  # 위키의 "사진 없음" 이미지


def api(**params):
    params.update(format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def candidate_titles(log):
    titles = set()
    for page in LIST_PAGES:
        data = api(action="parse", page=page, prop="links", redirects=1)
        titles.update(l["title"] for l in data["parse"]["links"] if l["ns"] == 0)

    seen_cats, queue = set(), [ROOT_CATEGORY]
    while queue:
        cat = queue.pop()
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        cont = {}
        while True:
            data = api(action="query", list="categorymembers", cmtitle=cat,
                       cmlimit="500", **cont)
            for m in data["query"]["categorymembers"]:
                if m["ns"] == 14:
                    queue.append(m["title"])
                elif m["ns"] == 0:
                    titles.add(m["title"])
            if "continue" not in data:
                break
            cont = data["continue"]
    log(f"후보 문서 {len(titles)}개")
    return sorted(titles)


KR_RE = re.compile(r"\{\{KR\|([^|}]+)")
GALLERY_RE = re.compile(r"\|\s*image\s*=\s*<gallery>\s*(.*?)</gallery>", re.S)
IMAGE_RE = re.compile(r"\|\s*image\s*=\s*\[*(?:File:)?([^|\]\n]+\.(?:png|jpe?g|webp|gif))", re.I)


def parse_character(title, text):
    if "{{Character" not in text:
        return None
    if not title.lower().endswith("ping"):  # "Star Teeniepings" 같은 묶음 문서 제외
        return None
    kr = KR_RE.search(text)
    if not kr:
        return None
    image = None
    g = GALLERY_RE.search(text)
    if g:
        for line in g.group(1).splitlines():
            name = line.split("|")[0].strip()
            if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                image = name.removeprefix("File:")
                break
    if not image:
        m = IMAGE_RE.search(text)
        image = m.group(1).strip() if m else None
    if not image:
        return None
    return {"en": title, "ko": kr.group(1).strip(), "file": image}


def fetch_characters(titles, log):
    found = {}
    for batch in chunks(titles, 50):
        data = api(action="query", prop="revisions", rvprop="content",
                   rvslots="main", titles="|".join(batch), redirects=1)
        for page in data["query"].get("pages", []):
            revs = page.get("revisions")
            if not revs:
                continue
            ch = parse_character(page["title"], revs[0]["slots"]["main"]["content"])
            if ch:
                found[ch["en"]] = ch
    log(f"티니핑 캐릭터 {len(found)}개 확인")
    return list(found.values())


def image_urls(files):
    urls = {}
    for batch in chunks(sorted(set(files)), 50):
        data = api(action="query", prop="imageinfo", iiprop="url", iiurlwidth="600",
                   titles="|".join("File:" + f for f in batch))
        norm = {n["to"]: n["from"] for n in data["query"].get("normalized", [])}
        for page in data["query"].get("pages", []):
            info = page.get("imageinfo")
            if info:
                src = norm.get(page["title"], page["title"]).removeprefix("File:")
                urls[src] = info[0].get("thumburl") or info[0]["url"]
    return urls


def load_db():
    if DB_PATH.exists():
        return {p["en"]: p for p in json.loads(DB_PATH.read_text(encoding="utf-8"))}
    return {}


def update(log=print):
    db = load_db()
    chars = fetch_characters(candidate_titles(log), log)
    urls = image_urls([c["file"] for c in chars])

    added = 0
    for c in chars:
        url = urls.get(c["file"])
        if not url or c["file"].startswith(PLACEHOLDER):
            # 위키에 아직 사진이 없는 핑은 빼두고, 사진이 올라오면 다음 업데이트 때 들어간다
            if db.pop(c["en"], None):
                log(f"  - 사진 없음, 제외: {c['en']}")
            continue
        if c["en"] not in db:
            added += 1
            log(f"  + {c['ko']} ({c['en']})")
        # 기존 핑도 이미지 주소/한글이름은 최신으로 갱신 (위키에서 사라진 핑은 그대로 둔다)
        db[c["en"]] = {"en": c["en"], "ko": c["ko"], "image": url}

    pings = sorted(db.values(), key=lambda p: p["en"])
    DB_PATH.write_text(json.dumps(pings, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"완료: 새 티니핑 {added}개, 전체 {len(pings)}개")
    return {"added": added, "total": len(pings)}


if __name__ == "__main__":
    update()
