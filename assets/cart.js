/* ==========================================================================
   TEXAS TRUCK PARTS — cart + order handoff
   Depends on assets/config.js (TTP.CONTACT, TTP.waUrl, TTP.mailUrl)
             assets/products.js (TTP.products)
             assets/site.js (TTP.money, TTP.sku, TTP.shot, TTP.fits, TTP.esc…)

   There is no server. Checkout composes the order as plain text and hands it to
   WhatsApp or email as a draft the customer sends themselves. So this file owns
   two things: cart state in localStorage, and the message built from it.
   ========================================================================== */
(function () {
  "use strict";

  var KEY = "ttp_cart";
  var esc = TTP.esc;

  /* TTP.money rounds to whole dollars — right for a browse card, wrong here.
     An order message is a document the customer will hold us to, and a cart of
     $1,049.99 + $3,499.99 + 2x$399.99 rounds to $5,350 against a true $5,349.96.
     Money inside the cart and the message is therefore exact to the cent. */
  var money = function (n) {
    if (n === null || n === undefined || n === "") return "Call for price";
    return "$" + Number(n).toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };
  TTP.money2 = money;

  /* Two-thirds of the catalogue's names run past 70 characters, and a few
     Facebook listings run to 101. Full names would blow the URL budget and
     make the message unreadable, so they are clipped at a word boundary —
     the SKU alongside is what actually identifies the part. */
  var NAME_MAX = 64;
  function shortName(s) {
    if (s.length <= NAME_MAX) return s;
    return s.slice(0, NAME_MAX).replace(/\s+\S*$/, "") + "…";
  }

  /* Freight threshold. Same number the PDP already uses to switch its shipping
     copy from "ground" to "freight, crated on a pallet" — kept in one place so
     the cart and the product page can never disagree about how a bed ships. */
  var FREIGHT_OVER = 1500;

  /* Every product publishes as in stock, so quantity is no longer clamped to the
     catalogue's per-unit count. This is a sanity ceiling on the stepper, not a
     stock statement — the yard confirms real availability when it confirms the
     order. Anyone needing more than this is a fleet order and should talk to us. */
  var MAX_QTY = 10;
  TTP.MAX_QTY = MAX_QTY;

  /* wa.me carries the message in the URL. Long URLs get truncated by WhatsApp
     and by some mobile browsers, and a truncated order is worse than a short
     one, so past this many characters the line list is trimmed and the full
     summary stays on the confirmation page. */
  var MAX_MSG = 1500;
  var MAX_LINES_WHEN_TRIMMED = 6;

  /* ---------- state ----------
     Only id + qty are persisted. Prices, stock and names are re-read from
     TTP.products on every access, so a cart left open for a week cannot quote
     last week's price, and a product pulled from the catalogue drops out of the
     cart visibly rather than lingering as a phantom line. */
  function read() {
    try {
      var raw = JSON.parse(localStorage.getItem(KEY) || "null");
      if (!raw || !Array.isArray(raw.items)) return { v: 1, items: [], ref: null };
      return raw;
    } catch (e) { return { v: 1, items: [], ref: null }; }
  }

  function write(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
    paint();
    document.dispatchEvent(new CustomEvent("ttp:cart"));
  }

  function find(id) {
    for (var i = 0; i < TTP.products.length; i++) {
      if (TTP.products[i].id === id) return TTP.products[i];
    }
    return null;
  }

  var cart = {
    /* Hydrated lines. Anything whose id no longer resolves is dropped here and
       written back, so the pruning happens once rather than on every render. */
    lines: function () {
      var state = read(), out = [], pruned = false, v = TTP.getVehicle();

      state.items.forEach(function (it) {
        var p = find(it.id);
        if (!p) { pruned = true; return; }
        var qty = Math.max(1, Math.min(MAX_QTY, it.qty || 1));
        if (qty !== it.qty) { it.qty = qty; pruned = true; }
        out.push({
          p: p,
          qty: qty,
          priced: TTP.hasPrice(p),
          freight: TTP.hasPrice(p) && p.price >= FREIGHT_OVER,
          atCap: qty >= MAX_QTY,
          /* null when no vehicle is saved — "unknown", not "does not fit". */
          fits: (v && v.year) ? TTP.fits(p, v) : null
        });
      });

      if (pruned) {
        state.items = state.items.filter(function (it) { return !!find(it.id); });
        try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
      }
      return out;
    },

    count: function () {
      return cart.lines().reduce(function (n, l) { return n + l.qty; }, 0);
    },

    /* Priced lines only. A cart holding a $1,049 bumper and a call-for-price
       tool box has a subtotal of $1,049 and an unknown total — those are
       different facts and the UI states both. */
    subtotal: function () {
      return cart.lines().reduce(function (n, l) {
        return n + (l.priced ? l.p.price * l.qty : 0);
      }, 0);
    },

    unpriced: function () {
      return cart.lines().filter(function (l) { return !l.priced; });
    },

    has: function (id) {
      return cart.lines().some(function (l) { return l.p.id === id; });
    },

    add: function (id, qty) {
      var p = find(id);
      if (!p) return false;
      var state = read();
      var cap = MAX_QTY;
      var existing = null;
      state.items.forEach(function (it) { if (it.id === id) existing = it; });

      if (existing) existing.qty = Math.min(cap, existing.qty + (qty || 1));
      else state.items.push({ id: id, qty: Math.min(cap, qty || 1), at: Date.now() });

      if (!state.ref) state.ref = newRef();
      write(state);
      return true;
    },

    setQty: function (id, qty) {
      var p = find(id), state = read();
      var cap = MAX_QTY;
      state.items = state.items.filter(function (it) {
        if (it.id !== id) return true;
        it.qty = Math.max(1, Math.min(cap, qty));
        return qty >= 1;
      });
      write(state);
    },

    remove: function (id) {
      var state = read();
      state.items = state.items.filter(function (it) { return it.id !== id; });
      if (!state.items.length) state.ref = null;   /* next order gets a fresh ref */
      write(state);
    },

    clear: function () { write({ v: 1, items: [], ref: null }); },

    /* Minted when the first item lands and held until the cart empties, so the
       reference the customer sees on screen is the one in the message. */
    ref: function () {
      var state = read();
      if (!state.ref) { state.ref = newRef(); write(state); }
      return state.ref;
    }
  };
  TTP.cart = cart;

  function newRef() {
    var A = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";  /* no I/O/0/1 — read aloud on the phone */
    var s = "";
    for (var i = 0; i < 6; i++) s += A[Math.floor(Math.random() * A.length)];
    return "TTP-" + s;
  }

  /* ---------- payment preference ----------
     Preference only. No money moves on this site and no account details live in
     this repo — the yard sends them over WhatsApp or email once there is a real
     buyer to send them to. "applepay" is a label here, not Apple's payment sheet;
     the checkout copy is careful to say so rather than imply a card charge. */
  TTP.PAYMENTS = [
    ["zelle",    "Zelle",         "Bank-to-bank, usually instant"],
    ["venmo",    "Venmo",         "Pay from your Venmo balance"],
    ["applepay", "Apple Pay",     "We send a request to your number"],
    ["crypto",   "Crypto",        "BTC, ETH or USDT — we confirm the network"],
    ["bank",     "Bank transfer", "ACH or wire from your bank"],
    ["unsure",   "Not sure yet",  "Send me the options"]
  ];

  TTP.paymentLabel = function (key) {
    if (key === "unsure") return "not sure — send options";
    for (var i = 0; i < TTP.PAYMENTS.length; i++) {
      if (TTP.PAYMENTS[i][0] === key) return TTP.PAYMENTS[i][1];
    }
    return key;
  };

  /* ---------- saved buyer details ----------
     A returning customer should not retype their name, number and truck. Kept in
     this browser only — it is never uploaded anywhere, because there is nowhere
     to upload it to. Notes are deliberately NOT saved: a note about one bumper
     reappearing on an unrelated order later is confusing, not helpful. */
  var BUYER_KEY = "ttp_buyer";
  var BUYER_FIELDS = ["name", "phone", "zip", "method", "vin", "payment"];

  TTP.buyer = {
    load: function () {
      try {
        var raw = JSON.parse(localStorage.getItem(BUYER_KEY) || "null");
        if (!raw || typeof raw !== "object") return null;
        var out = {}, any = false;
        BUYER_FIELDS.forEach(function (k) {
          if (typeof raw[k] === "string" && raw[k]) { out[k] = raw[k]; any = true; }
        });
        return any ? out : null;
      } catch (e) { return null; }
    },
    save: function (order) {
      if (!order) return;
      var out = {};
      BUYER_FIELDS.forEach(function (k) { if (order[k]) out[k] = String(order[k]); });
      try { localStorage.setItem(BUYER_KEY, JSON.stringify(out)); } catch (e) {}
    },
    clear: function () { try { localStorage.removeItem(BUYER_KEY); } catch (e) {} }
  };

  /* ---------- shipping copy, one source ---------- */
  TTP.shipNote = function (line) {
    if (!line.priced) return "Shipping quoted with price";
    return line.freight ? "Freight · quoted at confirmation" : "Free ground · lower 48";
  };

  /* ---------- the message ----------
     One builder for both channels so WhatsApp and email can never drift apart.
     order = {name, phone, zip, method, vin, payment, financing, notes} — all optional. */
  TTP.orderText = function (order, opts) {
    order = order || {};
    opts = opts || {};
    var lines = cart.lines();
    var ref = cart.ref();
    var trim = opts.trim !== false;

    var body = ["TEXAS TRUCK PARTS — Order " + ref, ""];

    var shown = lines, omitted = 0;
    if (trim && lines.length > MAX_LINES_WHEN_TRIMMED) {
      /* Estimate first; only trim if the full list would actually overflow. */
      var full = renderLines(lines).join("\n").length;
      if (full > MAX_MSG - 320) {
        shown = lines.slice(0, MAX_LINES_WHEN_TRIMMED);
        omitted = lines.length - shown.length;
      }
    }

    body = body.concat(renderLines(shown));
    if (omitted) body.push("…+" + omitted + " more item" + (omitted > 1 ? "s" : "") +
                           " — full list in order " + ref);
    body.push("");

    var sub = cart.subtotal();
    var nUnpriced = cart.unpriced().length;
    var nPriced = lines.length - nUnpriced;

    if (nPriced) body.push("Subtotal (" + nPriced + " priced item" + (nPriced > 1 ? "s" : "") +
                           "): " + money(sub));
    if (nUnpriced) body.push(nUnpriced + " item" + (nUnpriced > 1 ? "s" : "") + " needs a price quote.");

    var nFreight = lines.filter(function (l) { return l.freight; }).length;
    if (nFreight) body.push("Freight on " + nFreight + " item" + (nFreight > 1 ? "s" : "") +
                            " quoted at confirmation.");
    body.push("");

    if (order.method === "pickup") body.push("Pickup: Sugar Land, TX");
    else if (order.zip) body.push("Ship to: " + order.zip);
    else if (order.method === "ship") body.push("Ship to: (ZIP not given)");

    if (order.vin) body.push("VIN: " + order.vin);
    /* A preference only — nothing is charged on the site. The parts desk reads
       this to know which payment details to send back in the reply. */
    if (order.payment) body.push("Payment: " + TTP.paymentLabel(order.payment));
    if (order.financing) body.push("Financing: interested");

    var who = [];
    if (order.name) who.push(order.name);
    if (order.phone) who.push(order.phone);
    if (who.length) body.push("From: " + who.join(" · "));
    if (order.notes) body.push("Notes: " + order.notes);

    body.push("");
    body.push("Please confirm availability, freight and total.");

    return body.join("\n").replace(/\n{3,}/g, "\n\n");
  };

  function renderLines(lines) {
    return lines.map(function (l) {
      return l.qty + "x  " + TTP.sku(l.p) + "  " + shortName(l.p.name) +
             "  —  " + (l.priced ? money(l.p.price * l.qty) : "Call for price");
    });
  }

  /* Context line for the chat widget on a product page. */
  TTP.partText = function (p) {
    return "Hi — I'm looking at " + TTP.sku(p) + " " + shortName(p.name) +
           (TTP.hasPrice(p) ? " (" + money(p.price) + ")" : " (call for price)") +
           ". Is it still available?";
  };

  TTP.orderSubject = function () {
    return "Order " + cart.ref() + " — Texas Truck Parts";
  };

  /* ---------- header badge ---------- */
  function paint() {
    var n = cart.count();
    document.querySelectorAll("[data-cartcount]").forEach(function (el) {
      el.textContent = n;
      el.hidden = n === 0;
    });
    document.querySelectorAll("[data-cartbtn]").forEach(function (el) {
      el.classList.toggle("has", n > 0);
    });
  }
  TTP.paintCart = paint;

  /* ---------- drawer ----------
     Same scrim + slide pattern as the category filter drawer, so there is one
     interaction vocabulary on the site rather than two. */
  function drawerHTML() {
    return '<aside class="cartdrawer" id="cartdrawer" aria-label="Cart" aria-hidden="true">' +
      '<div class="cd-head">' +
        '<div><span class="mono">Your order</span><b id="cdRef">—</b></div>' +
        '<button type="button" id="cdClose" aria-label="Close cart">&times;</button>' +
      '</div>' +
      '<div class="cd-body" id="cdBody"></div>' +
      '<div class="cd-foot" id="cdFoot"></div>' +
    '</aside>';
  }

  function lineHTML(l) {
    var p = l.p;
    return '<div class="cline" data-line="' + p.id + '">' +
      '<a class="cl-img" href="product.html?id=' + p.id + '">' + TTP.shot(p, "thumb", 0) + '</a>' +
      '<div class="cl-meta">' +
        '<div class="sku">' + TTP.sku(p) + '</div>' +
        '<h4><a href="product.html?id=' + p.id + '">' + esc(p.name) + '</a></h4>' +
        '<div class="cl-ship">' + TTP.shipNote(l) + '</div>' +
        (l.fits === false
          ? '<div class="cl-warn">Does not fit your saved truck — listed for ' +
            esc(TTP.fitLine(p)) + '</div>'
          : '') +
        '<div class="cl-row">' +
          '<div class="qty sm">' +
            '<button type="button" data-cq="-1" data-id="' + p.id + '" aria-label="Decrease">−</button>' +
            '<span>' + l.qty + '</span>' +
            '<button type="button" data-cq="1" data-id="' + p.id + '"' +
              (l.atCap ? ' disabled' : '') + ' aria-label="Increase">+</button>' +
          '</div>' +
          '<div class="cl-price">' +
            (l.priced
              ? '<b>' + money(l.p.price * l.qty) + '</b>'
              : '<a class="askbtn" href="tel:' + TTP.pricingTel() + '">Call for price</a>') +
          '</div>' +
        '</div>' +
        '<button class="cl-rm" type="button" data-crm="' + p.id + '">Remove</button>' +
      '</div>' +
    '</div>';
  }

  function renderDrawer() {
    var body = document.getElementById("cdBody"), foot = document.getElementById("cdFoot");
    if (!body) return;
    var lines = cart.lines();
    var refEl = document.getElementById("cdRef");
    if (refEl) refEl.textContent = lines.length ? cart.ref() : "—";

    if (!lines.length) {
      body.innerHTML = '<div class="cd-empty"><p>Your order is empty.</p>' +
        '<a class="btn ghost" href="category.html"><span>Browse parts</span></a></div>';
      foot.innerHTML = "";
      return;
    }

    body.innerHTML = lines.map(lineHTML).join("");

    var nUn = cart.unpriced().length, nPriced = lines.length - nUn;
    var bad = lines.filter(function (l) { return l.fits === false; }).length;

    foot.innerHTML =
      '<div class="cd-sum">' +
        (nPriced
          ? '<div class="row"><span>Subtotal (' + nPriced + ' priced item' + (nPriced > 1 ? 's' : '') +
            ')</span><b>' + money(cart.subtotal()) + '</b></div>'
          : '') +
        (nUn ? '<div class="row muted"><span>' + nUn + ' item' + (nUn > 1 ? 's' : '') +
               ' quoted by phone</span><b>—</b></div>' : '') +
        '<p class="cd-note">Freight and tax confirmed by the parts desk before you pay. ' +
          'Nothing is charged here.</p>' +
        (bad ? '<p class="cd-bad">' + bad + ' item' + (bad > 1 ? 's do' : ' does') +
               ' not fit your saved truck.</p>' : '') +
      '</div>' +
      '<a class="btn block" href="cart.html"><span>Review &amp; send order</span></a>' +
      /* Deliberately NOT a wa.me link. Sending straight from the drawer produced a
         message with no name, phone, delivery address or payment preference — the
         yard then had to ask for all of it before it could quote freight. This
         routes to the details form and opens it on the form step. */
      '<a class="btn ghost block wa" href="cart.html?send=wa"><span>' + waIcon() +
        'Send on WhatsApp</span></a>';
  }

  function waIcon() {
    return '<svg class="waico" viewBox="0 0 24 24" aria-hidden="true">' +
      '<path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2zm0 18.15h-.01a8.23 8.23 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23a8.2 8.2 0 0 1 8.24 8.24c0 4.54-3.7 8.23-8.24 8.23zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.78.97-.15.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.24-1.47-1.38-1.72-.15-.25-.02-.39.11-.51.11-.11.25-.29.37-.44.13-.15.17-.25.25-.42.08-.17.04-.31-.02-.44-.06-.12-.56-1.35-.77-1.84-.2-.48-.4-.42-.56-.43h-.47c-.17 0-.44.06-.66.31-.23.25-.87.85-.87 2.07s.89 2.4 1.02 2.57c.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.47-.07 1.47-.6 1.68-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.17-.47-.29z"/></svg>';
  }

  function openDrawer(on) {
    var d = document.getElementById("cartdrawer"), s = document.getElementById("cartscrim");
    if (!d) return;
    if (on) renderDrawer();
    d.classList.toggle("on", on);
    d.setAttribute("aria-hidden", on ? "false" : "true");
    if (s) s.classList.toggle("on", on);
    document.body.classList.toggle("noscroll", on);
    if (on) { var c = document.getElementById("cdClose"); if (c) c.focus(); }
  }
  TTP.openCart = openDrawer;

  /* ---------- chat widget ---------- */
  function widgetHTML() {
    var C = TTP.CONTACT;
    return '<div class="chatw" id="chatw">' +
      '<div class="chatpanel" id="chatpanel" role="dialog" aria-label="Chat with the parts desk" aria-hidden="true">' +
        '<div class="cp-head">' +
          '<div><b>Texas Truck Parts</b><span class="mono">Parts desk · Mon–Sat</span></div>' +
          '<button type="button" id="cpClose" aria-label="Close chat">&times;</button>' +
        '</div>' +
        '<div class="cp-body">' +
          '<p class="cp-hi">Send us a message and a real person answers — usually within the hour during shop hours.</p>' +
          '<div class="cp-ctx" id="cpCtx" hidden></div>' +
          '<a class="btn block wa" id="cpWa" href="' + esc(C.waInvite) + '" target="_blank" rel="noopener">' +
            '<span>' + waIcon() + 'Chat on WhatsApp</span></a>' +
          '<div class="cp-alt">' +
            '<a href="tel:' + esc(C.phone) + '">Call ' + esc(C.phoneDisplay) + '</a>' +
            '<a href="mailto:' + esc(C.emails[0]) + '">Email us</a>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<button class="chatbub" id="chatbub" aria-label="Chat with the parts desk" aria-expanded="false">' +
        waIcon() + '<span>Chat</span></button>' +
    '</div>';
  }

  function openPanel(on) {
    var p = document.getElementById("chatpanel"), b = document.getElementById("chatbub");
    if (!p) return;
    p.classList.toggle("on", on);
    p.setAttribute("aria-hidden", on ? "false" : "true");
    if (b) b.setAttribute("aria-expanded", on ? "true" : "false");
  }

  /* The bubble's WhatsApp link depends on what there is to say. With a product
     or a cart in hand we use the number form, which carries prefilled text; with
     nothing to say we use the Business short link, which cannot. */
  TTP.chatContext = function (p) {
    var ctx = document.getElementById("cpCtx"), wa = document.getElementById("cpWa");
    if (!ctx || !wa) return;
    if (p) {
      ctx.hidden = false;
      ctx.innerHTML = '<span class="mono">Asking about</span><b>' + esc(p.name) + '</b>';
      wa.href = TTP.waUrl(TTP.partText(p));
      return;
    }
    if (cart.count()) {
      ctx.hidden = false;
      ctx.innerHTML = '<span class="mono">Your order</span><b>' + cart.ref() + ' · ' +
        cart.count() + ' item' + (cart.count() > 1 ? 's' : '') + '</b>';
      /* Opens a conversation, it does not submit the order — the full summary only
         ever goes out through the details form, so it arrives with contact and
         delivery information attached. */
      wa.href = TTP.waUrl("Hi — I have order " + cart.ref() + " in my cart (" +
        cart.count() + " item" + (cart.count() > 1 ? "s" : "") + "). Can you help?");
      return;
    }
    ctx.hidden = true;
    wa.href = TTP.CONTACT.waInvite;
  };

  /* ---------- boot ---------- */
  function boot() {
    /* Inject shared chrome once per page so three templates don't each carry a
       copy of the same markup. */
    if (!document.getElementById("cartdrawer")) {
      var host = document.createElement("div");
      host.innerHTML = '<div class="cartscrim" id="cartscrim"></div>' + drawerHTML() + widgetHTML();
      while (host.firstChild) document.body.appendChild(host.firstChild);
    }

    paint();

    /* The PDP's sticky buy bar occupies the bottom of the viewport below 900px,
       exactly where the chat bubble sits. product.html toggles `.on` on it from
       an IntersectionObserver, so mirror that onto <body> and let the stylesheet
       lift the bubble clear rather than having the two overlap. */
    var sticky = document.getElementById("stickybuy");
    if (sticky && window.MutationObserver) {
      var mirror = function () {
        document.body.classList.toggle("has-stickybuy", sticky.classList.contains("on"));
      };
      new MutationObserver(mirror).observe(sticky, { attributes: true, attributeFilter: ["class"] });
      mirror();
    }

    document.addEventListener("click", function (e) {
      var t = e.target;

      var open = t.closest("[data-cartbtn]");
      if (open) { e.preventDefault(); openDrawer(true); return; }

      if (t.closest("#cdClose") || t.closest("#cartscrim")) { openDrawer(false); return; }

      var add = t.closest("[data-add]");
      if (add) {
        e.preventDefault();
        var id = +add.dataset.add;
        var qty = +add.dataset.qty || 1;
        if (cart.add(id, qty)) {
          add.classList.add("added");
          setTimeout(function () { add.classList.remove("added"); }, 1200);
          openDrawer(true);
        }
        return;
      }

      var q = t.closest("[data-cq]");
      if (q) {
        var lid = +q.dataset.id;
        var cur = 0;
        cart.lines().forEach(function (l) { if (l.p.id === lid) cur = l.qty; });
        cart.setQty(lid, cur + (+q.dataset.cq));
        renderDrawer();
        document.dispatchEvent(new CustomEvent("ttp:cartpage"));
        return;
      }

      var rm = t.closest("[data-crm]");
      if (rm) {
        cart.remove(+rm.dataset.crm);
        renderDrawer();
        document.dispatchEvent(new CustomEvent("ttp:cartpage"));
        return;
      }

      if (t.closest("#chatbub")) {
        var panel = document.getElementById("chatpanel");
        var willOpen = !panel.classList.contains("on");
        if (willOpen) TTP.chatContext(TTP.currentProduct || null);
        openPanel(willOpen);
        return;
      }
      if (t.closest("#cpClose")) { openPanel(false); return; }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      openDrawer(false);
      openPanel(false);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
