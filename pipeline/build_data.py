"""Builds public/data.json for the sci-fi Kindle edition of Loot Table.

Catalog and story tags come from Open Library (books with science fiction subjects); Kindle
ASINs, covers and ratings from Amazon.com.au search results. Python 3.9+, standard library only.

    python pipeline/build_data.py            # resumes from pipeline/cache/
    python pipeline/build_data.py --max 1500 --no-amazon

There are no tier lists yet, so community quality is a Bayesian average of the ratings.
"""
import argparse, datetime, html, json, math, random, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
OUT = HERE.parent / "public" / "data.json"
SIDS = HERE / "sids.json"  # work key -> permanent share number, never reused
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

SUBJECTS = ["science fiction", "space opera", "military science fiction", "cyberpunk", "hard science fiction",
            "dystopias", "time travel", "first contact", "artificial intelligence", "space colonies",
            "interplanetary voyages", "life on other planets", "post-apocalyptic fiction", "robots",
            "alien invasion", "science fiction, humorous", "litrpg"]

# group -> tag -> words that mark it in Open Library subjects
VOCAB = {
    "setting": {
        "space": ["space opera", "interstellar", "space ships", "spaceships", "space warfare", "galactic", "space colonies", "interplanetary"],
        "near-future earth": ["near future", "twenty-first century"],
        "post-apocalyptic": ["post-apocalyptic", "end of the world", "nuclear warfare"],
        "dystopia": ["dystopia"],
        "alien world": ["life on other planets", "planets", "mars (planet)", "extrasolar"],
        "virtual reality": ["virtual reality", "litrpg", "gamelit", "video games"],
        "alternate history": ["alternative histories", "alternate history"],
    },
    "story": {
        "first contact": ["first contact", "human-alien encounters", "extraterrestrial beings", "aliens"],
        "alien invasion": ["invasion", "alien invasion"],
        "space war": ["space warfare", "military science fiction", "interstellar warfare", "soldiers"],
        "exploration": ["exploration", "discovery and exploration", "interplanetary voyages"],
        "colonisation": ["colonies", "colonization", "space colonies"],
        "time travel": ["time travel"],
        "artificial intelligence": ["artificial intelligence", "androids", "robots", "computers"],
        "cyberpunk": ["cyberpunk", "hackers", "cyberspace"],
        "genetic engineering": ["genetic engineering", "biotechnology", "cloning", "mutation"],
        "survival": ["survival"],
        "politics / empire": ["politics", "imperialism", "empire", "government"],
        "mystery / thriller": ["mystery", "thriller", "suspense", "detective"],
        "progression / LitRPG": ["litrpg", "gamelit", "progression"],
    },
    "tone": {
        "humorous": ["humorous", "humor", "humour", "satire", "comic"],
        "dark": ["horror", "dark"],
        "hard science": ["hard science fiction"],
    },
}


def get(url, cache_name=None, delay=0.0):
    path = CACHE / cache_name if cache_name else None
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    time.sleep(delay)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-AU,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8", "replace")
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:80]


