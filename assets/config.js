/* ==========================================================================
   TEXAS TRUCK PARTS — site configuration
   Loaded FIRST, before products.js and site.js.

   Everything that needs to know "what domain is this site?" reads it from here:
   canonical tags, og:url, og:image, JSON-LD @id / offers.url / breadcrumbs.
   One value, one place.

   IMPORTANT — texastruckparts.shop is a THIRD-PARTY site, not ours.
   data/store-products.json and assets/products.js were seeded from that store's
   public Store API, so every product row still carries an absolute `url` on that
   domain. Those URLs must never be emitted as canonicals, schema offer URLs or
   footer links — doing so points our SEO signals at somebody else's site.
   TTP.productUrl() below rewrites them onto our own origin. See WOO-MAPPING.md §12.
   ========================================================================== */
window.TTP = window.TTP || {};

/* ---------------------------------------------------------------------------
   The production origin, no trailing slash. Canonicals, og:url, og:image and
   every JSON-LD @id / offers.url / breadcrumb derive from this one value.

   Set explicitly rather than left empty: the empty fallback uses whatever origin
   served the page, so the same page reachable at a preview deployment URL would
   declare that preview URL canonical and compete with production for its own
   ranking. A fixed value means every copy points at one address.

   TEMPORARY — this is the Vercel-assigned host. Change it to the custom domain
   the moment there is one; see the launch checklist in WOO-MAPPING.md §14.

   Local dev note: served from 127.0.0.1:8777, canonicals and og:url will read
   as the vercel.app domain. That is correct — a canonical is a statement about
   where the page truly lives, not about where you happen to be viewing it.
   --------------------------------------------------------------------------- */
TTP.SITE = "https://texastruckpartsandaccessory.vercel.app";

/* TODO — NAP audit, still open on the ADDRESS only.
   The phone and email below are confirmed and now used sitewide. The street address
   (13618 Florence Rd, Ste D1, Sugar Land, TX 77498) and the "Est. 2019" badge still
   come from the same third-party source as the product data, and Name/Address/Phone
   must match the Google Business Profile exactly or the LocalBusiness schema in
   index.html actively damages local ranking. Confirm the address before launch. */

/* ---------------------------------------------------------------------------
   CONTACT — every phone number, WhatsApp link and email rendered BY JAVASCRIPT
   resolves from here.

   The hand-written HTML does NOT. Each page's header carries a literal
   <a class="tel"> block, and index.html repeats the number in the hero CTA, the
   form note, the yard section, the closing CTA band and the LocalBusiness
   JSON-LD. Changing the parts desk line means editing those nine spots in
   index/category/product/cart.html as well as the two strings below — in four
   different formats: "(952) 529-3586" for display, "+19525293586" for tel:
   hrefs, and "+1-952-529-3586" for the JSON-LD telephone property.
   --------------------------------------------------------------------------- */
TTP.CONTACT = {
  /* Order handoff. Digits only, country code first, no "+".
     ONLY this wa.me/<number>?text= form carries a prefilled message.

     DELIBERATELY NOT the same number as `phone` below. The parts desk line moved
     to 952-529-3586; the WhatsApp inbox stayed on this one, so orders keep
     landing where the yard already reads them. Do not "fix" the mismatch by
     syncing them — checkout is order-by-message, and pointing it at a number
     with no WhatsApp account silently breaks every order. */
  whatsapp: "14244128976",
  /* WhatsApp Business short link. Opens the same inbox but silently DROPS any
     ?text=, so it is used only where there is nothing to prefill (the bare
     chat bubble). Never use it for the order handoff. */
  waInvite: "https://wa.me/message/ASKUCPHXUHX6A1",

  phone: "+19525293586",
  phoneDisplay: "(952) 529-3586",

  /* First address is the default button; add a second to render an alternate. */
  emails: ["Support.ranchhand@gmail.com"],

  /* Optional dedicated pricing line. Every product now carries a price, so nothing
     renders "Call for price" any more and the CTAs that used this are down to the
     out-of-stock ones ("Call About This Part"). Still worth keeping: those calls are
     a different conversation from a parts-desk order, and routing them separately is
     one string. Empty means they fall back to the main line, which is fine. */
  pricingPhone: "",
  pricingPhoneDisplay: ""
};

/* Resolves the pricing line, falling back to the main number until one is set.
   Every "Call for price" CTA on the site reads from this one function. */
