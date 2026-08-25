# Harvests the Ranch Hand catalogue (factual data only) into data/ranchhand-products.json.
#
# Ranch Hand is a line we already resell — the catalogue carries SBD19HBLSL, MFD101BMN and
# the TTP-FB-* listings — but the aftermarket categories are nearly empty. This fills them:
# 283 products against the 45 currently spread over five aftermarket slugs.
#
# WHAT THIS TAKES AND WHAT IT DOES NOT
#   Takes: part numbers, UPCs, prices, weights, materials, finishes, retention flags,
#          series, category. Facts.
#   Records but does NOT download: image URLs. Product photography comes through the
#          dealer media portal (portal.cloudinary.com/lci-cloudinary/ranchhandmedia),
#          not from here.
#   Never takes: descriptions, taglines, bullet copy, testimonials. Listing copy is
#          written fresh.
#
# THREE SOURCES, because no single one has everything:
#   1. Sitemap  — the authoritative product list. robots.txt declares it at a
#                 non-standard path; /sitemap.xml itself 404s. 379 urls, 283 products.
#   2. Algolia  — every field in one POST. Credentials are published in
#                 window.algoliaConfig on each product page. The key is a SECURED key
#                 whose validUntil is ~24h out, so it is re-read from a live page every
#                 run rather than cached. Do not hardcode it.
#   3. PDP HTML — the spec accordion. Magento's custom_attributesV2 GraphQL field is
#                 broken server-side (returns Internal server error), so this is the
#                 only route to specs.
# Fitment is a separate stage (sync_ranchhand_fitment.py) — inverting VSP's
# vehicle->product index into product->vehicle costs ~1,200 cacheable calls.
#
# Re-running is safe and resumable: products already in the output are skipped unless
# --refresh is passed.
#
# Usage:  python build/sync_ranchhand.py [--limit N] [--refresh]
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "ranchhand-products.json")

BASE = "https://www.ranchhand.com"
# robots.txt declares the sitemap here; /sitemap.xml and /sitemap_index.xml both 404.
SITEMAP = BASE + "/media/sitemap-ranchhand-magento/sitemap.xml"
ALGOLIA_INDEX = "gwp_d2c_prod_ranchhand_products"

TIMEOUT = 45
# Roughly 40% of requests return 500/504 from origin/cache instability — not blocking
# (no Cloudflare, no CAPTCHA, no 429, never challenged, no UA sniffing). Pacing at 2.5s+
# measurably reduced the failure rate versus 0.6s, so slow is genuinely faster here.
DELAY = 2.5
RETRIES = 5
UA = "Mozilla/5.0 (compatible; TexasTruckParts-catalogue/1.0)"

# Product URLs are root-level with the Magento SKU as a 10-digit suffix:
#   /ranch-hand-fbc201blr-legend-front-bumper-with-grille-guard-2023108573
# Match the suffix, not the slug — slug forms are inconsistent across the catalogue.
PRODUCT_URL_RE = re.compile(r"^https://www\.ranchhand\.com/[a-z0-9-]+-(\d{10})/?$", re.I)

# Series lines, read off the product name. Legend 154, Midnight 40, Summit 36, Sport 30.
SERIES = ["Legend", "Midnight", "Summit", "Sport"]
BRAND = "Ranch Hand"

# Ranch Hand product families -> our category slugs (build/generate_products.py CATEGORIES).
# Every slug already exists on the site with SEO copy written, so nothing new is created.
#
# ORDER MATTERS — first match wins, so specific patterns precede the generic "bumper"
# catch-all. A Legend front bumper WITH an integrated grille guard files under bumpers,
# which is why the front-bumper test runs before the grille-guard one.
#
# Their counts: Front 90, Grille Guards 62, Running Steps 44, Rear 39, Accessories 33,
# Headache Racks 13, Mud Flaps 11 (sums to 292 vs 283 — 9 products are dual-category).
CAT_RULES = [
    (r"mud\s*flap|splash\s*guard",                        "accessories-hardware"),
    (r"headache\s*rack|head\s*ache|cab\s*rack|ladder",    "truck-racks"),
    (r"running\s*step|side\s*step|nerf|step\s*bar|steps?\b", "running-boards"),
    (r"rear\s*bumper|back\s*bumper",                      "rear-replacement-bumpers"),
    (r"front\s*bumper|bull\s*nose|winch",                 "front-replacement-bumpers"),
    (r"grille?\s*guard|brush\s*guard",                    "grill-guards"),
    (r"bumper",                                           "front-replacement-bumpers"),
    (r"light|bracket|hitch|accessor",                     "accessories-hardware"),
]

# The spec accordion uses "--" as its null sentinel. Coercing that to False would publish
# a positive claim that a part does NOT retain parking sensors or camera function — a
# fitment claim a buyer acts on, and one we would be asserting without evidence. Unknown
# stays unknown: the row is dropped and the listing simply omits it.
NULL_SENTINEL = {"--", "-", "", "n/a", "na", "none"}

BOOL_TRUE = {"yes", "true", "y"}
BOOL_FALSE = {"no", "false", "n"}


