# Syncs the full catalogue from the live store's public WooCommerce Store API and
# downloads product photography into assets/img/<wp_product_id>/.
#
# Replaces the old CSV + HTML-scraping pipeline. The Store API needs no auth and returns
# stable WordPress product IDs, real SKUs, prices, stock, categories, attributes (including
# the pa_year-range fitment attribute) and full image lists.
#
# Everything is keyed on the WordPress product id, which never shifts — unlike the CSV's
# row number, where inserting one product silently reassigned every later product's photos.
#
# Re-running is safe and resumable: images already on disk are skipped.
#
# Usage:  python build/sync_store.py [max_images_per_product]
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
IMGDIR = os.path.join(ROOT, "assets", "img")
PRODUCTS_JSON = os.path.join(DATA, "store-products.json")
MANIFEST = os.path.join(IMGDIR, "manifest.json")

API = "https://texastruckparts.shop/wp-json/wc/store/v1/products"
PER_PAGE = 100
MAX_IMAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 6
TIMEOUT = 40
DELAY = 0.25
UA = "Mozilla/5.0 (compatible; TexasTruckParts-V2-migration/1.0)"


def curl(url, binary=False):
    """Fetch via curl. Python's ssl module rejects a CA in this machine's trust chain
    ('Basic Constraints ... not marked critical'); curl uses the system store and works.
    Verification stays ON — do not add -k here."""
    p = subprocess.run(
        ["curl", "-sL", "--fail", "--max-time", str(TIMEOUT), "-A", UA, url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if p.returncode != 0:
        raise RuntimeError("curl exit %d %s" % (p.returncode, p.stderr.decode("utf-8", "replace")[:80]))
    return p.stdout if binary else p.stdout.decode("utf-8", "replace")


def fetch_catalogue():
    out, page = [], 1
    while True:
        url = "%s?per_page=%d&page=%d" % (API, PER_PAGE, page)
        batch = json.loads(curl(url))
        if not batch:
            break
        out.extend(batch)
        print("  page %d: %d products (%d total)" % (page, len(batch), len(out)))
        if len(batch) < PER_PAGE:
            break
        page += 1
        time.sleep(DELAY)
    return out


def pick_main(img):
    """Prefer a ~768w variant from the API's srcset; fall back to the full-size src.
    Full originals are ~350KB each, which would blow the plan's PageSpeed target."""
    best, srcset = None, img.get("srcset") or ""
    for part in srcset.split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w"):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                continue
            if 700 <= w <= 900 and (best is None or w < best[0]):
                best = (w, bits[0])
    return best[1] if best else img.get("src")


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(IMGDIR, exist_ok=True)

    print("Fetching catalogue from the Store API…")
    products = fetch_catalogue()
    json.dump(products, open(PRODUCTS_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("wrote %s (%d products)\n" % (PRODUCTS_JSON, len(products)))

    manifest = {}
    if os.path.exists(MANIFEST):
        try:
            manifest = json.load(open(MANIFEST, encoding="utf-8"))
        except Exception:
            manifest = {}

    total_bytes, downloaded = 0, 0
    for i, p in enumerate(products, 1):
        pid = str(p["id"])
        images = (p.get("images") or [])[:MAX_IMAGES]
        pdir = os.path.join(IMGDIR, pid)
        os.makedirs(pdir, exist_ok=True)

        shots = []
        for n, img in enumerate(images, 1):
            targets = [("main", pick_main(img)), ("thumb", img.get("thumbnail") or img.get("src"))]
            shot = {}
            for kind, src in targets:
                if not src:
                    continue
                ext = os.path.splitext(src.split("?")[0])[1].lower() or ".jpg"
                fname = "%d-%s%s" % (n, kind, ext)
                dest = os.path.join(pdir, fname)
                rel = "assets/img/%s/%s" % (pid, fname)
                if os.path.exists(dest) and os.path.getsize(dest) > 0:
                    shot[kind] = rel
                    continue
                try:
                    data = curl(src, binary=True)
                    open(dest, "wb").write(data)
                    shot[kind] = rel
                    total_bytes += len(data)
                    downloaded += 1
                except Exception as e:
                    print("       image failed %s (%s)" % (src[-38:], str(e)[:44]))
            if shot:
                shot.setdefault("main", shot.get("thumb"))
                shot.setdefault("thumb", shot.get("main"))
                shots.append(shot)

        manifest[pid] = {"shots": shots, "source": p.get("permalink")}
        if i % 10 == 0 or i == len(products):
            print("[%3d/%d] id=%-6s %d shots  (%d new files, %.1f MB)"
                  % (i, len(products), pid, len(shots), downloaded, total_bytes / 1048576))
            json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1)

    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1)
    withimg = len([k for k, v in manifest.items() if v.get("shots")])
    print("\nDONE — %d products, %d with images, %d new files, %.1f MB downloaded"
          % (len(products), withimg, downloaded, total_bytes / 1048576))
    missing = [k for k, v in manifest.items() if not v.get("shots")]
    if missing:
        print("no images for ids: %s" % ", ".join(missing[:20]))


main()
