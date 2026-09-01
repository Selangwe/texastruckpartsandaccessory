# Generates assets/products.js from data/store-products.json (written by sync_store.py).
#
# Everything is keyed on the WordPress product id, which is stable — the previous version
# keyed on a CSV row number, so inserting one product reassigned every later product's
# photos. Fitment comes from the store's own pa_year-range attribute (build/fitment_map.py),
# falling back to parsing the product title for the handful of products whose term carries
# no make.
import html, json, os, random, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fitment_map

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "store-products.json")
FB_SRC = os.path.join(ROOT, "data", "facebook-products.json")
RH_SRC = os.path.join(ROOT, "data", "ranchhand-products.json")
FB_IMGDIR = os.path.join(ROOT, "assets", "img", "_facebook")
MANIFEST = os.path.join(ROOT, "assets", "img", "manifest.json")
# The Ranch Hand photography keeps its own manifest because it is keyed on the
# manufacturer reference rather than a WordPress product id — mixing SKU strings
# into the store manifest's numeric keys would make both harder to reason about.
RH_MANIFEST = os.path.join(ROOT, "assets", "img", "rh", "manifest.json")
OUT = os.path.join(ROOT, "assets", "products.js")
# The sitemap ships at the site root, and reads its origin from config.js (see
# site_origin()) rather than repeating the domain here.
CONFIG_JS = os.path.join(ROOT, "assets", "config.js")
SITEMAP = os.path.join(ROOT, "sitemap.xml")

# Facebook products get ids in their own block so they can never collide with a
# WordPress product id (those top out in the low five figures).
FB_ID_BASE = 900000

# Ranch Hand imports get their own id block, below the Facebook one and well clear of
# the WordPress ids. Keyed off the manufacturer reference number, which is stable across
# their catalogue in a way the Magento entity id is not.
RH_ID_BASE = 800000

# Availability is decided by assign_stock() in the merchandising pass at the bottom of
# this file, not here. What the store reports is still read and carried through as a
# hint (a SKU the yard has actually run out of is the best candidate to publish as out
# of stock), but it no longer decides the published value on its own.
STOCK_HINT_KEY = "_storeOOS"

# --- category metadata: slug, display name, SEO intro copy (plan §06) ---
CATEGORIES = [
    ("front-bumper", "Front Bumpers", "OEM factory front bumpers pulled from low-mileage trucks",
     "Factory-original front bumpers taken off late-model Ford, Chevy, GMC and Ram trucks. Every unit is an OEM take-off — the same part the dealer sells, at 40–60% less, with the correct fog light slots, sensor holes and mounting brackets already in place. We photograph each bumper on our floor in Sugar Land so you see the exact piece before you buy, blemishes included."),
    ("rear-bumper", "Rear Bumpers", "Factory rear bumpers with and without park sensors",
     "OEM rear bumpers for Super Duty, Silverado/Sierra HD and Ram HD trucks, in chrome and factory paint codes. Sensor and no-sensor variants are listed separately so the harness and park-assist package match your truck exactly. Step pads, license brackets and end caps are included unless the listing says otherwise."),
    ("truck-bed", "Truck Beds", "Complete OEM beds — short bed, long bed, SRW and dually",
     "Complete factory truck beds in original paint, from 6.4ft short beds to 8ft dually (DRW) beds. These are full take-off beds — no rust, no filler, no accident history — pulled from low-mileage trucks and shipped crated on a pallet by freight. Bed only unless the listing states that lights, tailgate or bumper are included."),
    ("tailgate", "Tailgates", "Factory tailgates with step, camera and trim options",
     "OEM tailgates in factory colors, listed by exact configuration: with or without the integrated step, with or without the camera hole, and by trim level where the panel differs (King Ranch, Platinum, Lariat). Handle, latches and camera are included where the listing says so."),
    ("tail-lights", "Tail Lights", "Halogen, LED and BLISS blind-spot tail lights",
     "Factory tail lights sold as individual left-hand (driver) and right-hand (passenger) units so you only pay for the side you need. Halogen, full LED, and BLIS/BLISS blind-spot-equipped variants are listed separately — the harness plug and blind-spot module differ between them, so match the listing to your truck's original equipment."),
    ("accessories-hardware", "Accessories & Hardware", "Bed steps, gooseneck hitches, trim and brackets",
     "The small factory parts nobody stocks: gooseneck and fifth-wheel trailer prep hitches, painted bed step panels, front bed steps in driver and passenger side, brackets and trim. All OEM take-offs, all matched to a specific year range and truck."),
    ("front-replacement-bumpers", "Front Replacement Bumpers", "Heavy-duty aftermarket steel from Tough Country & One Source",
     "Aftermarket heavy-duty steel front bumpers built for work and recovery — Tough Country Evolution and Traditional series, and One Source replacement bumpers. New units unless marked Scratch/Dent, which are cosmetically imperfect and discounted accordingly but structurally sound and fully covered."),
    ("rear-replacement-bumpers", "Rear Replacement Bumpers", "Steel rear bumpers from Tough Country, Ranch Hand & One Source",
     "Heavy-duty aftermarket rear bumpers with integrated receiver hitches and step plates. Built from formed steel and powder coated, these replace the factory rear bumper outright for trucks that tow, haul, or work off pavement."),
    ("grill-guards", "Grill Guards", "Front-end protection built for work trucks",
     "Tough Country grill guards and brush guards that bolt to the frame and protect the grille, headlights and radiator support without blocking airflow or sensor operation."),
    ("wheels-tires", "Wheels & Tires", "Complete wheel and tire packages, mounted and balanced",
     "Complete wheel and tire sets sold as a package — KMC and American Force wheels wrapped in Nitto Ridge Grappler rubber, mounted and balanced, ready to bolt on. Sold as a set of four (or five where noted)."),
    # --- categories that exist only in the Facebook inventory (see WOO-MAPPING.md §12) ---
    ("tool-boxes", "Truck Tool Boxes", "Crossover, chest and side-mount boxes from Weather Guard, UWS & CamLocker",
     "Lockable truck tool boxes for work trucks — crossover boxes that sit behind the cab, low-profile and full-height chest boxes, and side-mount rail boxes. Weather Guard, UWS, CamLocker and RKI, in aluminium and steel, new and semi-new. Every box comes with keys and a weather-sealed closing system. Sizes vary by bed width, so send us your truck and bed length and we will match it."),
    ("running-boards", "Running Boards & Steps", "Running boards, nerf bars and side steps — estribos disponibles",
     "Running boards, nerf bars, step bars and rock sliders that bolt to the factory mounting points and make a lifted or heavy-duty truck usable every day. Sized by cab configuration — Regular, Extended/Super and Crew Cab all take different lengths — so confirm your cab before ordering. Estribos disponibles para Ford, Chevy, GMC y Ram; pregúntanos por tu modelo."),
    ("truck-racks", "Truck & Ladder Racks", "Ladder, headache and utility racks for working trucks",
     "Over-bed ladder racks, headache racks and utility rack systems for trucks that carry pipe, lumber, ladders and conduit. Built to work with a tool box already in the bed, and rated for the loads a real jobsite puts on them. Weather Guard and comparable brands, sized to your bed length."),
]
# store category name -> our slug
CAT_BY_NAME = {
    "Front Bumper": "front-bumper", "Rear Bumper": "rear-bumper", "Truck Bed": "truck-bed",
    "Tailgate": "tailgate", "Tail Lights": "tail-lights", "Accessories & Hardware": "accessories-hardware",
    "Front Replacement Bumpers": "front-replacement-bumpers",
    "Rear Replacement Bumpers": "rear-replacement-bumpers",
    "Grill Guards": "grill-guards", "Wheels & Tires": "wheels-tires",
}
MAKE_CATS = {"Ford": "Ford", "Chevy": "Chevrolet", "Chevrolet": "Chevrolet", "GMC": "GMC",
             "Ram": "Ram", "Dodge": "Ram", "Toyota": "Toyota"}

