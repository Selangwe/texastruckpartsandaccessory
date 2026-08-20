/* ==========================================================================
   TEXAS TRUCK PARTS — V2 shared behaviour
   Depends on assets/products.js (window.TTP)
   ========================================================================== */
(function () {
  "use strict";

  /* Facebook listings mostly sell on "message for pricing", so price can legitimately
     be null. That is not a zero — showing "$0" on a $1,200 bumper would be worse than
     showing no number at all. */
  var money = function (n) {
    if (n === null || n === undefined || n === "") return "Call for price";
    return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  };
  TTP.money = money;
  TTP.hasPrice = function (p) { return p.price !== null && p.price !== undefined && p.price !== 0; };

  /* ---------- blueprint part schematics, one per category ----------
     Stand-ins until the photo shoot (plan §10: photo library is a launch risk).
     Swapping these for <img> is a one-line change in card()/gallery. */
  var ART = {
    "front-bumper": '<path d="M6 50h188M14 50c0-14 7-21 20-21h132c13 0 20 7 20 21"/><path d="M6 50v18h188V50"/><rect x="44" y="36" width="26" height="11"/><rect x="130" y="36" width="26" height="11"/><circle cx="100" cy="42" r="5"/><path d="M28 68v8M172 68v8" stroke-dasharray="4 4"/>',
    "rear-bumper": '<path d="M8 46h184"/><path d="M16 46c0-12 6-18 18-18h132c12 0 18 6 18 18v22H16z"/><rect x="52" y="54" width="24" height="9"/><rect x="124" y="54" width="24" height="9"/><path d="M86 28v18M114 28v18" stroke-dasharray="4 4"/>',
    "truck-bed": '<path d="M12 22h176v50H12z"/><path d="M12 38h176" stroke-dasharray="6 5"/><path d="M46 22v50M100 22v50M154 22v50"/><path d="M28 72v8M172 72v8"/>',
    tailgate: '<path d="M18 28h164v42H18z"/><path d="M18 44h164" stroke-dasharray="6 5"/><rect x="84" y="50" width="32" height="10"/><path d="M34 70v8M166 70v8"/><circle cx="150" cy="37" r="4"/>',
    "tail-lights": '<path d="M54 16h84l16 30-16 30H54L38 46z"/><path d="M68 30h58M68 46h58M68 62h58"/>',
    "accessories-hardware": '<circle cx="58" cy="46" r="15"/><path d="M58 31v-8M58 61v8M43 46h-8M73 46h8"/><path d="M108 32h58v28h-58z" stroke-dasharray="5 4"/><path d="M118 60v10M156 60v10"/>',
    "front-replacement-bumpers": '<path d="M10 54h180"/><path d="M22 54V26a8 8 0 0 1 8-8h140a8 8 0 0 1 8 8v28"/><path d="M62 18v36M100 18v36M138 18v36"/><path d="M10 54v16h180V54"/>',
    "rear-replacement-bumpers": '<path d="M12 40h176v30H12z"/><rect x="86" y="52" width="28" height="12"/><path d="M40 70v8M160 70v8"/><path d="M12 40l14-14h148l14 14"/>',
    "grill-guards": '<path d="M40 72V26a10 10 0 0 1 10-10h100a10 10 0 0 1 10 10v46"/><path d="M70 16v56M100 16v56M130 16v56M40 44h120"/>',
    "wheels-tires": '<circle cx="100" cy="44" r="34"/><circle cx="100" cy="44" r="22" stroke-dasharray="5 5"/><circle cx="100" cy="44" r="7"/><path d="M100 22v8M100 58v8M78 44h8M114 44h8M86 30l6 6M108 52l6 6M114 30l-6 6M92 52l-6 6"/>',
    /* Facebook-only aisles */
    "tool-boxes": '<path d="M22 34h156v40H22z"/><path d="M22 46h156" stroke-dasharray="6 5"/><path d="M72 34V22h56v12"/><rect x="88" y="52" width="24" height="10"/><circle cx="100" cy="57" r="2.5"/><path d="M40 74v6M160 74v6"/>',
    "running-boards": '<path d="M14 46h172v16H14z"/><path d="M30 46V34M78 46V34M126 46V34M170 46V34"/><path d="M34 62v10M166 62v10"/><path d="M14 54h172" stroke-dasharray="5 4"/>',
    "truck-racks": '<path d="M28 74V24h144v50"/><path d="M28 34h144M28 48h144"/><path d="M76 24v50M124 24v50"/><path d="M18 74h164"/>'
  };
  TTP.art = function (cat) {
    return '<svg class="part" viewBox="0 0 200 84" aria-hidden="true">' + (ART[cat] || ART["accessories-hardware"]) + "</svg>";
  };

  var esc = function (s) {
    return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;")
      .replace(/</g, "&lt;").replace(/>/g, "&gt;");
  };
  TTP.esc = esc;

  /* Real photo when we have one, blueprint schematic when we don't.

     Only the WIDTH of each derivative is fixed by the resize pipeline (thumb 300w,
     main 768w); heights vary because the source photos are a mix of 4:3, square and
     portrait. So width is declared and height is not — the box is reserved by the
     container's `aspect-ratio` in site.css, and declaring a made-up height here
     would just be a wrong number the CSS overrides anyway.

     Both derivatives are offered via srcset so a card on a retina phone can pull the
     768w file without every card paying for it. */
  var WIDTHS = { thumb: 300, main: 768 };

  /* opts: {loading, fetchpriority, sizes, alt} */
  TTP.shot = function (p, kind, index, opts) {
    var i = index || 0;
    var img = p.images && p.images[i];
    if (!img) return TTP.art(p.cat);

    opts = typeof opts === "string" ? { loading: opts } : (opts || {});
    kind = kind || "thumb";

    var src = TTP.asset(img[kind] || img.main || img.thumb);
    /* Facebook photos are one file at an assorted size, and the generator measures
       and records w/h for them. Store photos come from a fixed resize pipeline, so
       only their width is known. Prefer measured values when we have them. */
    var w = img.w || WIDTHS[kind] || WIDTHS.thumb;
    var h = img.h || null;

    /* Every shot of the same part otherwise repeats one identical alt string N
       times. Numbering them describes what each image actually shows. */
    var alt = opts.alt || (i === 0 ? p.name : p.name + " — view " + (i + 1) + " of " + p.images.length);

    /* Only offer a srcset when the two derivatives are genuinely different files —
       a Facebook product has one photo stored as both main and thumb, and listing
       the same URL at two widths would tell the browser a lie. */
    var srcset = [];
    if (img.thumb && img.main && img.thumb !== img.main) {
      srcset.push(esc(TTP.asset(img.thumb)) + " 300w", esc(TTP.asset(img.main)) + " 768w");
    }

    return '<img class="shot" src="' + esc(src) + '"' +
      (srcset.length > 1 ? ' srcset="' + srcset.join(", ") + '"' +
        ' sizes="' + esc(opts.sizes || (kind === "main" ? "(max-width:900px) 100vw, 620px" : "(max-width:640px) 50vw, 300px")) + '"' : "") +
      ' alt="' + esc(alt) + '"' +
      ' loading="' + (opts.loading || "lazy") + '" decoding="async"' +
      (opts.fetchpriority ? ' fetchpriority="' + opts.fetchpriority + '"' : "") +
      ' width="' + w + '"' + (h ? ' height="' + h + '"' : "") + ">";
  };

  /* ---------- fitment helpers ---------- */
  TTP.fitLine = function (p) {
    var yr = p.yearFrom ? p.yearFrom + "–" + p.yearTo : "";
    var mk = p.makes.join(" / ");
    var md = p.models.length ? p.models.join(", ") : "";
    return [yr, mk, md].filter(Boolean).join(" · ");
  };
  /* The store's own SKU when it has one; a derived code only as a fallback. */
  TTP.sku = function (p) {
    if (p.sku) return p.sku;
    var pre = (p.cat || "xx").split("-").map(function (s) { return s[0]; }).join("").toUpperCase();
    return "TTP-" + pre + "-" + p.id;
  };
  TTP.fits = function (p, v) {
    if (!v || !v.year) return true;
    var y = +v.year;
    if (p.yearFrom && (y < p.yearFrom || y > p.yearTo)) return false;
    /* No make recorded means universal fit, not wrong fit. Tool boxes, racks and
       steps are sold by bed width and cab configuration rather than by make (see
       WOO-MAPPING §12), so testing them against a make would have the cart telling
       a customer their tool box does not fit — the one answer that is never true. */
    if (v.make && p.makes.length && p.makes.indexOf(v.make) === -1) return false;
    if (v.model && v.model !== "All models" && p.models.length && p.models.indexOf(v.model) === -1) return false;
    return true;
  };

  /* ---------- product card ---------- */
  TTP.card = function (p) {
    var b = [];
    if (p.condition === "OEM Take-Off") b.push('<span class="badge oem">OEM Take-Off</span>');
    else if (p.condition === "New — Scratch & Dent") b.push('<span class="badge dent">Scratch &amp; Dent</span>');
    else b.push('<span class="badge new">New</span>');
    if (p.savePct >= 5) b.push('<span class="badge save">Save ' + money(p.save) + "</span>");
    if (p.side) b.push('<span class="badge">' + p.side + "</span>");

    return '<article class="card">' +
      '<div class="thumb">' +
        '<div class="badges">' + b.join("") + "</div>" +
        /* Everything publishes as in stock and no unit count is shown — the yard
           confirms availability on the order. Counts read as scarcity pressure
           and go stale the moment a part sells. */
        '<div class="stock-pill"><span class="dot"></span>In stock</div>' +
        '<a class="thumblink" href="' + TTP.productPath(p) + '" tabindex="-1" aria-hidden="true">' +
          TTP.shot(p, "thumb", 0) + "</a>" +
        '<button class="cardadd" type="button" data-add="' + p.id + '" aria-label="Add ' + esc(p.name) + ' to order">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 5v14M5 12h14"/></svg>' +
        '</button>' +
      "</div>" +
      '<div class="meta">' +
        '<div class="sku">' + TTP.sku(p) + "</div>" +
        '<h3><a href="' + TTP.productPath(p) + '">' + esc(p.name) + "</a></h3>" +
        '<p class="fit">' + TTP.fitLine(p) + (p.color ? " · " + p.color : "") + "</p>" +
        '<div class="price"><b' + (TTP.hasPrice(p) ? "" : ' class="ask"') + ">" + money(p.price) +
          (p.save > 0 ? "<s>" + money(p.regPrice) + "</s>" : "") + "</b>" +
          (TTP.hasPrice(p)
            ? '<span class="fin">' + money(p.mo) + "/mo<br>financed</span>"
            : '<span class="fin">message us<br>for pricing</span>') +
        "</div>" +
      "</div></article>";
  };

  /* ---------- saved vehicle (persistent fitment bar, plan §03) ---------- */
  var KEY = "ttp_vehicle";
  TTP.getVehicle = function () {
    try { return JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch (e) { return null; }
  };
  TTP.setVehicle = function (v) {
    try { v ? sessionStorage.setItem(KEY, JSON.stringify(v)) : sessionStorage.removeItem(KEY); } catch (e) {}
    TTP.paintFitBar();
  };
  TTP.paintFitBar = function () {
    var bar = document.getElementById("fitbar");
    if (!bar) return;
    var v = TTP.getVehicle();
    if (!v || !v.year) { bar.classList.remove("on"); return; }
    bar.classList.add("on");
    bar.querySelector("[data-veh]").textContent =
      v.year + " " + v.make + (v.model && v.model !== "All models" ? " " + v.model : "");
    var n = TTP.products.filter(function (p) { return TTP.fits(p, v); }).length;
    bar.querySelector("[data-n]").textContent = n + " parts fit";
  };

  /* ---------- YMM finder wiring ---------- */
  TTP.initFinder = function (root) {
    var yr = root.querySelector("[data-yr]"), mk = root.querySelector("[data-mk]"),
        md = root.querySelector("[data-md]"), out = root.querySelector("[data-out]"),
        step = root.querySelector("[data-step]");
    if (!yr) return;

    var opt = function (el, txt) {
      var o = document.createElement("option"); o.textContent = txt; o.value = txt; el.appendChild(o);
    };
    // placeholder always carries an empty value so it never reads as a real choice
    var reset = function (el, ph) {
      el.innerHTML = ""; el.appendChild(new Option(ph, "")); el.value = ""; el.disabled = true;
    };

    reset(yr, "Select year"); yr.disabled = false;
    // JS reorders integer-like object keys ascending, so sort newest-first here
    Object.keys(TTP.ymm).sort(function (a, b) { return b - a; })
      .forEach(function (y) { opt(yr, y); });

    yr.addEventListener("change", function () {
      reset(mk, "Select make"); reset(md, "Select model");
      if (!yr.value) { out.textContent = "Awaiting vehicle input…"; return; }
      Object.keys(TTP.ymm[yr.value] || {}).sort().forEach(function (m) { opt(mk, m); });
      mk.disabled = false;
      if (step) step.textContent = "Step 02 / 03";
      out.innerHTML = "Year locked · <b>" + yr.value + "</b> — select a make";
    });

    mk.addEventListener("change", function () {
      reset(md, "Select model");
      if (!mk.value) return;
      ((TTP.ymm[yr.value] || {})[mk.value] || []).forEach(function (m) { opt(md, m); });
      md.disabled = false;
      if (step) step.textContent = "Step 03 / 03";
      var n = TTP.products.filter(function (p) {
        return TTP.fits(p, { year: yr.value, make: mk.value });
      }).length;
      out.innerHTML = "Make locked · <b>" + mk.value + "</b> — " + n + " parts fit so far";
    });

    md.addEventListener("change", function () {
      if (!md.value) return;
      var n = TTP.products.filter(function (p) {
        return TTP.fits(p, { year: yr.value, make: mk.value, model: md.value });
      }).length;
      out.innerHTML = "<b>" + n + " parts</b> fit your " + yr.value + " " + mk.value +
        (md.value !== "All models" ? " " + md.value : "");
    });

    root.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!yr.value || !mk.value) {
        out.innerHTML = "<b>Incomplete —</b> pick at least a year and make.";
        return;
      }
      var v = { year: yr.value, make: mk.value, model: md.value || "" };
      TTP.setVehicle(v);
      location.href = TTP.categoryPath() + "?fit=1";
    });
  };

  /* ---------- ticker pacing ----------
     The strip is one fixed-width nowrap copy duplicated once, so a fixed CSS
     duration means a fixed px/sec — and a fixed px/sec crosses a 390px phone
     screen in a third of the time it takes to cross a 1170px desktop one, which
     is why it read as far too fast on mobile. Derive the duration from the
     measured copy width instead, holding the time for one screen-width of text
     to pass constant at every viewport. */
  var SECONDS_PER_SCREEN = 26;

  function paceTicker() {
    var track = document.querySelector(".ticker-track");
    if (!track) return;
    var copy = track.querySelector("p");
    if (!copy) return;
    var copyW = copy.getBoundingClientRect().width;
    var view = window.innerWidth || document.documentElement.clientWidth;
    if (!copyW || !view) return;

    /* copyW / (view / SECONDS_PER_SCREEN) — seconds for one full copy to pass. */
    var secs = (copyW * SECONDS_PER_SCREEN) / view;
    secs = Math.max(30, Math.min(180, secs));   /* never frantic, never stalled */
    track.style.animationDuration = secs.toFixed(1) + "s";
  }
  TTP.paceTicker = paceTicker;

  /* ---------- chrome: menu, reveals, counters ---------- */
  function chrome() {
    paceTicker();
    /* Fonts land after first paint and change the strip's width, so re-measure. */
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(paceTicker);
    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(paceTicker, 200);
    });

    var burger = document.getElementById("burger"), menu = document.getElementById("menu");
    if (burger && menu) {
      burger.addEventListener("click", function () { menu.classList.toggle("open"); });
      menu.querySelectorAll("a").forEach(function (a) {
        a.addEventListener("click", function () { menu.classList.remove("open"); });
      });
    }

    var clear = document.querySelector("[data-clearveh]");
    if (clear) clear.addEventListener("click", function () { TTP.setVehicle(null); location.reload(); });
    TTP.paintFitBar();

    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: .1 });
    document.querySelectorAll(".rv").forEach(function (el, i) {
      el.style.transitionDelay = (i % 3) * 70 + "ms"; io.observe(el);
    });

    var cio = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target, target = +el.dataset.count, t0 = performance.now();
        (function tick(t) {
          var p = Math.min(1, (t - t0) / 1000), e = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(target * e).toLocaleString("en-US");
          if (p < 1) requestAnimationFrame(tick);
        })(t0);
        cio.unobserve(el);
      });
    }, { threshold: .5 });
    document.querySelectorAll("[data-count]").forEach(function (el) { cio.observe(el); });

    /* The only form on the site used the demo handler this replaced (index.html's
       part-request form — see its inline script, data-partreq). Nothing else to
       wire here; re-add a form[data-demo] handler if a future page needs one. */
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", chrome);
  else chrome();
})();
