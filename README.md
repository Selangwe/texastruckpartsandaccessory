# Texas Truck Parts & Accessory

Storefront for a truck parts yard — OEM take-offs, Ranch Hand bumpers and grille
guards, wheels, racks and bed accessories. 540 products across 13 categories.

**Production:** https://texastruckpartsandaccessory.vercel.app

---

## Architecture: static files, no build step

Four hand-authored HTML pages, one stylesheet, four scripts, and a generated
data file. There is no framework, no bundler, no transpiler, and nothing to
compile before deploying. Vercel serves the repo root as-is
(`outputDirectory: "."`, `buildCommand: ""`).

```
index.html          home
category.html       serves /shop/ and every /product-category/<slug>/
product.html        serves every /product/<slug>/
cart.html           cart + checkout hand-off

assets/
  config.js         loaded FIRST, in <head>. Site identity: origin, contact,
                    permalink builders, canonical helpers.
  products.js       GENERATED. TTP.products, TTP.categories, TTP.ymm.
  site.js           shared chrome: header, fitment bar, cards, hero reel.
  cart.js           cart state (localStorage) and the order form.
  site.css          the whole design system, ~640 lines.
  img/              product photography, ~3,700 files. Also img/pay/ (payment marks).
  video/            hero reel + its poster frame.

build/              local tooling. Python + Node. NOT deployed.
data/               source JSON from the importers. NOT deployed.
sitemap.xml         GENERATED alongside products.js.
```

The three pages that serve many URLs do it through Vercel rewrites, not through
generated files — `category.html` and `product.html` each read the slug out of
`location.pathname` and render client-side. So there are 540 product URLs but
only one product page on disk.

## Getting started

```bash
npm run dev     # http://127.0.0.1:8777
```

**Use this server, not another one.** `build/dev-server.js` implements HTTP Range
requests (`206 Partial Content`). Safari and iOS refuse to play a `<video>` from
a server that does not, so under `python -m http.server` or similar the hero reel
looks broken locally while being perfectly fine in production. Vercel supports
Range natively.

## The data pipeline

`assets/products.js` is generated and should never be hand-edited.

```
data/store-products.json      ─┐
data/facebook-products.json   ─┼─→  build/generate_products.py  ─→  assets/products.js
data/ranchhand-products.json  ─┘                                └─→  sitemap.xml
```

| script | does |
|---|---|
| `npm run data` | regenerate `assets/products.js` + `sitemap.xml` from `data/` |
| `npm run sync` | pull the store feed |
| `npm run fb:parse` / `fb:images` | parse the Facebook export, fetch its photos |
| `npm run rh:sync` / `rh:images` | pull the Ranch Hand catalogue and photos |
| `npm run build` | `sync` → `fb:parse` → `data` |

The generator also does merchandising: it fills missing prices from category
medians, applies discounts subject to a floor, and marks a share out of stock. It
is seeded by date, so a rerun on the same day is reproducible.

### Slugs are deduplicated, and that matters

The upstream feeds hand back colliding slugs — 49 of them were shared by 2 to 7
products, which stranded 86 products on permalinks that resolved to a sibling.
`dedupe_slugs()` appends `-2`, `-3`, … to later collisions. **The first occurrence
always keeps its slug**, so regenerating never changes a URL that already worked.
Do not remove that guarantee: these URLs are indexed.

## URLs and canonicals

`TTP.SITE` in `assets/config.js` is the single source of truth for the origin.
Canonicals, `og:url`, `og:image`, JSON-LD `@id`, offer URLs and breadcrumbs all
derive from it, and so does the sitemap — the generator regexes it back out of
`config.js` rather than hardcoding a domain.

> **`texastruckparts.shop` is a THIRD-PARTY site, not ours.** The imported feeds
> carry that domain in their permalink fields. It must never be emitted as a
> canonical, a schema offer URL, or a footer link — doing so points our SEO
> signals at somebody else's site. The `url` field is stripped from the shipped
> data for exactly this reason.

Permalinks are built by helpers in `config.js` (`TTP.productPath`,
`TTP.categoryPath`, `TTP.productUrl`) so the URL a page *links to* and the URL it
*declares canonical* cannot drift apart. `vercel.json` sets `trailingSlash: true`;
every generated URL carries the slash to avoid a redirect hop.

## Caching

`vercel.json` marks `/assets/img/**` and `/assets/video/**` `immutable` for a
year. Those trees are content-addressed by product id — a file at a given path is
never edited, only added or removed.

**The code files are deliberately excluded from that.** `products.js`, `site.js`,
`site.css`, `config.js` and `cart.js` are regenerated on deploy and carry no
content hash in their filenames, so a long `max-age` would pin returning visitors
to stale code with no way to bust it. They keep the revalidating default. If you
ever add hashed filenames, revisit this.

## What is deliberately not deployed

`.vercelignore` keeps `build/`, `data/`, `*.csv`, `*.md` and `.claude/` out of the
bundle, along with two internal pages (the V2 planning document and the Facebook
parse QA tool) that were previously reachable and indexable by anyone who guessed
the URL. It also excludes the two image-fetcher `manifest.json` files, which are
build bookkeeping nothing at runtime reads.

There is a note in that file about the ~10.5 MB of orphaned scrape images in
`assets/img/_facebook/` and why they are *not* listed — read it before adding
them.

## Cart and checkout

The cart lives in `localStorage` and the checkout does not take payment. It
collects the order and hands off to a human, with the payment method chosen from
`TTP.PAYMENTS` in `assets/cart.js` (Zelle, Venmo, Apple Pay, Crypto, bank
transfer, or "not sure yet").

Note that the footer payment marks and `TTP.PAYMENTS` are maintained separately
and currently differ: the footer advertises Visa, Mastercard and Google Pay,
which the checkout does not offer as selectable options. If you change one, check
the other — and the `paymentAccepted` list in the homepage JSON-LD, which is a
third copy.

## Conventions

- **ES5 syntax, modern APIs.** No transpiler, so no arrow functions or `let` in
  shipped code — but `IntersectionObserver`, `URLSearchParams`, `fetch` and CSS
  `:has()` are all in use and fine.
- **Comments explain *why*.** The codebase is heavily commented, and most of those
  comments record a decision and the reason behind it. Match that when editing.
- **Colour goes through tokens.** `assets/site.css` `:root` holds the palette.
  `--oxide` is the brand orange, measured off `assets/img/logo.png`; `--oxide-rgb`
  carries the same colour as bare channels because `rgba()` cannot read a hex
  custom property. Translucent brand tints must use `rgba(var(--oxide-rgb), …)` —
  hardcoding them is what let the palette drift a whole hue from the logo before.
- **The hero reel is atmosphere, not content.** It is gated on `saveData` and
  `prefers-reduced-motion`, is never preloaded, and falls back to a graded poster
  plate. If it fails, the page is still finished. The `Reel 01 · 00:00` timecode
  strip under the hero only appears once the video actually fires `playing` — it
  is the ground truth for "is the reel really running", since the fallback plate
  is a still of the same footage.