COLORS = [
    "Granite Crystal", "Abalone White", "Oxford White", "Star White", "Platinum White", "Bright White",
    "Summit White", "Iconic Silver", "Billet Silver", "Sterling Silver", "Stone Grey", "Marsh Grey",
    "Carbonized Grey", "Darkened Bronze", "Hunter Green", "Ruby Red", "Black & Brown Two Tone",
    "Chrome", "Black",
]
BRANDS = ["Tough Country", "One Source", "Ranch Hand", "American Force", "KMC", "Fab Fours", "Westin"]
FEATURES = [
    ("sensor", r"w/ Sensor|Sensor Holes?|Sensor Hole|w/ Sensors", "Park sensor holes"),
    ("no-sensor", r"No Sensors?", "No sensor holes"),
    ("fog", r"Fog Light", "Fog light provision"),
    ("led", r"\bLED\b", "LED"),
    ("bliss", r"\bBLISS?\b|\bBLIS\b", "BLIS blind-spot equipped"),
    ("camera", r"Camera", "Camera hole"),
    ("step", r"w/ Step|Step Camera|Step Panel|Bed Step|Step\b", "Integrated step"),
    ("no-step", r"NO STEP", "No step"),
    ("drw", r"\bDRW\b|Dually", "Dually / DRW"),
    ("srw", r"\bSRW\b", "Single rear wheel / SRW"),
    ("skid", r"Skid Plate", "Skid plate"),
    ("halogen", r"Halogen", "Halogen"),
]

# --- title-parsing fallback, used only when the store's fitment term lacks a make ---
CHASSIS_RE = r"\b(1500|2500|3500|4500)\b"
FAMILY = {"Chevrolet": "Silverado", "GMC": "Sierra", "Ram": "Ram"}
MAKES_RE = [
    ("Ram", r"\b(Ram|Dodge Ram|Mopar)\b"),
    ("Ford", r"\bFord\b|\bF-?250\b|\bF-?350\b|\bF-?450\b|\bSuper Duty\b|\bRanger\b"),
    ("Chevrolet", r"\bChevy\b|\bChevrolet\b|\bSilverado\b"),
    ("GMC", r"\bGMC\b|\bSierra\b|\bDenali\b"),
]
MAKE_PREFIX = {
    "Ford": ("F-", "Ranger", "Super Duty"),
    "Chevrolet": ("Silverado",), "GMC": ("Sierra",), "Ram": ("Ram",),
}


def parse_years(name):
    m = re.search(r"(19|20)(\d{2})\s*[-–]\s*(19|20)(\d{2})", name)
    return (int(m.group(1) + m.group(2)), int(m.group(3) + m.group(4))) if m else (None, None)


def parse_models(name, makes):
    out = []

    def add(m):
        if m not in out:
            out.append(m)

    for n in re.findall(r"\bF-?(150|250|350|450)\b", name):
        add("F-" + n)
    if re.search(r"\bRanger Raptor\b", name, re.I):
        add("Ranger Raptor")
    elif re.search(r"\bRanger\b", name, re.I):
        add("Ranger")
    # "Super Duty" is a range, not a model — expand it so the model dropdown keeps one
    # vocabulary (matches how fitment_map expands the same term)
    if not out and "Ford" in makes and re.search(r"Super Duty", name, re.I):
        for n in ("F-250", "F-350", "F-450"):
            add(n)
    bare = re.sub(r"\bF-?(150|250|350|450)\b", " ", name)
    nums = re.findall(CHASSIS_RE, bare)
    for mk in makes:
        fam = FAMILY.get(mk)
        if not fam:
            continue
        for n in nums:
            add(fam + " " + n)
    return out


def models_for(make, models):
    pre = MAKE_PREFIX.get(make)
    return [m for m in models if m.startswith(pre)] if pre else models


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s.lower())
    return re.sub(r"[\s_]+", "-", s).strip("-")[:80]