def curl(url, binary=False, headers=None, post=None):
    """Fetch via curl. Python's ssl module rejects a CA in this machine's trust chain
    ('Basic Constraints ... not marked critical'); curl uses the system store and works.
    Verification stays ON — do not add -k here.

    Retries on transport failure AND on a short body, because ranchhand.com returns
    intermittent 500/504s that an exit-code check alone would let through as
    success-with-no-data. Without body validation ~15% of the catalogue vanishes
    silently."""
    cmd = ["curl", "-sL", "--max-time", str(TIMEOUT), "-A", UA]
    for k, v in (headers or {}).items():
        cmd += ["-H", "%s: %s" % (k, v)]
    if post is not None:
        cmd += ["-X", "POST", "--data-binary", post]
    cmd.append(url)

    last = ""
    for attempt in range(RETRIES):
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        body = p.stdout if binary else p.stdout.decode("utf-8", "replace")
        if p.returncode == 0 and len(body) > 400:
            return body
        last = "exit %d, %d bytes" % (p.returncode, len(body))
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("curl failed after %d tries (%s): %s" % (RETRIES, last, url))


def sitemap_products():
    """The 283 product URLs keyed by Magento SKU, straight from the sitemap.

    Used to cross-check the Algolia result: if the two disagree the catalogue changed
    mid-run, and importing the smaller set silently would drop products with no error."""
    xml = curl(SITEMAP)
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
    out = {}
    for u in urls:
        m = PRODUCT_URL_RE.match(u.strip())
        if m:
            out[m.group(1)] = u.strip()
    print("  sitemap: %d urls, %d products" % (len(urls), len(out)))
    return out


