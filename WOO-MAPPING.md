# Texas Truck Parts V2 — WooCommerce handoff

Three templates carrying the V2 design system, built against the **live catalogue of 238
products** pulled from the store's own WooCommerce Store API. Dependency-free static
HTML/CSS/JS so the whole flow is clickable before any hosting work starts.

```
npm run sync    # pull products + images from the live store
npm run data    # regenerate assets/products.js
npm run dev     # http://127.0.0.1:8777
npm run build   # sync + data
```

---

## 1. Hosting — deploy as a child theme, not as static files

Put these templates on Hostinger as a **WooCommerce child theme** on the WordPress install.
Uploading the raw HTML would give you the design with no admin — every new product would
mean editing code, which defeats the point.

- Build and test on a **Hostinger staging subdomain** first (one-click in hPanel)
- Push to the live domain only after UAT, with the 301 redirect map from the plan's §10
- This static folder stays as the design reference / client review artifact

## 2. File map

| Static file | Woo child-theme destination |
|---|---|
| `index.html` | `front-page.php` |
| `category.html` | `archive-product.php` + `taxonomy-product_cat.php` |
| `product.html` | `single-product.php` |
| `assets/config.js` | `functions.php` — the origin comes from `home_url()`; see §10 |
| `assets/site.css` | `assets/css/site.css` — `wp_enqueue_style` |
| `assets/site.js` | `assets/js/site.js` — `wp_enqueue_script`, footer, no jQuery |
| `assets/products.js` | **replaced by Woo queries** — see §3 |
| `data/store-products.json` | prototype data only — not deployed |

## 3. Replacing the data layer

`assets/products.js` is a static snapshot of the Store API. The templates only ever read
`TTP.products`, `TTP.categories` and `TTP.ymm`, so wiring Woo means producing those three
shapes — no markup or CSS changes.

| Field | Woo source |
|---|---|
| `id` | WordPress product ID (already what the prototype uses) |
| `sku`, `name`, `price`, `regPrice`, `desc`, `url`, `slug` | core product fields |
| `save`, `savePct`, `mo` | derived — keep the formulas in `generate_products.py` |
| `inStock`, `qty` | `stock_status`, `stock_quantity` |
| `cat`, `catName` | `product_cat` term |
| `yearFrom`, `yearTo`, `makes`, `models` | `pa_year-range` attribute → `build/fitment_map.py` |
| `color`, `brand`, `side`, `condition`, `features` | parsed from the title; promote to real attributes over time |
| `images` | product gallery |

**YMM index caching:** build the year→make→model index once into a transient and invalidate
on `save_post_product` / `deleted_post`. Rebuilding it per page load would query all 238+
products every time.

## 4. Fitment — the one field that breaks silently

The store already sets a global `pa_year-range` attribute on **237 of 238** products, with
only **13 distinct terms**. `build/fitment_map.py` maps each to structured
`{yearFrom, yearTo, makes, models}`. Make is cross-checked against the product's make
category (Ford / Chevy / GMC / Ram), which the store already assigns.

A product with no Year Range term is **invisible to the YMM lookup** while looking perfectly
fine on its own page. That is the single most important thing to guard.

**Build two guardrails into the child theme:**

1. A `save_post_product` hook that raises an admin notice when Year Range is empty, plus a
   warning column in the Products list
2. Pre-select the Year Range term from the title on product creation (reuse the map in
   `fitment_map.py`) so it is confirm-not-type

**Fix these in wp-admin** — their terms carry no make, so they rely on title parsing:

| WP ID | Product | Term |
|---|---|---|
| 10071 | American Force Iceberg SS Wheels | `1999-2026` |
| 10106 | Ranch Hand Ram 1500 Sport Series Rear | `2019-2024` |
| 10079 | One Source Ford F250 Rear Replacement | `2017-2026` |
| 7948 | GMC Sierra 2500/3500 Tough Country | *(none)* |

