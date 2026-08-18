# Downloads real product photography from the live texastruckparts.shop product pages
# into assets/img/ so the V2 templates serve images from our own folder — no hotlinking
# to the old site's CDN.
#
# For each product it reads the WooCommerce gallery (data-large_image, in gallery order),
# then picks two sizes per shot from the page's own srcset:
#     thumb  ~300w  -> product cards + PDP thumbnails
#     main   ~768w  -> PDP main image
# Falls back to the full-size original when a variant is missing.
#
# Re-running is safe: products already in the manifest and files already on disk are
# skipped, so an interrupted run resumes where it stopped.
#
# Usage:  python build/fetch_images.py [max_images_per_product] [max_products]
import csv, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "texas_truck_parts_products_v2.csv")
IMGDIR = os.path.join(ROOT, "assets", "img")
MANIFEST = os.path.join(IMGDIR, "manifest.json")

MAX_IMAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 6
MAX_PRODUCTS = int(sys.argv[2]) if len(sys.argv) > 2 else 0   # 0 = all
DELAY = 0.6          # be polite to the live store
TIMEOUT = 30
UA = "Mozilla/5.0 (compatible; TexasTruckParts-V2-migration/1.0)"

SRCSET_RE = re.compile(r"(https://[^\s\"']+/wp-content/uploads/[^\s\"']+?\.(?:jpg|jpeg|png|webp))\s+(\d+)w", re.I)
GALLERY_RE = re.compile(r'data-large_image="([^"]+)"')
STEM_RE = re.compile(r"^(.*?)(?:-\d+x\d+)?\.(jpg|jpeg|png|webp)$", re.I)


def get(url, binary=False):
    """Fetch via curl. Python's ssl module rejects a CA in this machine's trust chain
    ('Basic Constraints ... not marked critical'); curl uses the system store and works.
    Verification stays ON — do not add -k here."""
    p = subprocess.run(
        ["curl", "-sL", "--fail", "--max-time", str(TIMEOUT), "-A", UA, url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if p.returncode != 0:
        raise RuntimeError("curl exit %d %s" % (p.returncode, p.stderr.decode fallback_dec()))
    return p.stdout if binary else p.stdout.decode("utf-8", "replace")


def stem(url):
    """s-l1600-259-300x300.jpg -> s-l1600-259 (path included, size suffix stripped)"""
    m = STEM_RE.match(url)
    return m.group(1) if m else url


def pick(cands, want, full):
    """cands: [(width, url)] sorted; choose the smallest variant >= want, else the largest."""
    if not cands:
        return full
    ge = [c for c in cands if c[0] >= want]
    return (min(ge, key=lambda c: c[0]) if ge else max(cands, key=lambda c: c[0]))[1]


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    if MAX_PRODUCTS:
        rows = rows[:MAX_PRODUCTS]
    os.makedirs(IMGDIR, exist_ok=True)
    manifest = {}
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST, encoding="utf-8"))

    bytes_total = 0
    for i, r in enumerate(rows, 1):
        pid = r["#"].strip()
        url = r["Product URL"].strip()
        if manifest.get(pid, {}).get("shots"):
            print("[%2d/%d] id=%s cached (%d shots)" % (i, len(rows), pid, len(manifest[pid]["shots"])))
            continue
        try:
            html = get(url)
        except Exception as e:
            print("[%2d/%d] id=%s PAGE FAILED %s" % (i, len(rows), pid, e))
            manifest[pid] = {"shots": [], "error": str(e)[:120]}
            continue

        # gallery images, in order, deduped
        gallery, seen = [], set()
        for g in GALLERY_RE.findall(html):
            if g not in seen:
                seen.add(g)
                gallery.append(g)
        gallery = gallery[:MAX_IMAGES]

        # every srcset width on the page, grouped by image stem
        widths = {}
        for u, w in SRCSET_RE.findall(html):
            widths.setdefault(stem(u), []).append((int(w), u))

        pdir = os.path.join(IMGDIR, "p" + pid)
        os.makedirs(pdir, exist_ok=True)
        shots = []
        for n, full in enumerate(gallery, 1):
            cands = sorted(set(widths.get(stem(full), [])))
            targets = [("main", pick(cands, 768, full)), ("thumb", pick(cands, 300, full))]
            shot = {}
            for kind, src in targets:
                ext = os.path.splitext(src.split("?")[0])[1].lower() or ".jpg"
                fname = "%d-%s%s" % (n, kind, ext)
                dest = os.path.join(pdir, fname)
                rel = "assets/img/p%s/%s" % (pid, fname)
                if os.path.exists(dest) and os.path.getsize(dest) > 0:
                    shot[kind] = rel
                    continue
                try:
                    data = get(src, binary=True)
                    open(dest, "wb").write(data)
                    shot[kind] = rel
                    nonlocal_bytes[0] += len(data)
                except Exception as e:
                    print("       image failed %s (%s)" % (src[-40:], str(e)[:50]))
            if shot.get("thumb") or shot.get("main"):
                shot.setdefault("main", shot.get("thumb"))
                shot.setdefault("thumb", shot.get("main"))
                shots.append(shot)

        manifest[pid] = {"shots": shots, "source": url}
        print("[%2d/%d] id=%s %d shots  (%.1f MB so far)"
              % (i, len(rows), pid, len(shots), nonlocal_bytes[0] / 1048576))
        json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1)
        time.sleep(DELAY)

    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1)
    withimg = len([k for k, v in manifest.items() if v.get("shots")])
    total = sum(len(v.get("shots", [])) for v in manifest.values())
    print("\nDONE — %d/%d products have images, %d shots, %.1f MB"
          % (withimg, len(rows), total, nonlocal_bytes[0] / 1048576))
    missing = [k for k, v in manifest.items() if not v.get("shots")]
    if missing:
        print("no images for ids: %s" % ", ".join(missing))


nonlocal_bytes = [0]
main()