def algolia_credentials(seed_url):
    """Read app id + secured API key off a live product page.

    The key base64-decodes to a validUntil roughly 24 hours out, so a cached copy
    silently starts returning auth errors the next day. Always read it fresh."""
    html = curl(seed_url)
    m = re.search(r"window\.algoliaConfig\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        raise RuntimeError("algoliaConfig not found on %s — page structure changed" % seed_url)
    cfg = json.loads(m.group(1))
    app = cfg.get("applicationId") or cfg.get("appId")
    key = cfg.get("apiKey")
    if not app or not key:
        raise RuntimeError("algoliaConfig present but missing applicationId/apiKey")
    print("  algolia app=%s key=%s..." % (app, key[:12]))
    return app, key


def fetch_catalogue(app, key):
    """One POST per 1000 hits. The catalogue is ~283 products, so this is a single call."""
    out, page = [], 0
    while True:
        url = "https://%s-dsn.algolia.net/1/indexes/%s/query" % (app, ALGOLIA_INDEX)
        body = json.dumps({"params": "hitsPerPage=1000&page=%d" % page})
        res = json.loads(curl(url, headers={
            "X-Algolia-Application-Id": app,
            "X-Algolia-API-Key": key,
            "Content-Type": "application/json",
        }, post=body))
        hits = res.get("hits", [])
        out.extend(hits)
        print("  page %d: %d hits (%d of %s)" % (page, len(hits), len(out), res.get("nbHits", "?")))
        page += 1
        if page >= res.get("nbPages", 1):
            break
        time.sleep(DELAY)
    return out


def classify(name, algolia_cats):
    """Map to one of our existing slugs. The product name wins over Algolia's category
    facet, because that facet mixes merchandising collections ('New', 'Best Sellers')
    with real product types. Anything unmatched is flagged for review rather than
    guessed into a category — same philosophy as parse_facebook.js."""
    hay = (name or "").lower()
    for pattern, slug in CAT_RULES:
        if re.search(pattern, hay):
            return slug, None
    for c in algolia_cats or []:
        cl = str(c).lower()
        for pattern, slug in CAT_RULES:
            if re.search(pattern, cl):
                return slug, None
    return None, "no category rule matched name or facets"


def parse_specs(html):
    """The spec block is a flat Label/Value list inside an Alpine accordion
    (data-ref="accordion-key-2"), not a <table>. Returns ({label: value}, [unknown]),
    with "--" rows collected separately rather than coerced to a boolean."""
    block = html
    m = re.search(r'data-ref="accordion-key-2".*?>(.*?)(?:</section>|</div>\s*</div>\s*</div>)',
                  html, re.S)
    if m:
        block = m.group(1)

    specs, unknown = {}, []
    for lm in re.finditer(r">\s*([A-Z][A-Za-z0-9 /()'.&-]{2,60}?)\s*:?\s*<[^>]*>\s*([^<>]{1,120}?)\s*<",
                          block):
        label = re.sub(r"\s+", " ", lm.group(1)).strip().rstrip(":")
        value = re.sub(r"\s+", " ", lm.group(2)).strip()
        if not label or label in specs or label in unknown:
            continue
        if value.lower() in NULL_SENTINEL:
            unknown.append(label)          # unknown, NOT false — see NULL_SENTINEL
            continue
        specs[label] = value
    return specs, unknown


def coerce(specs):
    """Normalise the fields the templates read. Everything else carries through verbatim
    so nothing is lost if a template starts using it later."""
    out = {}
    for label, value in specs.items():
        v = value.strip()
        low = v.lower()
        if low in BOOL_TRUE:
            out[label] = True
        elif low in BOOL_FALSE:
            out[label] = False
        else:
            num = re.match(r'^([\d,]+(?:\.\d+)?)\s*(lbs?|pounds?|in(?:ches)?|")?$', v, re.I)
            out[label] = float(num.group(1).replace(",", "")) if num else v
    return out


def price_of(hit):
    """Algolia nests price under price.USD.default on this index, but falls back to a
    flat number on some records."""
    p = hit.get("price")
    if isinstance(p, dict):
        return p.get("USD", {}).get("default")
    return p


def main():
    argv = sys.argv[1:]
    refresh = "--refresh" in argv
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 0

    os.makedirs(DATA, exist_ok=True)
    existing = {}
    if os.path.exists(OUT) and not refresh:
        existing = {p["mfrRef"]: p
                    for p in json.load(open(OUT, encoding="utf-8")) if p.get("mfrRef")}
        print("resuming: %d products already harvested" % len(existing))

    print("reading sitemap...")
    sm = sitemap_products()
    if not sm:
        raise RuntimeError("sitemap yielded no product urls — path or format changed")

    print("reading algolia credentials from a live product page...")
    app, key = algolia_credentials(next(iter(sm.values())))

    print("fetching catalogue...")
    hits = fetch_catalogue(app, key)

    # Reconcile. The sitemap is authoritative for existence, Algolia for field values.
    # A gap either way means the catalogue moved under us; it is reported rather than
    # quietly resolved in favour of whichever set happens to be smaller.
    algolia_skus = {str(h.get("sku") or "").strip() for h in hits}
    missing = set(sm) - algolia_skus
    print("  reconcile: sitemap=%d algolia=%d | sitemap-only=%d | algolia-only=%d"
          % (len(sm), len(algolia_skus), len(missing), len(algolia_skus - set(sm))))
    if missing:
        print("    WARNING sitemap-only skus, no algolia record, skipped: %s"
              % ", ".join(sorted(missing)[:10]))

    if limit:
        hits = hits[:limit]

    products, review = [], []
    for i, h in enumerate(hits, 1):
        # The Magento SKU is an internal number (2023108573); manufacturer_ref_num is the
        # real model code (FBC201BLR) and the ONLY key that joins to VSP fitment and to
        # the Ranch Hand rows already in our catalogue (SBD19HBLSL, MFD101BMN).
        ref = (h.get("manufacturer_ref_num") or "").strip()
        name = (h.get("name") or "").strip()
        sku = str(h.get("sku") or "").strip()
        url = h.get("url") or sm.get(sku, "")

        if ref and ref in existing:
            products.append(existing[ref])
            continue

        slug, why = classify(name, h.get("categories") or h.get("categories_without_path"))

        rec = {
            "mfrRef": ref or None,
            "magentoSku": sku or None,
            "name": name,
            "url": url,
            "cat": slug,
            # Set explicitly rather than left to generate_products.py's name-matching:
            # a name like "FBC201BLR Legend Front Bumper" carries no brand token, so
            # name-derivation would file it with no brand at all.
            "brand": BRAND,
            "series": next((x for x in SERIES if re.search(r"\b%s\b" % x, name, re.I)), None),
            "price": price_of(h),
            "inStock": bool(h.get("in_stock", True)),
            # URLs recorded for later; files are NOT downloaded here. Photography comes
            # through the dealer media portal.
            "imageUrls": [u for u in [h.get("image_url"), h.get("thumbnail_url")] if u],
            "specs": {},
            "specsUnknown": [],
            "fitment": [],            # filled by sync_ranchhand_fitment.py
            "needsReview": why,
        }

        if url:
            try:
                html = curl(url)
                specs, unknown = parse_specs(html)
                rec["specs"] = coerce(specs)
                rec["specsUnknown"] = unknown
                if not rec["mfrRef"]:
                    m = re.search(r"Manufacturer Reference Number[^A-Z0-9]{0,20}([A-Z0-9-]{4,20})", html)
                    if m:
                        rec["mfrRef"] = m.group(1)
                time.sleep(DELAY)
            except RuntimeError as e:
                rec["needsReview"] = (rec["needsReview"] or "") + " | spec fetch failed: %s" % e

        if rec["needsReview"]:
            review.append(rec)
        products.append(rec)
        print("  [%d/%d] %-14s %-48s %s"
              % (i, len(hits), rec["mfrRef"] or "?", name[:48], rec["cat"] or "REVIEW"))

    json.dump(products, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    print("\nwrote %s" % OUT)
    print("  %d products, %d need review" % (len(products), len(review)))
    by_cat = {}
    for p in products:
        k = p["cat"] or "(review)"
        by_cat[k] = by_cat.get(k, 0) + 1
    for c, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print("    %-28s %d" % (c, n))
    unknown_total = sum(len(p["specsUnknown"]) for p in products)
    print("  %d spec rows left unknown rather than coerced to false" % unknown_total)
    print("  %d image urls recorded, 0 downloaded (dealer media step)"
          % sum(len(p["imageUrls"]) for p in products))


if __name__ == "__main__":
    main()
