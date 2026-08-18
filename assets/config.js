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
   SET THIS to the production origin, no trailing slash. e.g.
     TTP.SITE = "https://www.yourdomain.com";
   Left empty, the templates fall back to whatever origin they are served from,
   which is right for local dev and staging and wrong for production.
   --------------------------------------------------------------------------- */
TTP.SITE = "";

/* TODO — NAP audit, blocks launch.
   The address, both phone numbers and the info@texastruckparts.shop email hardcoded
   in index.html came from the same third-party source as the product data. Name,
   Address and Phone must match the Google Business Profile exactly or the
   LocalBusiness schema actively damages local ranking. Confirm all four
   (business name, street address, phone, email) before this goes live. */

/* Path prefixes — change these if the Woo permalink structure differs. */
TTP.PATHS = {
  shop: "/shop/",
  productCategory: "/product-category/",
  product: "/product/"
};

TTP.origin = function () {
  return (TTP.SITE || window.location.origin || "").replace(/\/+$/, "");
};

TTP.abs = function (path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return TTP.origin() + "/" + String(path).replace(/^\/+/, "");
};

/* The canonical URL for a product on OUR site, built from the slug rather than
   trusting the scraped absolute `url` field. */
TTP.productUrl = function (p) {
  return TTP.origin() + TTP.PATHS.product + p.slug + "/";
};

TTP.categoryUrl = function (slug) {
  return slug ? TTP.origin() + TTP.PATHS.productCategory + slug + "/"
              : TTP.origin() + TTP.PATHS.shop;
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