If the store adds a Year Range term not in the map, `npm run data` prints
`!! NEW year-range terms not in build/fitment_map.py` — add it and re-run.

## 5. Adding a product after launch

No build step, no developer:

1. **Products → Add New**; keep the `YYYY-YYYY Make Model Part …` title convention (drives
   SEO, and is the fallback if an attribute is missed)
2. **Regular price** + **Sale price** — the delta drives the "Save $X · N%" badge
3. **Categories**: part type *and* make
4. **Year Range attribute** — see §4. This is the one that fails quietly
5. Photos, first image = main. Target 5–8; the catalogue currently averages 14
6. **Stock quantity** — drives "Only 1 left"
7. Publish → appears in the category grid, YMM results and related products immediately

## 6. Photography

Real photography, pulled by `build/sync_store.py` into `assets/img/<wp_product_id>/`.
Nothing hotlinks — every image is served from our own folder.

| File | Source | Used by |
|---|---|---|
| `N-thumb.jpg` | ~300w (~13 KB) | product cards, PDP thumbnails |
| `N-main.jpg` | ~768w (~78 KB) | PDP main image |

The full-size originals (~350 KB each) are deliberately not used — at 6 shots × 238
products that is ~500 MB and would sink the plan's PageSpeed 90+ / LCP <2.5s target.

**The original plan listed a missing photo library as a High-severity launch risk.** That
claim was previously recorded here as resolved, but it was only true of the *source* store's
media library — locally just 27 of 238 products had photos, so the prototype rendered
blueprint schematics for the other 211.

Resolved for real on 2026-08-17: `npm run sync` completed, giving **238 of 238 products
photos** — 2,843 files, 1,422 image pairs, 4–6 shots per product, 176 MB. Verified: zero
broken paths, all 10 category hero images resolve, no schematic fallbacks left on the
category grid. The risk now applies only to *new* intake.

**For the Woo build these files are prototype-only** — the images already live in the
WordPress media library attached to those products. What does need attention: most source
images have generic or missing alt text (an SEO gap in the plan). The templates generate
alt text from the product name.

## 7. Plugin mapping

| Feature | Woo implementation |
|---|---|
| YMM fitment lookup | Custom — meta/tax query on `pa_year-range`. Don't buy a generic YMM plugin; they assume VIN databases you don't need |
| Filter sidebar | Woo core widgets, or `WP_Query` with `tax_query` |
| Sort dropdown | Woo `orderby`; "biggest discount" needs a custom `orderby` on the sale delta |
| Financing "as low as $X/mo" | Snap / Acima / Progressive plugins; figure is `price / 12`, floored at $55 |
| Stock counter | Woo stock quantity; "Only N left" at qty ≤ 2 |
| Reviews | Woo reviews + Google Reviews widget — see §8 |
| Request a Part | Fluent Forms / WPForms → email + SMS notify |
| Product / FAQ / Breadcrumb schema | Emitted inline as JSON-LD; move to `functions.php` so Yoast doesn't duplicate it |

## 8. Placeholder vs. real

**Real:** all 238 products — names, real SKUs, prices, sale prices, stock, descriptions,
permalinks, photography, and fitment from the store's own attribute.

**Placeholder — replace before launch:**
- The three homepage reviews are **invented copy**. The live store has **0 reviews across
  all 238 products**, so the plan's social-proof gap is real. Do not ship these; collect
  real ones via the post-purchase email sequence
- Stat rail: parts count is live; 48 states / 60% / $55 come from the plan's copy
- The **street address and "Est. 2019"** still come from the scraped store — see §11

**Corrected during the build:** the brand lockup read "Est. 2007"; the store's own badge alt
text says *"Texas Truck Parts Established 2019"*, so it now reads **Est. 2019**.

## 9. Deliberate deviations from the plan

- **Stock:** the store reports 149 of 238 in stock. Per your instruction every product
  publishes as in stock — `FORCE_ALL_IN_STOCK = True` in `build/generate_products.py`.
  Set it to `False` to honour real stock.