TTP.pricingTel = function () {
  return TTP.CONTACT.pricingPhone || TTP.CONTACT.phone;
};
TTP.pricingTelDisplay = function () {
  return TTP.CONTACT.pricingPhoneDisplay || TTP.CONTACT.phoneDisplay;
};

/* Both channels compose the same plain text; these just wrap it in a URL.
   encodeURIComponent, not encodeURI — the body contains &, # and + which would
   otherwise be read as URL syntax and truncate the message. */
TTP.waUrl = function (text) {
  return "https://wa.me/" + TTP.CONTACT.whatsapp +
         (text ? "?text=" + encodeURIComponent(text) : "");
};
TTP.mailUrl = function (subject, body, to) {
  return "mailto:" + (to || TTP.CONTACT.emails[0]) +
         "?subject=" + encodeURIComponent(subject) +
         "&body=" + encodeURIComponent(body);
};

/* Path prefixes — change these if the Woo permalink structure differs. */
TTP.PATHS = {
  shop: "/shop/",
  productCategory: "/product-category/",
  product: "/product/"
};

/* Root-relative permalinks. These are what the site LINKS to, and what the
   canonicals declare — one source, so the two can never disagree. Vercel rewrites
   (vercel.json) and the local dev server both map these onto the real .html files;
   the pages then resolve a product by slug instead of by id.

   The ?id= / ?cat= query forms still work and are still what the pages fall back
   to, so any old link or bookmark keeps resolving. */
TTP.productPath = function (p) {
  return TTP.PATHS.product + p.slug + "/";
};

TTP.categoryPath = function (slug) {
  return slug ? TTP.PATHS.productCategory + slug + "/" : TTP.PATHS.shop;
};

TTP.origin = function () {
  return (TTP.SITE || window.location.origin || "").replace(/\/+$/, "");
};

/* Root-relative asset URL. The generated catalogue stores image paths relative
   ("assets/img/10452/1-main.jpg"), which resolved fine while every page lived at
   the site root — but a product served at /product/<slug>/ would resolve them to
   /product/<slug>/assets/... and 404. Anchor them to the root instead. */
TTP.asset = function (path) {
  if (!path) return "";
  if (/^(https?:)?\/\//i.test(path) || path.charAt(0) === "/") return path;
  return "/" + String(path).replace(/^\.?\//, "");
};

TTP.abs = function (path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return TTP.origin() + "/" + String(path).replace(/^\/+/, "");
};

/* The canonical URL for a product on OUR site, built from the slug rather than
   trusting the scraped absolute `url` field. */
TTP.productUrl = function (p) {
  return TTP.origin() + TTP.productPath(p);
};

TTP.categoryUrl = function (slug) {
  return TTP.origin() + TTP.categoryPath(slug);
};

/* Which product/category the current pretty URL refers to. Returns null when the
   page was reached by its .html?query form, in which case the page falls back to
   reading the query string. */
TTP.pathSlug = function (kind) {
  var prefix = kind === "product" ? TTP.PATHS.product : TTP.PATHS.productCategory;
  var path = window.location.pathname;
  if (path.indexOf(prefix) !== 0) return null;
  var rest = path.slice(prefix.length).replace(/\/+$/, "");
  return rest ? decodeURIComponent(rest) : null;
};

/* The static <head> of each template ships with __SITE__ placeholders so the
   markup stays domain-free and no stale domain can leak into a canonical.
   Resolve them as early as possible — this runs in <head>, before body parse.

   In the WooCommerce port this whole function disappears: WordPress knows its own
   home_url() and the templates interpolate it server-side. */
(function resolvePlaceholders() {
  var origin = TTP.origin();
  var swap = function (s) { return s.replace(/__SITE__/g, origin); };

  [["link[rel=canonical]", "href"],
   ["meta[property='og:url']", "content"],
   ["meta[property='og:image']", "content"],
   ["meta[name='twitter:image']", "content"]
  ].forEach(function (pair) {
    document.querySelectorAll(pair[0]).forEach(function (el) {
      var v = el.getAttribute(pair[1]);
      if (v && v.indexOf("__SITE__") > -1) el.setAttribute(pair[1], swap(v));
    });
  });

  /* Inline JSON-LD blocks carry @id / url / logo placeholders too. Run on
     DOMContentLoaded as well, since blocks later in the document are not parsed
     yet when this executes in <head>. */
  var fixLd = function () {
    document.querySelectorAll('script[type="application/ld+json"]').forEach(function (s) {
      if (s.textContent.indexOf("__SITE__") > -1) s.textContent = swap(s.textContent);
    });
  };
  fixLd();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fixLd);
})();
