# GEO / AI Search Analysis — texastruckpartsandaccessory.vercel.app

Audited 2026-08-20 against the live deployment. Every figure below was measured, not estimated.

> Per Google's AI optimization guide, optimizing for generative AI search **is** SEO. Nothing in
> this report is a separate "GEO discipline" — it is SEO fundamentals applied to AI-search surfaces.

---

## GEO Readiness Score: 20 / 100

| Criterion | Weight | Score | Why |
|---|---|---|---|
| Citability | 25% | 5 | Product pages expose 182 crawler-visible words; 0 of 257 descriptions are extractable |
| Structural readability | 20% | 5 | Product pages have **no `<h1>` and no `<h2>`** in served HTML |
| Multi-modal | 15% | 3 | Every image is injected by JS; none present in the HTML a crawler reads |
| Authority & brand | 20% | 4 | No author, no dates, one `sameAs`, entity collision (below) |
| Technical accessibility | 20% | 3 | Sitewide `noindex` + client-side rendering |

**Lift the `noindex` and change nothing else and the score reaches roughly 34/100** — because the
rendering problem, not the noindex, is the real ceiling.

---

## Finding 1 — AI crawlers see empty pages *(critical)*

AI crawlers do not execute JavaScript. This site builds all of its content from
`assets/products.js` at runtime, so what a crawler actually receives is a shell.

Measured with plain HTTP requests (no JS), exactly as GPTBot/ClaudeBot/PerplexityBot fetch:

| Page | Crawler-visible words | `<h1>` | `<h2>` | JSON-LD |
|---|---|---|---|---|
| `/` | 715 | ✅ 1 | 7 | 1 (LocalBusiness) |
| `/shop/` | 261 | "All Parts" | 0 | 0 |
| `/product/<any-of-257>/` | **182** | **none** | **0** | **0** |

The 182 words are the ticker, nav and footer. They are **identical on all 257 product pages**.

What's lost, per product page:
- The product name (the `<h1>`)
- The **305-word average description** — 78,506 words across the catalogue
- Price, SKU, fitment table, the six-question FAQ
- The `Product`, `FAQPage` and `BreadcrumbList` JSON-LD
- Every product photo

The served `<title>` on every product page is the static placeholder **"Product | Texas Truck
Parts"**. The real title is set by JS. To any non-rendering consumer, all 257 pages are the same
untitled page.

This single issue caps citability, structure, multi-modal and schema simultaneously.

### The fix, and why it's cheap here

**Pre-render the 257 product pages and 13 category pages at build time.** You already have the
machinery: `build/generate_products.py` reads the catalogue and writes `assets/products.js`. Having
it also emit one static `.html` per product is the same data, a different template. That converts
78,506 words of genuinely useful, specific product copy from invisible to citable, and puts the
Product/FAQ schema into the HTML where it counts.

It also removes the Vercel rewrites — real files at real paths — and makes the canonicals, which
already point at `/product/<slug>/`, resolve to actual documents rather than a rewritten shell.

---

## Finding 2 — Entity collision *(strategic, decide before launch)*

Searching this business's own identifiers surfaces a **different, already-indexed business** using
the same name, address and phone the site publishes:

| Signal | This site | Already indexed |
|---|---|---|
| Name | Texas Truck Parts | Texas Truck Parts & Accessories |
| Site | `…vercel.app` (noindex) | `texastruckparts.shop` (live, indexable, WooCommerce) |
| Address | 13618 Florence Rd, Sugar Land | 13618 Florence Rd, Sugar Land |
| Facebook | Ranch Hand Bumpers (`61585668963901`) | Texas Truck Parts & Accessories (`61561194960236`) |

`texastruckparts.shop` is the store this catalogue was seeded from, it is live and indexable, and
it already publishes **these same 78,506 words of product description**.

Three consequences for AI search specifically:

1. **Entity resolution.** AI engines answer "who is Texas Truck Parts in Sugar Land?" by resolving
   an entity. Publishing the same name, address and phone as an established indexed business means
   competing to be that entity rather than being one.
2. **Duplicate content.** If the descriptions are pre-rendered as-is, they arrive as a second copy
   of text already indexed elsewhere. Duplicated passages are poor citation candidates.
