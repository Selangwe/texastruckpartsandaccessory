# Downloads the Ranch Hand catalogue photography into assets/img/rh/ so the V2
# templates serve it from our own folder — no hotlinking to Lippert's Cloudinary
# account, whose transform URLs we do not control and cannot keep alive.
#
# The importer records the two URLs Ranch Hand's own PDP happens to use: a 550px
# display copy and a 75px thumbnail. Neither is a size this site serves, and both
# are derivatives of one master, so this script strips the transform segment back
# to the delivery root and asks Cloudinary for the two widths our pipeline wants:
#     thumb   300w  -> product cards + PDP thumbnails
#     main    768w  -> PDP main image
#
# Every source is a square studio shot on white, so the derivatives are requested
# as c_pad onto a white square. That makes each file EXACTLY 300x300 / 768x768
# rather than "at most" — which matters, because assets/site.js publishes those
# numbers as srcset width descriptors and as the <img width> attribute. c_fit
# would quietly hand back a 735px file for the handful of small masters and turn
# both of those into lies. Padding is a no-op on an already-square master.
#
# f_jpg, not f_auto: padding onto white leaves no transparency worth preserving,
# and the couple of dozen PNG masters would otherwise land as 200KB PNGs where a
# 30KB JPEG is indistinguishable.
#
# Re-running is safe: products already in the manifest with files still on disk
# are skipped, so an interrupted run resumes where it stopped.
#
# Usage:  python build/fetch_ranchhand_images.py [max_products] [workers]
#         (or: npm run rh:images)
import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "ranchhand-products.json")
IMGDIR = os.path.join(ROOT, "assets", "img", "rh")
MANIFEST = os.path.join(IMGDIR, "manifest.json")

MAX_PRODUCTS = int(sys.argv[1]) if len(sys.argv) > 1 else 0   # 0 = all

# Most of the wall clock here is Cloudinary rendering a derivative it has never been
# asked for before -- their masters run to 6500px, and the first request for a given
# size takes the better part of ten seconds while the cached second one is instant.
# That is latency, not load, so a handful of requests in flight turns a 40-minute
# serial crawl into a few minutes without leaning on their CDN. Keep this small.
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
TIMEOUT = 60         # first-render latency, not transfer time
UA = "Mozilla/5.0 (compatible; TexasTruckParts-V2-migration/1.0)"

# .../image/upload/<any number of transform segments>/v1/<public id>
# The transform segments are what we are throwing away; the v1/... tail is the
# stable identity of the master asset.
UPLOAD_RE = re.compile(r"^(https://res\.cloudinary\.com/[^/]+/image/upload/)(?:[^/]*/)*?(v\d+/.+)$")

DERIVATIVES = (("main", 768), ("thumb", 300))


def get(url):
    """Fetch via curl. Python's ssl module rejects a CA in this machine's trust chain
    ('Basic Constraints ... not marked critical'); curl uses the system store and works.
    Verification stays ON — do not add -k here."""
    p = subprocess.run(
        ["curl", "-sL", "--fail", "--max-time", str(TIMEOUT), "-A", UA, url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if p.returncode != 0:
        raise RuntimeError("curl exit %d %s" % (p.returncode, p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout


def master(urls):
    """The one master asset behind however many sized copies the feed listed."""
    for u in urls or []:
        m = UPLOAD_RE.match(u.split("?")[0])
        if m:
            return m.group(1), m.group(2)
    return None, None


def derivative(root, public_id, width):
    return "%sc_pad,b_white,f_jpg,q_auto,w_%d,h_%d/%s" % (root, width, width, public_id)


def fetch_one(rec):
    """Downloads both derivatives for one product. Runs on a worker thread, so it
    touches nothing but its own SKU's folder and returns a (ref, entry, bytes)
    triple for the main thread to record."""
    # Keyed on the manufacturer reference, not the row index: the importer re-sorts
    # the feed on every sync, and a positional key would reassign every later
    # product's photo the first time a SKU is added or dropped.
    ref = rec.get("mfrRef")
    if not ref:
        return None, None, 0

    root, public_id = master(rec.get("imageUrls"))
    if not root:
        return ref, {"shots": [], "error": "no cloudinary url in feed"}, 0

    pdir = os.path.join(IMGDIR, ref)
    os.makedirs(pdir, exist_ok=True)
    shot, got = {}, 0
    for kind, width in DERIVATIVES:
        fname = "1-%s.jpg" % kind
        dest = os.path.join(pdir, fname)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            shot[kind] = "assets/img/rh/%s/%s" % (ref, fname)
            continue
        try:
            data = get(derivative(root, public_id, width))
        except Exception as e:
            return ref, {"shots": [], "error": str(e)[:120]}, got
        # A Cloudinary error page comes back as 200 HTML, so check the magic bytes
        # rather than trusting the status code curl --fail saw.
        if not data.startswith(b"\xff\xd8"):
            return ref, {"shots": [], "error": "not a JPEG (%d bytes)" % len(data)}, got
        # Written under a temp name and renamed so a killed run can never leave a
        # half-file that the next run's size check would happily accept.
        tmp = dest + ".part"
        open(tmp, "wb").write(data)
        os.replace(tmp, dest)
        got += len(data)
        shot[kind] = "assets/img/rh/%s/%s" % (ref, fname)

    return ref, {"shots": [shot], "source": root + public_id}, got


def main():
    if not os.path.exists(SRC):
        sys.exit("missing %s — run `npm run rh:sync` first" % SRC)
    rows = json.load(open(SRC, encoding="utf-8"))
    if MAX_PRODUCTS:
        rows = rows[:MAX_PRODUCTS]

    os.makedirs(IMGDIR, exist_ok=True)
    manifest = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}

    def cached(rec):
        shots = manifest.get(rec.get("mfrRef") or "", {}).get("shots")
        return bool(shots) and all(os.path.exists(os.path.join(ROOT, sh[k]))
                                   for sh in shots for k in ("main", "thumb"))

    todo = [r for r in rows if not cached(r)]
    print("%d products, %d already on disk, %d to fetch on %d workers"
          % (len(rows), len(rows) - len(todo), len(todo), WORKERS))

    # pool.map hands results back in feed order on this thread, so the manifest and
    # the running totals are only ever touched here -- the workers own nothing but
    # their own SKU folder, and no locking is needed.
    total, done = 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for ref, entry, got in pool.map(fetch_one, todo):
            done += 1
            total += got
            if ref is None:
                print("[%3d/%d] no mfrRef — skipped" % (done, len(todo)))
                continue
            manifest[ref] = entry
            if entry.get("shots"):
                print("[%3d/%d] %-14s ok  (%.1f MB)" % (done, len(todo), ref, total / 1048576))
            else:
                print("[%3d/%d] %-14s FAILED %s" % (done, len(todo), ref, entry.get("error")))
            # Flushed every product so a Ctrl-C costs one download, not the run.
            json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1)

    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1)
    withimg = [k for k, v in manifest.items() if v.get("shots")]
    print("\nDONE — %d/%d products have photography, %.1f MB downloaded this run"
          % (len(withimg), len(rows), total / 1048576))
    missing = sorted(k for k, v in manifest.items() if not v.get("shots"))
    if missing:
        print("no photo for: %s" % ", ".join(missing))
    print("now run `npm run data` to fold them into assets/products.js")


main()