def open_library(max_works):
    fields = "key,title,author_name,first_publish_year,subject,ratings_average,ratings_count,cover_i,language,readinglog_count"
    works = {}
    per_subject = max(100, max_works // len(SUBJECTS) * 2)
    for subj in SUBJECTS:
        for page in range(1, per_subject // 100 + 1):
            q = urllib.parse.urlencode({"q": f'subject:"{subj}"', "sort": "readinglog", "fields": fields,
                                        "limit": 100, "page": page, "language": "eng"})
            data = json.loads(get(f"https://openlibrary.org/search.json?{q}", f"ol/{slug(subj)}_{page}.json", 1.0))
            for d in data.get("docs", []):
                if d.get("author_name") and d.get("title"):
                    works.setdefault(d["key"], d)
            print(f"open library: {subj} p{page}, {len(works)} works", flush=True)
            if len(data.get("docs", [])) < 100:
                break
    ranked = sorted(works.values(), key=lambda d: -(d.get("readinglog_count") or 0))
    return ranked[:max_works]


def tags_for(subjects):
    low = [s.lower() for s in subjects]
    out = {}
    for group, tags in VOCAB.items():
        hit = [t for t, words in tags.items() if any(w in s for s in low for w in words)]
        if hit:
            out[group] = sorted(hit)
    return out


class Blocked(Exception):
    pass


def amazon(title, author):
    """First Kindle result on Amazon.com.au: asin, image, rating, rating count, or None"""
    q = f"{title} {author}"
    page = get("https://www.amazon.com.au/s?" + urllib.parse.urlencode({"k": q, "i": "digital-text"}),
               f"amazon/{slug(q)}.html", random.uniform(2.0, 4.0))
    if "captcha" in page.lower() and "s-search-result" not in page:
        (CACHE / f"amazon/{slug(q)}.html").unlink(missing_ok=True)
        raise Blocked()
    m = re.search(r'data-asin="(B0[0-9A-Z]{8})"[^>]*data-component-type="s-search-result"(.{0,15000})', page, re.S)
    if not m:
        return None
    asin, block = m.group(1), m.group(2)
    rating = re.search(r"([0-9.]+) out of 5 stars", block)
    count = re.search(r'aria-label="([0-9,]+) ratings?"', block) or re.search(r">\(?([0-9,]+)\)?</span>", block)
    img = re.search(r'class="s-image"[^>]*src="([^"]+)"', block) or re.search(r'src="([^"]+)"[^>]*class="s-image"', block)
    return {
        "asin": asin,
        "image": html.unescape(img.group(1)) if img else None,
        "rating": float(rating.group(1)) if rating else None,
        "ratingCount": int(count.group(1).replace(",", "")) if count else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=1500)
    ap.add_argument("--no-amazon", action="store_true")
    args = ap.parse_args()

    docs = open_library(args.max)
    sids = json.loads(SIDS.read_text()) if SIDS.exists() else {}
    use_amazon = not args.no_amazon
    works, tags = [], {}
    for i, d in enumerate(docs):
        key = "book:" + d["key"].rsplit("/", 1)[-1]
        author = d["author_name"][0]
        az = None
        if use_amazon:
            try:
                az = amazon(d["title"], author)
            except Blocked:
                print("amazon.com.au is asking for a captcha: carrying on without it", flush=True)
                use_amazon = False
            except Exception as e:  # one bad page shouldn't stop the build
                print(f"amazon: {d['title']}: {e}", flush=True)
        if key not in sids:
            sids[key] = max(sids.values(), default=0) + 1
        rating = (az or {}).get("rating") or d.get("ratings_average")
        count = (az or {}).get("ratingCount") if az and az.get("rating") else d.get("ratings_count")
        year = str(d["first_publish_year"]) if d.get("first_publish_year") else None
        subjects = d.get("subject") or []
        works.append({
            "key": key, "title": d["title"], "authors": d["author_name"][:3], "narrators": [],
            "bookCount": 1, "firstAsin": (az or {}).get("asin") or "",
            "image": (az or {}).get("image") or (f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg" if d.get("cover_i") else None),
            "rating": round(rating, 2) if rating else None, "ratingCount": count or None, "runtimeMin": None,
            "firstRelease": f"{year}-01-01" if year else None, "lastRelease": f"{year}-01-01" if year else None,
            "categories": [s for s in subjects if "fiction" in s.lower()][:6],
            "core": True, "mentions": 0, "ident": key, "sid": sids[key],
        })
        t = tags_for(subjects)
        if t:
            tags[key] = t
        if i % 25 == 0:
            print(f"{i + 1}/{len(docs)} {d['title']}", flush=True)

    # Bayesian average of ratings, as a log-odds-like strength around 0 (stands in for tier lists)
    rated = [w for w in works if w["rating"] and w["ratingCount"]]
    prior = sum(w["rating"] for w in rated) / max(1, len(rated))
    quality = {}
    for w in rated:
        n = w["ratingCount"]
        quality[w["key"]] = round((w["rating"] * n + prior * 50) / (n + 50) - prior, 4) * 2

    data = {
        "format": 1, "builtAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "vocab": {g: list(t) for g, t in VOCAB.items()}, "works": works, "tags": tags, "books": {},
        "lists": [], "quality": quality,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    SIDS.write_text(json.dumps(sids, indent=0))
    print(f"wrote {OUT}: {len(works)} works, {sum(1 for w in works if w['firstAsin'])} with a Kindle ASIN, {len(tags)} tagged")


if __name__ == "__main__":
    sys.exit(main())