def clean(s):
    """Store API returns HTML — strip tags and unescape entities (20&#215;10 -> 20×10)."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def money(minor, unit):
    try:
        return round(int(minor) / (10 ** int(unit)), 2)
    except (TypeError, ValueError):
        return 0.0


def jpeg_dims(path):
    """Intrinsic size straight off the JPEG header — no Pillow dependency.
    Facebook photos are a single derivative at assorted sizes, so the real width and
    height get recorded per image rather than assumed."""
    try:
        with open(path, "rb") as f:
            if f.read(2) != b"\xff\xd8":
                return None
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                marker = f.read(1)
                if not marker:
                    return None
                if marker[0] in (0xC0, 0xC1, 0xC2, 0xC3):
                    f.read(3)
                    h, w = struct.unpack(">HH", f.read(4))
                    return (w, h)
                ln = f.read(2)
                if len(ln) < 2:
                    return None
                f.seek(struct.unpack(">H", ln)[0] - 2, 1)
    except Exception:
        return None


def webp_dims(path):
    """Intrinsic size straight off the WebP header — same no-Pillow rule as jpeg_dims.

    Only needed because one category hero happens to be a .webp. All three WebP
    flavours are covered: lossy (VP8 ), lossless (VP8L) and extended (VP8X).
    """
    try:
        with open(path, "rb") as f:
            head = f.read(30)
        if head[:4] != b"RIFF" or head[8:12] != b"WEBP":
            return None
        fourcc = head[12:16]
        if fourcc == b"VP8 ":
            # frame header: 3-byte tag, 3-byte start code, then 14-bit w/h
            w, h = struct.unpack("<HH", head[26:30])
            return (w & 0x3FFF, h & 0x3FFF)
        if fourcc == b"VP8L":
            bits = struct.unpack("<I", head[21:25])[0]
            return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        if fourcc == b"VP8X":
            # 24-bit little-endian canvas width-1 / height-1
            w = head[24] | (head[25] << 8) | (head[26] << 16)
            h = head[27] | (head[28] << 8) | (head[29] << 16)
            return (w + 1, h + 1)
    except Exception:
        pass
    return None


def image_dims(path):
    """Intrinsic (w, h) for any hero we ship, or None. JPEG or WebP; nothing else occurs."""
    if not path:
        return None
    full = os.path.join(ROOT, path.replace("/", os.sep))
    return webp_dims(full) if full.lower().endswith(".webp") else jpeg_dims(full)


def facebook_products(start_index):
    """Folds data/facebook-products.json into the same product shape as the store feed.

    These are the business's own listings, so they publish alongside the store
    catalogue. Two things differ and are handled rather than faked:
      * most posts sell on 'message for pricing', so price is None, not 0
      * each photo is one file, not a thumb/main pair, so w/h are measured
    Anything the parser flagged `needs-review` is skipped — an unreviewed guess should
    not appear as a live product."""
    if not os.path.exists(FB_SRC):
        return [], 0
    payload = json.load(open(FB_SRC, encoding="utf-8"))
    rows = payload.get("products", [])

    out, held = [], 0
    for i, fp in enumerate(rows):
        if fp.get("status") != "ok":
            held += 1
            continue
        cat = fp.get("cat")
        if not cat:
            held += 1
            continue

        images = []
        for fn in fp.get("images", []):
            path = os.path.join(FB_IMGDIR, fn)
            if not os.path.exists(path):
                continue
            rel = "assets/img/_facebook/" + fn
            wh = jpeg_dims(path)
            shot = {"main": rel, "thumb": rel}
            if wh:
                shot["w"], shot["h"] = wh
            images.append(shot)
        if not images:
            held += 1
            continue

        name = fp.get("name") or "Truck part"
        price = fp.get("price")
        out.append({
            "id": FB_ID_BASE + i,
            "sortIndex": start_index + i,
            "slug": slugify(name) or ("fb-" + str(i)),
            "sku": "TTP-FB-%04d" % (i + 1),
            "name": name,
            "cat": cat,
            "catName": next((n for s, n, _t, _b in CATEGORIES if s == cat), ""),
            "price": price, "regPrice": price,
            "save": 0, "savePct": 0,
            "inStock": True, "qty": 1,
            "url": "",
            "desc": fp.get("text") or "",
            "yearFrom": fp.get("yearFrom"), "yearTo": fp.get("yearTo"),
            "makes": fp.get("makes") or [], "models": fp.get("models") or [],
            "color": None, "brand": fp.get("brand"), "side": None,
            "condition": fp.get("condition") or "New Aftermarket",
            "features": [],
            "images": images,
            "mo": max(55, round(price / 12)) if price else None,
            "source": "facebook",
        })
    return out, held


# Makes and models we can recognise in a Ranch Hand product name. Their names carry
# fitment as prose ("Fits Select F-250, F-350 Super Duty"), so this reads what is
# actually there and leaves the rest empty rather than guessing -- an unmatched product
# simply does not surface in the YMM finder, which is honest. Real fitment arrives with
# the VSP stage.
RH_MODEL_MAKE = [
    ("f-150", "Ford", "F-150"), ("f-250", "Ford", "F-250"), ("f-350", "Ford", "F-350"),
    ("f-450", "Ford", "F-450"), ("f-550", "Ford", "F-550"), ("super duty", "Ford", "Super Duty"),
    ("silverado", "Chevrolet", "Silverado"), ("colorado", "Chevrolet", "Colorado"),
    ("sierra", "GMC", "Sierra"), ("canyon", "GMC", "Canyon"),
    ("ram 1500", "Ram", "Ram 1500"), ("ram 2500", "Ram", "Ram 2500"),
    ("ram 3500", "Ram", "Ram 3500"), ("tundra", "Toyota", "Tundra"),
]

# Spec labels whose value is a plain yes/no about what the part keeps working. Only the
# ones actually present are stated -- see the "--" sentinel note in sync_ranchhand.py.
# The category display names are plurals written for page headings ("Accessories &
# Hardware"), which read badly mid-sentence. These are the singular nouns for prose.
RH_NOUN = {
    "front-replacement-bumpers": "front replacement bumper",
    "rear-replacement-bumpers": "rear replacement bumper",
    "grill-guards": "grille guard",
    "running-boards": "running step",
    "truck-racks": "headache rack",
    "accessories-hardware": "accessory",
}

RH_RETAINS = [
    ("Retains Factory Fog Lights", "the factory fog lights"),
    ("Retains Factory Tow Hooks", "the factory tow hooks"),
    ("Retains Factory Receiver", "the factory receiver"),
    ("Retains Front Camera Functionality", "front camera function"),
    ("Retains Parking Sensors", "the parking sensors"),
]


def rh_fitment(name):
    """Pull makes/models out of the product name. Returns ([makes], [models])."""
    low = (name or "").lower()
    makes, models = [], []
    for needle, make, model in RH_MODEL_MAKE:
        if needle in low:
            if make not in makes:
                makes.append(make)
            if model not in models:
                models.append(model)
    return makes, models


def rh_description(rec, cat_name):
    """Compose listing copy from the spec facts.

    Written rather than borrowed. Ranch Hand's own product copy is a two-sentence blurb,
    a bullet list, a 150-230 word unbroken paragraph and a second list of ALL-CAPS
    labelled bullets; none of that is reused, and neither is any of their phrasing. What
    is reused is the facts -- gauge, finish, weight, what the part retains -- which are
    not theirs to own. Short declaratives, numbers instead of adjectives, no superlatives.

    Every clause is gated on the fact existing. A part whose retention flags came back
    "--" gets no sentence about them at all, because we do not know."""
    sp = rec.get("specs") or {}
    series = rec.get("series")
    bits = []

    # opener: what it is
    lead = "New Ranch Hand %s" % RH_NOUN.get(rec.get("cat"), "part")
    if series:
        lead += " from the %s series" % series
    bits.append(lead + ".")

    # build
    material = sp.get("Material Type")
    finish = sp.get("Hardware Finish")
    color = sp.get("Product Color")
    build = []
    if material:
        build.append(str(material).lower())
    if finish:
        build.append(str(finish).lower())
    if build:
        line = "Built from " + " with a ".join(build)
        if color and str(color).lower() not in line:
            line += " in %s" % str(color).lower()
        bits.append(line + ".")

    # weight and shipping, useful because these ship freight
    weight = sp.get("Item Weight (Pounds)")
    if weight:
        bits.append("Ships at %s lb." % (int(weight) if isinstance(weight, float) and weight.is_integer() else weight))

    # what it keeps working -- only where the data says so
    keeps = [phrase for label, phrase in RH_RETAINS if sp.get(label) is True]
    drops = [phrase for label, phrase in RH_RETAINS if sp.get(label) is False]
    if keeps:
        bits.append("Retains %s." % oxford(keeps))
    if drops:
        bits.append("Does not retain %s." % oxford(drops))

    # identifiers a buyer can check against their own truck
    ident = []
    if rec.get("mfrRef"):
        ident.append("Part %s" % rec["mfrRef"])
    if rec.get("upc"):
        ident.append("UPC %s" % rec["upc"])
    if ident:
        bits.append(" · ".join(ident) + ".")

    # A universal part has nothing to confirm, so telling the buyer to send a VIN for one
    # is noise. Only fitted parts get the fitment line.
    if rec.get("universal") or str(sp.get("Universal Part", "")).lower() == "yes":
        bits.append("Universal fit.")
    else:
        bits.append("Send us your VIN and we will confirm cab, bed and sensor package "
                    "before it ships.")
    return " ".join(bits)


def oxford(items):
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return "%s and %s" % (items[0], items[1])
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


def ranchhand_products(start_index):
    """Folds data/ranchhand-products.json into the same product shape as everything else.

    Built by build/import_ranchhand_dump.py (offline) or build/sync_ranchhand.py (live).
    Three things differ from the store feed and are handled rather than papered over:
      * photography comes from Ranch Hand's own CDN via build/fetch_ranchhand_images.py
        and is keyed on the SKU, not the product id. A SKU the fetcher has not reached
        yet keeps an empty images list, and product.html renders its schematic
        placeholder with an honest "no photo on file" note.
      * specs exist for only part of the catalogue so far, so copy degrades to whatever
        facts are actually present
      * anything the importer flagged needsReview is skipped, same as Facebook"""
    if not os.path.exists(RH_SRC):
        return [], 0

    shots_by_sku = {}
    if os.path.exists(RH_MANIFEST):
        m = json.load(open(RH_MANIFEST, encoding="utf-8"))
        shots_by_sku = {k: v["shots"] for k, v in m.items() if v.get("shots")}

    rows = json.load(open(RH_SRC, encoding="utf-8"))
    out, held = [], 0
    for i, rec in enumerate(rows):
        cat = rec.get("cat")
        if not cat or rec.get("needsReview"):
            held += 1
            continue

        name = rec.get("name") or ""
        # House style puts the brand up front -- their own names omit it, and the
        # catalogue already carries "Ranch Hand ..." titles from the Facebook source.
        if not name.lower().startswith("ranch hand"):
            name = "Ranch Hand " + name

        cat_name = next((n for s_, n, _t, _b in CATEGORIES if s_ == cat), "")
        makes, models = rh_fitment(rec.get("name"))
        price = rec.get("price")
        universal = bool(rec.get("universal"))
        sku = rec.get("mfrRef") or ("RH-%04d" % i)

        out.append({
            "id": RH_ID_BASE + i,
            "sortIndex": start_index + i,
            "slug": slugify(name) or ("rh-" + str(i)),
            "sku": sku,
            "name": name,
            "cat": cat,
            "catName": cat_name,
            "price": price, "regPrice": price,
            "save": 0, "savePct": 0,
            "inStock": bool(rec.get("inStock", True)), "qty": 1,
            "url": "",
            "desc": rh_description(rec, cat_name),
            "yearFrom": None, "yearTo": None,
            "makes": makes, "models": models,
            "color": (rec.get("specs") or {}).get("Product Color"),
            "brand": rec.get("brand") or "Ranch Hand",
            "series": rec.get("series"),
            "side": None,
            "condition": "New Aftermarket",
            "universal": universal,
            "features": [],
            "images": shots_by_sku.get(sku, []),
            "mo": max(55, round(price / 12)) if price else None,
            "source": "ranchhand",
        })
    return out, held


# ===========================================================================
# MERCHANDISING PASS
#
# Three catalogue-wide edits that run after the three source feeds are merged and
# before categories are computed, so TTP.categories[] min/max/inStock are derived
# from the published numbers rather than the imported ones.
#
# Everything here is seeded. Re-running the generator reproduces the same catalogue
# byte for byte — a price that shuffles on every deploy is a price nobody can quote
# over the phone, and availability that moved on its own would make the out-of-stock
# badge mean nothing.
# ===========================================================================

MERCH_SEED = 20260831

# Flat amounts taken off every price.
DISCOUNTS = [114.0, 105.45, 100.85, 93.49, 85.0]

# No published price may fall below this. The catalogue starts at $17.95 and 281 of
# the Ranch Hand lines sit under $81, so a flat $85 off would drive a large slice of
# the accessories negative.
PRICE_FLOOR = 19.95

# Share of the catalogue published as out of stock.
OOS_SHARE = 0.05

# Relative likelihood of being picked, by condition. An OEM take-off is a specific
# part off a specific truck — when it sells there is not another one behind it. New
# aftermarket stock is a catalogue line that can be reordered, so it rarely reads as
# unavailable.
OOS_WEIGHT = {
    "OEM Take-Off": 6.0,
    "New — Scratch & Dent": 3.0,
    "New Aftermarket": 0.6,
}

# Multiplier for a SKU the live store already reports as out of stock.
OOS_STORE_HINT_BOOST = 4.0

# Words carrying no matching signal — every listing here is a truck part in Texas.
MATCH_STOP = {
    "the", "and", "for", "with", "new", "oem", "truck", "parts", "part", "fits",
    "fit", "from", "your", "this", "that", "will", "our", "you", "are", "has",
    "brand", "available", "heavy", "duty", "steel", "full", "replacement", "bumper",
    "bumpers", "front", "rear", "quality", "install", "installed", "ready", "in",
    "of", "to", "on", "or", "we", "us", "it", "is", "by",
}

# Tokens that actually identify a part: truck families, trims and brands. A shared
# "silverado" or "2500" means far more than a shared "heavy".
MATCH_STRONG = {
    "f150", "f250", "f350", "f450", "superduty", "silverado", "sierra", "ram",
    "tacoma", "tundra", "titan", "colorado", "canyon", "frontier", "ranger",
    "1500", "2500", "3500", "2500hd", "3500hd", "chevy", "chevrolet", "gmc",
    "ford", "dodge", "toyota", "nissan", "legend", "summit", "midnight", "sport",
    "horizon", "evos", "traditional", "winch", "camera", "sensor", "diesel",
}


def match_tokens(text):
    """Lowercase alphanumeric tokens worth matching on."""
    if not text:
        return set()
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in raw if len(t) > 1 and t not in MATCH_STOP}


def match_score(a_name, a_desc, b_name, b_desc):
    """How strongly two listings look like the same kind of part.

    Name agreement counts for more than description agreement — a description
    repeats boilerplate across a whole brand, while the name is where the truck and
    the trim actually live. Several of the priceless Facebook rows are titled things
    like "Full Replacement", though, so the description is the only place their
    fitment appears and it has to count for something.
    """
    an, bn = match_tokens(a_name), match_tokens(b_name)
    ad, bd = match_tokens(a_desc), match_tokens(b_desc)
    score = 0.0
    for t in an & bn:
        score += 3.0 if t in MATCH_STRONG else 1.0
    for t in (ad & bd) - (an & bn):
        score += 0.6 if t in MATCH_STRONG else 0.15
    for t in ((an & bd) | (ad & bn)) - (an & bn):
        score += 0.4 if t in MATCH_STRONG else 0.1
    return score


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else round((xs[n // 2 - 1] + xs[n // 2]) / 2, 2)


def fill_missing_prices(products, rng):
    """Give every priceless listing a number borrowed from a comparable one.

    The Facebook imports mostly sold on "message for pricing", so they arrive with
    price None. Borrowing is confined to the same category and then scored on name
    and description overlap, because the failure that matters is not an imprecise
    price — it is a $6,000 bumper inheriting an $80 accessory's number and being
    ordered at it. Where nothing in the category resembles the listing at all, the
    category median is a defensible stand-in in a way a random draw is not.
    """
    priced_by_cat = {}
    all_priced = []
    for p in products:
        if p["price"]:
            priced_by_cat.setdefault(p["cat"], []).append(p)
            all_priced.append(p)

    filled, by_median, cross = 0, 0, 0
    for p in products:
        if p["price"]:
            continue
        pool = priced_by_cat.get(p["cat"], [])
        if not pool:
            # A category can be too thin to borrow within — tool-boxes holds exactly
            # one listing, and it is this one. Widening to the whole catalogue is the
            # weakest form of match here and the log calls it out by name, because a
            # tool box priced off a bumper is precisely the mistake the same-category
            # rule exists to prevent. Worth a human glance whenever it fires.
            pool = all_priced
            cross += 1
        if not pool:
            continue

        scored = [(match_score(p["name"], p["desc"], q["name"], q["desc"]), q) for q in pool]
        best = max(s for s, _ in scored)
        if best > 0:
            # Every candidate tied at the top is equally defensible; the seed picks one.
            top = sorted([q for s, q in scored if s == best], key=lambda q: q["id"])
            price = rng.choice(top)["price"]
        else:
            price = median([q["price"] for q in pool])
            by_median += 1
        if not price:
            continue

        p["price"] = round(price, 2)
        p["regPrice"] = p["price"]
        p["save"], p["savePct"] = 0, 0
        p["mo"] = max(55, round(p["price"] / 12))
        filled += 1
    return filled, by_median, cross


def fit_discount(price, rng):
    """The amount to take off this price, or None if none of them fit.

    The seeded pick is the intended amount; where it would breach the floor the
    smaller amounts are tried in turn rather than the price being clamped, because a
    clamp would silently pile every cheap accessory onto the same floor value.
    """
    want = rng.choice(DISCOUNTS)
    for d in [want] + sorted(DISCOUNTS, reverse=True):
        if round(price - d, 2) >= PRICE_FLOOR:
            return d
    return None


def apply_discounts(products, rng):
    """Take a flat amount off every price that can carry one.

    The pre-discount number stays on as regPrice, so the strikethrough and the
    "Save $X · N%" badge the templates already render show the reduction. Store
    products that arrived with a real regular price keep it and simply save more.
    """
    cut = skipped = 0
    for p in products:
        if not p["price"]:
            continue
        d = fit_discount(p["price"], rng)
        if d is None:
            skipped += 1
            continue
        was = p["regPrice"] or p["price"]
        p["price"] = round(p["price"] - d, 2)
        p["regPrice"] = round(max(was, p["price"]), 2)
        disc = round(p["regPrice"] - p["price"], 2)
        p["save"] = disc if disc > 0 else 0
        p["savePct"] = round(disc / p["regPrice"] * 100) if p["regPrice"] and disc > 0 else 0
        p["mo"] = max(55, round(p["price"] / 12))
        cut += 1
    return cut, skipped


def assign_stock(products, rng):
    """Publish a realistic slice of the catalogue as out of stock.

    Weighted rather than uniform: a brand-new Ranch Hand bumper reading "sold out"
    is not a scarcity signal, it is a listing that looks broken, because that part is
    a catalogue line the yard can reorder. One-of-one OEM take-offs are where genuine
    unavailability lives, and a SKU the live store already reports as out is the
    strongest candidate of all.
    """
    target = int(round(len(products) * OOS_SHARE))
    pool = []
    for p in products:
        w = OOS_WEIGHT.get(p["condition"], 1.0)
        if p.pop(STOCK_HINT_KEY, False):
            w *= OOS_STORE_HINT_BOOST
        p["inStock"] = True
        if w > 0:
            pool.append((w, p))

    # Weighted sampling without replacement (Efraimidis-Spirakis): give each item the
    # key u**(1/w) and take the HIGHEST. A larger weight pushes the exponent toward 0,
    # which pushes the key toward 1 — so the heavily weighted conditions crowd the top
    # of the list. Taking the lowest keys instead inverts the whole thing and hands
    # every out-of-stock badge to the new aftermarket lines, which is the one outcome
    # this weighting exists to avoid. Sorting on id first keeps the draw stable against
    # any reordering of the source feeds.
    pool.sort(key=lambda wp: wp[1]["id"])
    keyed = sorted(((rng.random() ** (1.0 / w), p) for w, p in pool),
                   key=lambda kp: kp[0], reverse=True)
    for _, p in keyed[:target]:
        p["inStock"] = False
        p["qty"] = 0
    return target


def site_origin():
    """Read the production origin out of assets/config.js — never hardcode it.

    config.js is the deliberate single source of truth for "what domain is this
    site?"; canonicals, og:url and every JSON-LD @id already derive from it, and
    a sitemap that disagreed with the canonicals would be worse than no sitemap
    at all. It also carries a standing warning that texastruckparts.shop is a
    THIRD-PARTY store we were seeded from and must never be emitted as one of
    our own URLs — so the origin is taken from the one line that is allowed to
    define it, and asserted, rather than typed in a second time here.
    """
    src = open(CONFIG_JS, encoding="utf-8").read()
    m = re.search(r"""TTP\.SITE\s*=\s*["']([^"']+)["']""", src)
    if not m:
        sys.exit("could not find TTP.SITE in %s" % CONFIG_JS)
    origin = m.group(1).rstrip("/")
    if not origin.startswith("https://"):
        sys.exit("TTP.SITE is not an https:// origin: %r" % origin)
    return origin


def write_sitemap(products, cats):
    """Emit sitemap.xml for the home page, the shop, every category and every product.

    Trailing slash on every URL, without exception. vercel.json sets
    "trailingSlash": true, so an unslashed URL is a 308 to the slashed one —
    a sitemap full of those spends half the crawl budget on redirects and asks
    Google to discover each page twice.

    URLs are built from the same slug + path shapes TTP.productPath() and
    TTP.categoryPath() use in config.js, so what we submit is byte-identical to
    what the pages declare canonical.
    """
    origin = site_origin()
    urls = [origin + "/", origin + "/shop/"]
    urls += [origin + "/product-category/" + c["slug"] + "/" for c in cats]
    urls += [origin + "/product/" + p["slug"] + "/" for p in products]

    with open(SITEMAP, "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            # Slugs are ASCII by construction (slugify strips everything else), but
            # escape anyway — an & or < reaching the file unescaped makes the whole
            # sitemap unparseable and silently drops all 555 URLs, not just one.
            f.write("  <url><loc>%s</loc></url>\n" % html.escape(u, quote=False))
        f.write("</urlset>\n")

    print("wrote %s (%d urls, origin %s)" % (SITEMAP, len(urls), origin))
    return urls


def dedupe_slugs(products):
    """Guarantee every product owns a slug nobody else does.

    The slug IS the permalink: product.html resolves a page with
    filter(x => x.slug === slug)[0], and TTP.productUrl() hands the same URL to
    the canonical tag, the JSON-LD and every card in the grid. So when two
    products share a slug only the FIRST one is reachable at all — the rest are
    published, linked and sitemapped, but every one of those links lands on the
    first product's page. Three sources feed this catalogue (the WooCommerce
    store, the Facebook parse and the Ranch Hand import) and each slugifies from
    the product name, so near-identical titles collided freely across the fold.

    The safety property, and the reason this runs the way it does:

      * The FIRST occurrence of a slug always keeps it, untouched. First means
        first in `products`, which is the same array order product.html's
        filter()[0] resolves against — so every URL that works today still
        resolves to exactly the same product. Only the stranded duplicates,
        which had no working URL of their own, get a new one.
      * Later occurrences take -2, -3, ... in ascending order.
      * A generated suffix is checked against every slug in the catalogue, not
        just the ones handed out so far. Without that, a duplicate of "foo"
        could be renamed to "foo-2" and quietly steal the permalink from a
        product that legitimately arrived from the store already named "foo-2".

    Must run after the last catalogue is folded in, so it sees every product,
    and before merchandise() only because there is no reason to defer it.
    """
    reserved = {p["slug"] for p in products}
    taken, renamed = set(), 0
    for p in products:
        base = p["slug"]
        if base not in taken:
            taken.add(base)
            continue
        n = 2
        while True:
            cand = "%s-%d" % (base, n)
            if cand not in taken and cand not in reserved:
                break
            n += 1
        p["slug"] = cand
        reserved.add(cand)
        taken.add(cand)
        renamed += 1
    if renamed:
        print("  slugs: %d duplicate permalinks resolved (%d unique)"
              % (renamed, len(taken)))
    return renamed


def merchandise(products):
    """Fill prices, then discount, then decide stock — in that order.

    Filling first means the borrowed prices are pre-discount numbers that then take
    the same reduction as everything else, so a filled listing is indistinguishable
    from an imported one rather than being the only thing on the site at full price.
    """
    rng = random.Random(MERCH_SEED)
    filled, by_median, cross = fill_missing_prices(products, rng)
    cut, skipped = apply_discounts(products, rng)
    oos = assign_stock(products, rng)
    print("  merchandising (seed %d):" % MERCH_SEED)
    print("    prices filled:   %d (%d from category median)" % (filled, by_median))
    if cross:
        print("      !! %d matched OUTSIDE their own category - too few priced siblings"
              % cross)
    print("    prices reduced:  %d (%d left alone - no discount clears the $%.2f floor)"
          % (cut, skipped, PRICE_FLOOR))
    print("    out of stock:    %d of %d (%.1f%%)"
          % (oos, len(products), 100.0 * oos / max(1, len(products))))


def main():
    if not os.path.exists(SRC):
        sys.exit("missing %s — run `npm run sync` first" % SRC)
    store = json.load(open(SRC, encoding="utf-8"))

    shots_by_id = {}
    if os.path.exists(MANIFEST):
        m = json.load(open(MANIFEST, encoding="utf-8"))
        shots_by_id = {str(k): v.get("shots", []) for k, v in m.items() if v.get("shots")}

    products, seen_terms, fallbacks, skipped = [], [], [], []
    for idx, sp in enumerate(store):
        pid = sp["id"]
        name = clean(sp.get("name"))
        # category names arrive HTML-escaped ("Wheels &amp; Tires")
        catnames = [clean(c.get("name")) for c in sp.get("categories") or []]

        cat = next((CAT_BY_NAME[c] for c in catnames if c in CAT_BY_NAME), None)
        if not cat:
            skipped.append((pid, name[:60], catnames))
            continue

        # ---- fitment: store attribute first, title parsing only as a fallback ----
        terms = [t.get("name") for a in sp.get("attributes") or []
                 if (a.get("name") or "").lower().startswith("year")
                 for t in a.get("terms") or []]
        seen_terms.extend(terms)

        y0 = y1 = None
        makes, models = [], []
        for t in terms:
            res = fitment_map.normalise(t)
            if not res:
                continue
            a, b, mk, md = res
            y0 = a if y0 is None else min(y0, a)
            y1 = b if y1 is None else max(y1, b)
            for x in mk:
                if x not in makes:
                    makes.append(x)
            for x in md:
                if x not in models:
                    models.append(x)

        # make categories are a second, independent signal
        for c in catnames:
            mk = MAKE_CATS.get(c)
            if mk and mk not in makes:
                makes.append(mk)

        if not makes:
            makes = [m for m, pat in MAKES_RE if re.search(pat, name, re.I)][:1]
            if re.search(r"\bChevy\b|\bSilverado\b", name, re.I) and re.search(r"\bGMC\b|\bSierra\b", name, re.I):
                makes = ["Chevrolet", "GMC"]
            fallbacks.append((pid, name[:52], terms))
        if not models:
            models = parse_models(name, makes)
        if y0 is None:
            y0, y1 = parse_years(name)

        prices = sp.get("prices") or {}
        unit = prices.get("currency_minor_unit", 2)
        sale = money(prices.get("price"), unit)
        reg = money(prices.get("regular_price"), unit) or sale
        disc = round(reg - sale, 2)

        qty = sp.get("low_stock_remaining") or 1
        # Published availability is settled later; keep the live signal as a hint.
        store_oos = not bool(sp.get("is_in_stock"))

        color = next((c for c in COLORS if c.lower() in name.lower()), None)
        brand = next((b for b in BRANDS if b.lower() in name.lower()), None)

        feats = [{"key": k, "label": lab} for k, pat, lab in FEATURES if re.search(pat, name, re.I)]
        keys = {f["key"] for f in feats}
        if "no-sensor" in keys:
            feats = [f for f in feats if f["key"] != "sensor"]
        if "no-step" in keys:
            feats = [f for f in feats if f["key"] != "step"]

        side = None
        if re.search(r"\bLH\b|Driver|Drivers|Left Hand", name, re.I):
            side = "Driver / LH"
        elif re.search(r"\bRH\b|Passenger|Right Hand", name, re.I):
            side = "Passenger / RH"

        if re.search(r"Scratch/Dent", name, re.I):
            condition = "New — Scratch & Dent"
        elif brand:
            condition = "New Aftermarket"
        else:
            condition = "OEM Take-Off"

        products.append({
            "id": pid,
            "sortIndex": idx,
            "slug": sp.get("slug") or slugify(name),
            "sku": (sp.get("sku") or "").strip(),
            "name": name,
            "cat": cat,
            "catName": next((c for c in catnames if c in CAT_BY_NAME), ""),
            "price": sale, "regPrice": reg,
            "save": disc if disc > 0 else 0,
            "savePct": round(disc / reg * 100) if reg and disc > 0 else 0,
            "inStock": True, "qty": qty, STOCK_HINT_KEY: store_oos,
            "url": sp.get("permalink", ""),
            "desc": clean(sp.get("description")) or clean(sp.get("short_description")),
            "yearFrom": y0, "yearTo": y1,
            "makes": makes, "models": models,
            "color": color, "brand": brand, "side": side,
            "condition": condition, "features": feats,
            "images": shots_by_id.get(str(pid), []),
            "mo": max(55, round(sale / 12)) if sale else 55,
        })

    # ---- fold in the Facebook catalogue ----
    fb, fb_held = facebook_products(len(products))
    products.extend(fb)

    # ---- fold in the Ranch Hand catalogue ----
    rh, rh_held = ranchhand_products(len(products))
    products.extend(rh)
    if rh:
        print("  ranch hand: %d published, %d held" % (len(rh), rh_held))

    # ---- permalinks: one slug, one product ----
    # Runs here, after the last fold, so it sees the whole merged catalogue —
    # most of the collisions were between sources, not inside one.
    dedupe_slugs(products)

    # ---- merchandising: prices and availability ----
    # Must run before the block below. Categories derive minPrice/maxPrice/inStock
    # from these products, and would otherwise describe the imported catalogue
    # rather than the published one.
    merchandise(products)

    # ---- categories ----
    cats = []
    for slug, nm, tag, blurb in CATEGORIES:
        items = [p for p in products if p["cat"] == slug]
        prices = [p["price"] for p in items if p["price"]]
        hero = next((p["images"][0]["thumb"] for p in items if p["images"]), None)
        # Measured, not assumed: the store derivatives are a square 300px tier but the
        # Facebook imports are whatever size the CDN handed back. The homepage writes
        # these onto the <img> so the tile has an aspect ratio before the file lands.
        hero_wh = image_dims(hero) or (0, 0)
        cats.append({
            "slug": slug, "name": nm, "tagline": tag, "intro": blurb,
            # The thumb derivative, not the full-size shot. The homepage draws all
            # 13 of these at once as a decorative tile background, cropped with
            # object-fit:cover and greyscaled — nothing about that render can use
            # the extra resolution, and the -main tier cost ~1.08 MB of the home
            # page for it. Facebook imports have no separate derivative, so their
            # "thumb" is the same file and this is a no-op for those three.
            "hero": hero,
            # Shipped so the <img> can carry width/height and reserve its box. The
            # tile is absolutely positioned at inset:0, so these never size it —
            # they only give the box an intrinsic ratio, which is what stops the
            # grid reflowing as 13 lazy images land. 0 means "unmeasurable", and
            # the homepage omits the attributes rather than writing a zero.
            "heroW": hero_wh[0],
            "heroH": hero_wh[1],
            "count": len(items),
            "inStock": len([p for p in items if p["inStock"]]),
            "minPrice": min(prices) if prices else 0,
            "maxPrice": max(prices) if prices else 0,
        })

    # ---- YMM index: year -> make -> [models] ----
    ymm = {}
    for p in products:
        if not p["yearFrom"]:
            continue
        for y in range(p["yearFrom"], p["yearTo"] + 1):
            for mk in p["makes"]:
                ymm.setdefault(str(y), {}).setdefault(mk, set()).update(
                    models_for(mk, p["models"]) or ["All models"])
    ymm = {y: {mk: sorted(ms) for mk, ms in mks.items()} for y, mks in sorted(ymm.items(), reverse=True)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("/* GENERATED by build/generate_products.py - do not edit by hand.\n")
        f.write("   Sources: data/store-products.json, facebook-products.json, "
                "ranchhand-products.json (%d products, %d categories) */\n"
                % (len(products), len(cats)))
        f.write("window.TTP = window.TTP || {};\n")
        f.write("TTP.products = " + json.dumps(products, ensure_ascii=False, indent=1) + ";\n")
        f.write("TTP.categories = " + json.dumps(cats, ensure_ascii=False, indent=1) + ";\n")
        f.write("TTP.ymm = " + json.dumps(ymm, ensure_ascii=False) + ";\n")

    print("wrote %s" % OUT)

    # ---- sitemap ----
    # Written from the same in-memory catalogue, so it can never drift out of
    # step with what products.js publishes.
    write_sitemap(products, cats)

    print("products: %d (%d store + %d facebook + %d ranch hand) | categories: %d | years: %d"
          % (len(products), len(products) - len(fb) - len(rh), len(fb), len(rh),
             len(cats), len(ymm)))
    if fb_held:
        print("facebook rows held back (needs-review / no photo / no category): %d" % fb_held)
    nopr = [p for p in products if not p["price"]]
    if nopr:
        print("no price — render as 'Call for price': %d" % len(nopr))
    print("in stock: %d | with images: %d | with real SKU: %d"
          % (len([p for p in products if p["inStock"]]),
             len([p for p in products if p["images"]]),
             len([p for p in products if p["sku"]])))
    nofit = [p for p in products if not p["yearFrom"] or not p["makes"]]
    print("unresolved fitment: %d %s" % (len(nofit), [p["name"][:40] for p in nofit[:3]]))
    if fallbacks:
        print("fell back to title parsing: %d" % len(fallbacks))
        for pid, nm, t in fallbacks[:6]:
            print("   %-7s %-52s %s" % (pid, nm, t))
    unmapped = fitment_map.unmapped(seen_terms)
    if unmapped:
        print("!! NEW year-range terms not in build/fitment_map.py: %s" % unmapped)
    if skipped:
        print("skipped (no known part category): %d" % len(skipped))
        for pid, nm, cs in skipped[:8]:
            print("   %-7s %-56s %s" % (pid, nm, cs))


main()