- **Scope:** three templates rather than pre-generated pages. `category.html?cat=…` renders
  any category and `product.html?id=…` renders any of the 238, which is how Woo serves them
  anyway.
- **The CSV is no longer the source.** `texas_truck_parts_products_v2.csv` is kept for
  reference but was a 34% sample (80 of 238) and lacked SKUs, fitment and images. Everything
  now builds from `data/store-products.json`.

## 10. SEO — what the templates now do

`assets/config.js` loads first on every page and owns the site's identity.

```js
TTP.SITE = "";   // ← set to the production origin, no trailing slash
```

Empty means "use whatever origin served this page", which is right for dev and
staging and wrong for production. **Set it before launch.** Everything downstream —
canonical, `og:url`, `og:image`, JSON-LD `@id`, offer URLs, breadcrumbs — derives
from it via `TTP.origin()`, `TTP.abs()`, `TTP.productUrl()` and `TTP.categoryUrl()`.
The static `<head>` blocks carry `__SITE__` placeholders that config.js resolves, so
no domain is hardcoded in markup.

| Area | State |
|---|---|
| Headings | One `<h1>` per page. The header brand lockup is a `<span class="lockup">`, not a heading — it was previously an `<h1>` on all three templates, giving category and product pages two |
| Canonical | Homepage static; category derives from the category/make; PDP derives from the product slug |
| Robots | Indexable views `index,follow`; any filtered slice (`?fit=1`, colour, condition, price) flips to `noindex,follow` and canonicalises to its parent |
| Open Graph / Twitter | Full set on all three, rewritten per product and per category. `og:image` falls back to `assets/img/og-default.jpg` |
| LocalBusiness | `AutoPartsStore` with `@id`, geo, logo, hasMap, `areaServed`, `hasOfferCatalog`, explicit Sunday-closed |
| Product | Adds `priceValidUntil`, `hasMerchantReturnPolicy` (30 days, mirrors the FAQ), `deliveryTime`, `additionalProperty` fitment pairs, `isAccessoryOrSparePartFor`, and `seller` as an `@id` reference to the store node |
| Category | `CollectionPage` + `ItemList` (up to 30 items), emitted only on indexable views |
| Images | `TTP.shot()` offers `srcset`/`sizes` across both derivatives so a card does not download the 768w file, and numbers alt text per shot instead of repeating the product name N times. PDP hero is `eager` + `fetchpriority="high"`. It declares `width` only (thumb 300w, main 768w): heights genuinely vary — the source photos are a mix of 4:3, square and portrait — and layout is reserved by the container's `aspect-ratio` in site.css, so a declared height would be a wrong number the CSS overrides. The previous fixed `768×576` on every image was inaccurate but not a live CLS bug, since the container has always governed the box |
| Fonts | Google Fonts moved off the critical path via `media="print"` swap with a `<noscript>` fallback |

### Still open

- **`assets/img/og-default.jpg`, `logo.png`, `icon.svg`, `apple-touch-icon.png`,
  `favicon.ico` do not exist yet.** The markup references them. Produce them or the
  social previews and tab icon are broken.
- **`/shipping/` and `/returns/` pages do not exist.** Two footer links are still
  dead `#` anchors, and the PDP `hasMerchantReturnPolicy` schema asserts a 30-day
  window with no page backing it. Build both.
- **`geo` coordinates in the LocalBusiness block are the 77498 centroid**, not a
  surveyed pin. Replace with the exact lat/lng from the Google Business Profile.
- **The three homepage testimonials are still invented** (§8). They carry no review
  schema, which is the only reason this is not a rich-results violation today. Do not
  add `aggregateRating` or `Review` markup until real reviews exist.
- **FAQPage schema is retained but inert.** Google retired FAQ rich results for all
  sites on 7 May 2026. The on-page FAQ content still earns its place; the markup no
  longer buys a SERP feature. Do not add new `FAQPage` expecting one.

