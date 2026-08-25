# Builds data/ranchhand-products.json from an already-harvested Algolia dump, without
# touching the network.
#
# sync_ranchhand.py does the live harvest and is the tool to use for a refresh. This one
# exists because the reconnaissance pass already pulled the complete 283-product index,
# and re-running ~283 paced requests against an origin that 5xxs 40% of the time to
# re-fetch data we already hold would be rude and pointless.
#
# It shares sync_ranchhand's classification rules by importing them, so the category
# mapping can never drift between the two paths.
#
# Inputs (from the reconnaissance scratchpad, passed on the command line):
#   alg_all.json   — the full Algolia index: 283 hits, 16 fields each
#   sample15.json  — 15 products with their PDP spec accordion parsed out
#
# Usage:  python build/import_ranchhand_dump.py <alg_all.json> [sample15.json]
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from sync_ranchhand import BRAND, SERIES, classify, coerce, NULL_SENTINEL

OUT = os.path.join(ROOT, "data", "ranchhand-products.json")


def price_of(hit):
    p = hit.get("price")
    if isinstance(p, dict):
        return p.get("USD", {}).get("default")
    return p


def clean_specs(raw):
    """Same contract as sync_ranchhand.parse_specs: '--' means unknown, not false.
    Returns (specs, unknown-labels)."""
    specs, unknown = {}, []
    for label, value in (raw or {}).items():
        v = str(value).strip()
        if v.lower() in NULL_SENTINEL:
            unknown.append(label)
            continue
        specs[label] = v
    return coerce(specs), unknown


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python build/import_ranchhand_dump.py <alg_all.json> [sample15.json]")

    dump = json.load(open(sys.argv[1], encoding="utf-8"))
    hits = dump.get("hits") if isinstance(dump, dict) else dump
    print("algolia dump: %d records" % len(hits))

    # Specs only exist for the products the recon pass opened individually. Keyed on the
    # model code, which is the join key everywhere in this pipeline.
    specs_by_ref = {}
    if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
        for s in json.load(open(sys.argv[2], encoding="utf-8")):
            ref = (s.get("model_code") or "").strip()
            if ref:
                specs_by_ref[ref] = s
        print("spec sample: %d products" % len(specs_by_ref))

    products, review = [], []
    for h in hits:
        ref = (h.get("manufacturer_ref_num") or "").strip()
        name = (h.get("name") or "").strip()

        # categories_without_path holds the real product type ("Ranch Hand Full Bumpers");
        # the nested `categories` object is the merchandising tree and mixes in
        # collections, so it is only a fallback.
        cats = h.get("categories_without_path") or []
        slug, why = classify(name, cats)

        sample = specs_by_ref.get(ref, {})
        specs, unknown = clean_specs(sample.get("specs"))

        rec = {
            "mfrRef": ref or None,
            "magentoSku": str(h.get("sku") or "").strip() or None,
            "name": name,
            "url": h.get("url") or "",
            "cat": slug,
            "brand": BRAND,
            "series": (sample.get("series")
                       or next((x for x in SERIES if re.search(r"\b%s\b" % x, name, re.I)), None)),
            "price": price_of(h),
            "inStock": bool(h.get("in_stock", 1)),
            "universal": (h.get("universal_part") or "").strip().lower() == "yes",
            "upc": sample.get("upc") or specs.get("UPC"),
            "sourceCategory": cats[0] if cats else None,
            # Recorded, not downloaded. Photography is a separate, licensed step.
            "imageUrls": [u for u in [h.get("image_url"), h.get("thumbnail_url")] if u],
            "specs": specs,
            "specsUnknown": unknown,
            "fitment": [],
            "needsReview": why,
        }
        if why:
            review.append(rec)
        products.append(rec)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(products, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    print("\nwrote %s" % OUT)
    print("  %d products, %d flagged for review" % (len(products), len(review)))

    by_cat = {}
    for p in products:
        k = p["cat"] or "(review)"
        by_cat[k] = by_cat.get(k, 0) + 1
    for c, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print("    %-28s %d" % (c, n))

    withspecs = sum(1 for p in products if p["specs"])
    print("\n  %d of %d have specs (the rest need `npm run rh:sync` to fill in)"
          % (withspecs, len(products)))
    print("  %d spec rows held as unknown rather than coerced to false"
          % sum(len(p["specsUnknown"]) for p in products))
    if review:
        print("\n  flagged (no category rule matched):")
        for r in review[:12]:
            print("    %-14s %s" % (r["mfrRef"] or "?", r["name"][:64]))


if __name__ == "__main__":
    main()