3. **Brand-name mismatch.** Your Facebook page and support address are *Ranch Hand* branding; the
   site is *Texas Truck Parts*. Brand mentions correlate ~3× more strongly with AI visibility than
   backlinks, so mentions have to accumulate against **one** consistent name to count.

This is a business decision, not a code change — but it should be settled before the noindex comes
off, because it determines which name the mentions should accrue to. It is the same open item as
the NAP TODO in `assets/config.js`.

---

## Finding 3 — Crawler access and files

| Item | Status | Note |
|---|---|---|
| `X-Robots-Tag` | `noindex, nofollow` sitewide | Deliberate, pre-launch. Blocks all citation. |
| `robots.txt` | `User-agent: * / Allow: /` | Every AI crawler already permitted — no changes needed |
| GPTBot / OAI-SearchBot / ClaudeBot / PerplexityBot | Allowed | Covered by the wildcard |
| `llms.txt` | Absent | **Leave it.** Google states it ignores these files entirely; it is not a citation lever |
| Server-side rendering | None | See Finding 1 |

Note the interaction: `robots.txt` allows crawling, and `X-Robots-Tag` forbids indexing. That is
the correct combination for a pre-launch site — crawlers must be able to fetch a page to read the
noindex.

---

## Finding 4 — Authority signals

| Signal | Status |
|---|---|
| `sameAs` entity links | **1** (Facebook, added today). Was zero. |
| Author byline / credentials | None |
| Publication or updated dates | None anywhere |
| Wikipedia / Wikidata | None |
| Reddit / YouTube presence | None found |
| Citations to primary sources | None |
| Reviews | 0 across 257 products (per `WOO-MAPPING.md` §8) |

Dates matter more than they look: content under 3 months old is ~3× more likely to be cited, and
pages stale 6+ months lose citation eligibility. Nothing on this site carries a date at all, so
every page is undateable rather than fresh.

---

## Finding 5 — Passage citability

Optimal citation length is **134–167 words** in a self-contained block. Of 257 descriptions:

- **0** fall in the 134–167 word band
- **204** exceed 300 words
- Average is 305 words

The copy is well written and specific — real fitment detail, real condition notes, exact-item
photography claims. It is simply packaged as one long block rather than as extractable answers.
Roughly 44% of AI citations come from the first 30% of a page, and these descriptions bury their
most quotable facts (year range, finish, sensor configuration, condition) mid-paragraph.

---

## Top 5 highest-impact changes, in order

1. **Pre-render product and category pages.** Unlocks 78,506 words, the schema, the images, real
   `<h1>`s and per-page titles. Everything else is downstream of this.
2. **Settle the entity question** — which name, which address, which phone, one Facebook page —
   before lifting the noindex, so mentions accumulate to one identity.
3. **Rewrite descriptions into a 134–167 word lead block**, with the specific facts front-loaded,
   followed by the longer detail. Same content, restructured for extraction.
4. **Add dates and a named author/organization** to every product and page.
5. **Give each product page a real `<title>` and `<h1>` in the HTML** — currently all 257 share the
   placeholder "Product | Texas Truck Parts".

## Schema recommendations

The `Product`, `FAQPage` and `BreadcrumbList` markup is already well built — it just executes too
late to be read. Pre-rendering fixes it. Beyond that:

- Extend `sameAs` as profiles are established (Facebook is in; add YouTube, Instagram, GBP)
- Add `Organization` with `logo`, `foundingDate` and `areaServed`
- Add `datePublished` / `dateModified` to product pages
- Keep `aggregateRating` out until real reviews exist

## What is already right

- Canonicals are self-referential and resolve (fixed today)
- One clean permalink structure, with the old query URLs still resolving
- `robots.txt` permits every AI crawler
- LocalBusiness JSON-LD is static, so it is visible without JS
- Titles and meta descriptions on `/` and `/shop/` are specific and well written
- No `llms.txt` — correctly, since Google ignores it

---

### Sources

- Google, *AI optimization guide* — developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Ahrefs (Dec 2025), 75,000-brand study — brand mentions vs. backlinks correlation
- SE Ranking, 1.3M-citation study — recency and passage-length findings