### The one thing that will break SEO in the Woo port

All three templates render their indexable content from JavaScript — the PDP builds
its `<h1>`, description, specs and schema in `product.html`'s inline script, and
`category.html` builds its `<h1>`, title and product grid the same way. That is fine
for a clickable prototype and **not** fine in production. `single-product.php` and
`taxonomy-product_cat.php` must emit the H1, copy, canonical, meta and JSON-LD
server-side. The JS in these files is the *specification* for those values, not the
mechanism. `assets/products.js` (1.25 MB, blocking) disappears with the port.

## 11. Domain and NAP — verify before anything ships

`texastruckparts.shop` is a **third-party site**. The prototype's catalogue was
seeded from its public Store API, so the scraped data still carries it:

| Location | Count | Action |
|---|---|---|
| `data/store-products.json` | ~14,900 | Prototype data, not deployed. Leave |
| `assets/products.js` — `p.url` | 238 | Never emitted. `TTP.productUrl()` rebuilds from `p.slug` on our own origin |
| `index.html` — `info@…` email | 0 | **Resolved.** Replaced with `Support.ranchhand@gmail.com` |
| Phone `(832) 706-8091` / `(281) 905-1053` | 0 | **Resolved.** Both replaced with `(424) 412-8976` |
| Templates — canonical / OG / schema | 0 | Cleared; all derive from `TTP.SITE` |

Phone and email are now confirmed values and live in **one place** — `TTP.CONTACT` in
`assets/config.js`. Nothing else hardcodes them.

**Still unresolved:** the street address (13618 Florence Rd, Ste D1, Sugar Land, TX 77498),
the business hours and the "Est. 2019" badge all came from the scraped store. **Name,
Address and Phone must match the Google Business Profile exactly** or the LocalBusiness
schema damages local ranking rather than helping it. Confirm the address before launch.

## 12. The Facebook catalogue (your own inventory)

A second, independent product source: the Apify `facebook-posts-scraper` export of the
page's own posts (`61585668963901`). Unlike the store API data, **these products and
photos are yours.**

```
node build/parse_facebook.js <export-file>   # -> data/facebook-products.json
node build/fetch_facebook_images.js          # -> assets/img/_facebook/
```

Also wired as `npm run fb:parse` / `npm run fb:images`.

### Results from the 2026-08-15 export

| | |
|---|---|
| Posts in export | 115 |
| Distinct products | **45** — 19 clean, 26 flagged for review |
| Reposts merged | 35 (same listing posted repeatedly; photos pooled) |
| Non-product posts | 35 (promos, disclaimers, "message for pricing") |
| Photos recovered | **344 of 355** (16.7 MB) — 11 URLs already dead |
| Products with ≥1 photo | 43 of 45 |
| Products with a price in the copy | 4 |

### Photo URLs expire — this is the thing to know

Facebook CDN links are signed and short-lived. The ones in this export carried
`oe=` expiring **2026-08-19T10:18Z**, roughly four days after the scrape. They were
downloaded in time. **Any future export must be run through `fb:images` within a few
days or the photos are unrecoverable** — the post is still on Facebook, but that
export's URLs are not.

### What the parser will not do

Facebook posts are not a product feed, so the parser classifies and flags rather than
guessing. Anything with no detectable make, no category, no photo, or signs that two
posts merged into one window is marked `needs-review` with a `reviewReason` instead of
being silently published. Review them at **`/fb-review.html`** (`npm run dev`, then
<http://127.0.0.1:8777/fb-review.html>) — it shows each extracted product beside its
actual photos, filtered by status.

Known limits, all visible in that page:
- The export is one flattened row-major line, so posts are located by permalink and a
  post that shares via a `/share/` shortlink can still merge with its neighbour. Those
  are flagged, not corrected.
- Roughly a third of the copy is bilingual (Spanish); `spanish: true` marks them.
- Prices are mostly absent — the page sells on "message for pricing", so only 4 of 45
  carry a number. Pricing has to come from you.

### Merged into one catalogue

Per your call, **both sources publish together** and every category is kept.
`generate_products.py` folds `data/facebook-products.json` into the same product shape
and writes a single `assets/products.js`:

```
npm run fb:parse   # export -> data/facebook-products.json
npm run fb:images  # photos  -> assets/img/_facebook/
npm run data       # store + facebook -> assets/products.js
```

**257 products across 13 categories** — 238 from the store API, 19 from Facebook.
Facebook products carry `source: "facebook"` so they stay identifiable, and take ids
from `FB_ID_BASE` (900000+) so they can never collide with a WordPress product id.

Three categories were added because the Facebook inventory has product types the store
catalogue does not:

| Slug | Name | Live |
|---|---|---|
| `tool-boxes` | Truck Tool Boxes | 1 |
| `running-boards` | Running Boards & Steps | 1 |
| `truck-racks` | Truck & Ladder Racks | 1 |

Facebook bumpers and grille guards merge into the existing bumper aisles rather than
duplicating them. Only `status: "ok"` rows publish — the review queue stays out of the
live catalogue until you clear it, which is why each new aisle shows 1 while the
parser found more.

**These three are universal-fit.** Tool boxes, racks and steps are sold by bed width
and cab configuration, not by make, so the parser no longer flags them for "no make" —
that rule would have parked the whole accessories side of the catalogue in review
permanently.

### "Call for price"

Most Facebook listings sell on *message for pricing*, so `price` is `null` — not `0`.
Showing "$0" on a $1,200 bumper is worse than showing no number. So:

- cards and the PDP render **"Call for price"** with the financing line replaced by a
  call-to-quote
- `Product` schema emits `availability` and `seller` but **no `price` node** — an Offer
  with a fabricated price would be worse than one that cannot win price-based rich
  results
- 17 of the 19 live Facebook products are in this state; pricing has to come from you

### Photos

Facebook photos are a single derivative at assorted sizes (mostly ~590w, some
portrait), not a thumb/main pair. So the generator **measures each JPEG's real
dimensions** at build time and `TTP.shot()` emits those, and it suppresses `srcset`
when the two derivatives are the same file rather than claiming one URL is two widths.

### The two catalogues are still different businesses

Worth keeping in view even though they now ship together: the Facebook inventory is
bumper-led with no tailgates, tail lights, wheels or truck beds — categories that make
up much of the 238-product store-API set. Merging them is a presentation decision; it
does not make the scraped products yours.

## 13. The cart — order-by-message, not order-by-payment

`assets/cart.js` + `cart.html` add a real order path that fits a static site: a localStorage
cart whose checkout **composes the order as plain text and hands it to WhatsApp or email as a
draft the customer sends.** No payment is taken and no total is invented.

That is not a compromise so much as a match for the inventory. 17 of 257 products carry no
price at all, freight on a $3,500 truck bed depends on a residential-vs-commercial address and
a liftgate, and every take-off wants a VIN check before it ships. All three need a human in the
loop, so the flow ends in a conversation rather than a card form.

| Piece | Where |
|---|---|
| Cart state, message builder, drawer, chat widget | `assets/cart.js` |
| Review → details → sent | `cart.html` |
| Phone / WhatsApp / email / pricing line | `TTP.CONTACT` in `assets/config.js` |
| Drawer, widget, cart-line, quick-add styles | `assets/site.css` |

**Rules the catalogue forced:**
- Only `id` + `qty` are persisted; every price, name and stock figure is re-read from
  `TTP.products` on access, so a week-old cart can never quote a stale price
- Quantities clamp to `p.qty` — the whole catalogue is 1-of-1 and 2-of-2 take-offs
- Unpriced items are orderable but excluded from the subtotal, which is labelled with its
  own item count; `$0` is never rendered
- Freight (≥ $1,500) is marked per line and never totalled
- Cart money is exact to the cent, unlike `TTP.money`'s whole-dollar browse rounding —
  `TTP.money2()` in `cart.js`
- The cart is **not** cleared when the handoff fires. A static page cannot confirm delivery,
  so only an explicit "Start a new order" clears it

**WhatsApp link forms — they are not interchangeable.** `wa.me/<number>?text=…` carries a
prefilled message; the Business short link `wa.me/message/<CODE>` opens the same inbox but
silently drops `?text=`. The order handoff must always use the number form. The short link is
used only for the bare chat bubble, where there is nothing to prefill.

### Porting to WooCommerce

`TTP.cart` reads only `TTP.products`, so it maps onto Woo's cart the same way the templates map
onto its queries. The natural port is Woo's own cart/checkout with the message handoff kept as a
*secondary* CTA — "send this order on WhatsApp" beside "pay now" — since a good share of this
customer base would rather message than fill in a card form.

## 14. Pre-launch: the site is deliberately not indexable

`vercel.json` serves **`X-Robots-Tag: noindex, nofollow` on every route**, and `robots.txt`
explains why. The site currently runs on `texastruckpartsandaccessory.vercel.app` with no custom
domain, and `index.html` publishes LocalBusiness structured data with a street address still
inherited from the scraped store (§11). Being indexed in that state puts ranking signals on a host
that gets abandoned, under an address that may be wrong.

Note the crawl is **allowed**. `Disallow: /` would stop crawlers fetching the pages and therefore
stop them reading the noindex header, which is how URLs end up indexed as bare titles that are then
awkward to remove. Allow the crawl, serve noindex.

`TTP.SITE` is now set to `https://texastruckpartsandaccessory.vercel.app` rather than left empty,
so a page reachable at a preview deployment URL still declares the production URL canonical instead
of competing with itself.

### ⚠ Canonicals currently point at URLs that do not exist

`TTP.PATHS` describes the **WooCommerce** permalink structure — `/product/<slug>/`,
`/product-category/<slug>/`, `/shop/`. The static site does not serve those; it serves
`product.html?id=…` and `category.html?cat=…`. So every canonical, `og:url`, JSON-LD `@id`,
`offers.url` and breadcrumb currently names a URL that returns **404**:

| Emitted as canonical | Actually serves |
|---|---|
| `/product/2020-2022-ford-f250…/` → 404 | `/product.html?id=10452` → 200 |
| `/product-category/truck-bed/` → 404 | `/category.html?cat=truck-bed` → 200 |
| `/shop/` → 404 | `/category.html` → 200 |

This is **inert while the site is noindex** — nothing is crawling to believe it. It becomes
actively destructive the moment indexing is switched on without the Woo port, because every page
would be telling Google its real version lives somewhere that 404s, and Google drops pages whose
canonical target does not resolve.

Two ways out, and the choice depends on whether this static site or WooCommerce is the real
destination:

- **Static site is the destination** — either point `TTP.PATHS` at the real URLs
  (`product.html?id=`), which makes canonicals truthful immediately but leaves query-string URLs,
  or add Vercel rewrites so `/product/<slug>/` genuinely serves `product.html` and the page reads
  the slug instead of an id. The rewrite route gives clean URLs *and* correct canonicals.
- **WooCommerce is the destination** — leave `TTP.PATHS` alone; the paths become real when the
  templates land in the child theme. Just do not lift the noindex before that happens.

**Launch checklist — in order:**

1. Point the custom domain at the Vercel project
2. Update `TTP.SITE` in `assets/config.js` to that domain
3. **Resolve the canonical/permalink mismatch above** — canonicals must resolve to live URLs
4. Verify the street address against the Google Business Profile, then delete the `headers` block
   from `vercel.json` and replace `robots.txt` with a real one plus a sitemap

## 15. Still not built

Payment capture, accounts & order tracking, abandoned-cart recovery, back-in-stock alerts,
product comparison, wholesale tier, blog — all Woo plugin or Phase-2 work per the plan's own
priority list, none of which affects the design system above.
