/* Facebook posts export -> product catalogue, second pass.

   Facebook posts are not a product feed. A post can be a listing, a promo, a
   disclaimer, or the same listing reposted a week later, and roughly a third of the
   copy is Spanish. So this classifies rather than assuming, and marks anything it is
   not confident about for human review instead of quietly inventing a product. */
/* Usage:  node build/parse_facebook.js <export-file>
   Accepts the Apify facebook-posts-scraper CSV/XLSX text, or a Drive
   read_file_content dump of the form {"fileContent": "..."}.

   Output: data/facebook-products.json
   Then:   node build/fetch_facebook_images.js   (grab the photos before the
           signed CDN URLs expire — they are valid for about four days) */
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const OUT = path.join(ROOT, 'data');
const SRC = process.argv[2] || path.join(ROOT, 'data', 'facebook-export.csv');

if (!fs.existsSync(SRC)) {
  console.error('No export at ' + SRC + '\nUsage: node build/parse_facebook.js <export-file>');
  process.exit(1);
}

let c = fs.readFileSync(SRC, 'utf8');
if (c.trimStart().startsWith('{')) {
  try { c = JSON.parse(c).fileContent || c; } catch (e) { /* plain CSV after all */ }
}
const unesc = s => s.replace(/\\([_&*\[\]()#~`>+\-=|{}.!])/g, '$1');
const norm = s => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

/* ---- anchors ----
   Posts appear either as permalink.php?story_fbid=pfbid… or as a /share/ shortlink.
   Anchoring on only the first kind left the share-linked posts unanchored, so their
   window merged into the previous post — that is what produced single "products"
   carrying 38 photos and four different makes. */
const anchors = [];
const seen = new Set();
let m;
const postRe = /story\\?_fbid=(pfbid[0-9A-Za-z]+)|facebook\.com\\?\/share\\?\/([0-9A-Za-z]+)/g;
while ((m = postRe.exec(c))) {
  const id = m[1] || ('share:' + m[2]);
  if (seen.has(id)) continue;
  seen.add(id);
  anchors.push({ fbid: id, at: m.index });
}
anchors.sort((a, b) => a.at - b.at);
anchors.forEach((a, i) => { a.end = i + 1 < anchors.length ? anchors[i + 1].at : c.length; });

/* ---- per-post text + images ---- */
const imgRe = /https:\/\/scontent[^,\s"]+/g;
const raw = anchors.map(a => {
  const win = c.slice(a.at, a.end);
  const imageUrls = [...new Set((win.match(imgRe) || []).map(unesc))];
  const images = imageUrls
    .map(u => (u.split('?')[0].match(/\/([^/]+\.(?:jpg|jpeg|png|webp))$/i) || [])[1])
    .filter(Boolean);
  /* A post body is spread across several columns (message, ocrText, link preview),
     so the whole window's readable prose gets joined in document order. Taking only
     the longest fragment lost the product line on ~half the posts and kept the
     marketing tail — "Perfect for ranch trucks…" with no mention of what it fits. */
  const runs = [...new Set((win.match(/[A-Za-z][A-Za-z0-9 ,.'\/&$%!?:()\-]{28,}/g) || [])
    .map(unesc)
    .map(s => s.replace(/\s+/g, ' ').trim())
    .filter(s => /[a-z]{3}/.test(s) && !/,{4,}/.test(s) && !/^X?Ifr\b/.test(s)
                 && !/^pfbid/.test(s) && !/facebook\.com|fbcdn|mibextid|scontent/.test(s)
                 // drop opaque API tokens (long, unspaced, mixed case+digits) —
                 // they were leaking into product names
                 && !(/^[A-Za-z0-9_-]{20,}&?$/.test(s) && !/\s/.test(s))))];
  return { fbid: a.fbid, text: runs.join(" · "), images, imageUrls };
});

/* ---- classify ---- */
const PART = /bumper|grill(e)? guard|brush guard|tailgate|tail ?light|truck bed|bed liner|tool ?box|estribo|running board|nerf bar|step bar|winch|headache rack|fender|wheel|rim|tire|hitch|mud ?flap/i;
const PROMO = /^(please verify|sold as-is|message for more|dm for|call us|we finance today|follow us|check out our page)/i;

const MAKES = [
  [/\bford\b|f-?[123]50|f-?450|super ?duty|bronco|ranger/i, 'Ford'],
  [/\bchev(y|rolet)\b|silverado|colorado/i, 'Chevrolet'],
  [/\bgmc\b|sierra|canyon/i, 'GMC'],
  [/\bram\b|\bdodge\b/i, 'Ram'],
  [/\btoyota\b|tundra|tacoma/i, 'Toyota']
];
const BRANDS = [/tough country/i, /ranch hand/i, /one source/i, /road armor/i,
  /fab fours/i, /westin/i, /weather ?guard/i, /camlocker/i, /\buws\b/i, /\brki\b/i];

/* Scores every category and takes the strongest signal, rather than returning on the
   first regex that happens to match. A post can mention a tool box in passing while
   selling a bumper ("great setup for your work truck"), and first-match ordering put
   those in the wrong aisle. Weight reflects how decisive a phrase is: "crossover box"
   names the product, "box" alone does not. */
const CAT_SIGNALS = [
  ['tool-boxes', [
    [/crossover (tool ?)?box|chest box|side ?mount box|\btool ?box(es)?\b|toolbox/i, 5],
    [/weather ?guard|camlocker|\buws\b|\brki\b/i, 2],
    [/lockable|includes 2 keys|secure storage|storage box/i, 2]
  ]],
  ['running-boards', [
    [/running ?board|nerf bar|step bar|side step|rock slider/i, 5],
    [/estribo/i, 5]
  ]],
  ['truck-racks', [
    [/ladder rack|headache rack|truck rack|utility rack|cab rack/i, 5],
    [/ladders, tools, pipes|for ladders|carry pipe/i, 2]
  ]],
  ['grill-guards', [
    [/grill(e)? guard|brush guard|bull bar|push bar/i, 5]
  ]],
  ['rear-replacement-bumpers', [
    [/rear (replacement )?bumper/i, 5],
    [/\brear bumper\b/i, 4]
  ]],
  ['front-replacement-bumpers', [
    [/front (replacement )?bumper|replacement bumper/i, 5],
    [/\bfront bumper\b/i, 4],
    [/\bbumper\b/i, 1]
  ]],
  ['tailgate', [[/tailgate/i, 5]]],
  ['tail-lights', [[/tail ?light/i, 4]]],
  ['wheels-tires', [[/\bwheels?\b|\brims?\b|\btires?\b/i, 3]]],
  ['truck-bed', [[/truck bed\b|bed ?liner|spray ?in/i, 4]]]
];

/* The headline decides which aisle, the body only breaks ties within it.

   A cross-sell post — "a Ranch Hand bumper … pair it with a Weather Guard toolbox" —
   names two products, and scoring the whole body filed that bumper under tool boxes
   because "toolbox" is a more distinctive word than "bumper". So: if any category is
   named in the headline, only those categories are eligible at all. Body scoring is
   the fallback for posts whose headline names nothing. */
function categorise(t, headline) {
  const head = headline || '';

  const score = (entry, text) => entry[1].reduce(
    (n, sig) => n + (sig[0].test(text) ? sig[1] : 0), 0);

  const named = CAT_SIGNALS.filter(e => score(e, head) > 0);
  const pool = named.length ? named : CAT_SIGNALS;

  let best = null, bestScore = 0;
  pool.forEach(function (entry) {
    // within the eligible pool, headline evidence still outweighs body evidence
    const s = score(entry, head) * 3 + score(entry, t);
    if (s > bestScore) { bestScore = s; best = entry[0]; }
  });
  return bestScore >= 3 ? best : null;
}

/* Title = the first fragment that actually names a part, trimmed before the pitch. */
function title(t) {
  const frags = t.split(' · ');
  let s = frags.find(f => PART.test(f) && /[A-Z]/.test(f)) || frags[0] || '';
  s = s.split(/\s(?:We |WE )?FINANCE\b/)[0];
  s = s.split(/\b(?:Brand new|Bumper (?:is|works|comes)|Will work|Has hardware|Perfect for|Great for|Upgrade your|Message (?:for|with))\b/)[0];
  return s.replace(/\s+/g, ' ').trim().slice(0, 95);
}

const titleCase = s => s ? s.toLowerCase().replace(/\b\w/g, ch => ch.toUpperCase()) : null;

const byText = new Map();
const rows = [];

raw.forEach(p => {
  const t = p.text;
  const isProduct = t.length > 45 && PART.test(t) && !PROMO.test(t);
  const key = norm(title(t)).slice(0, 70);

  const head = title(t);
  const rec = {
    fbid: p.fbid,
    name: head,
    cat: categorise(t, head),
    brand: titleCase((BRANDS.map(re => t.match(re)).find(Boolean) || [null])[0]),
    makes: MAKES.filter(([re]) => re.test(t)).map(([, n]) => n),
    models: [...new Set((t.match(/F-?[1234]50|Silverado ?(?:HD )?[23]500|Sierra ?(?:HD )?[23]500|Ram ?[123]500|Super ?Duty|Tundra|Tacoma/gi) || [])
      .map(s => s.replace(/\s+/g, ' ').trim()))],
    years: [...new Set((t.match(/\b20[0-3]\d\b/g) || []).map(Number))].sort(),
    price: Number(((t.match(/\$\s?([\d,]{3,7})/) || [])[1] || '').replace(/,/g, '')) || null,
    financed: /we finance|financiamos|financ/i.test(t),
    spanish: /\b(disponible|estribo|para el|nuevo|env[ií]o|precio|camioneta)\b/i.test(t),
    images: p.images,
    text: t,
    status: null
  };
  rec.yearFrom = rec.years[0] || null;
  rec.yearTo = rec.years[rec.years.length - 1] || null;

  if (!isProduct) { rec.status = 'not-a-product'; rows.push(rec); return; }
  if (byText.has(key)) {                       // repost of an existing listing
    const first = byText.get(key);
    first.images = [...new Set(first.images.concat(rec.images))];
    first.reposts = (first.reposts || 0) + 1;
    rec.status = 'duplicate-of:' + first.fbid;
    rows.push(rec);
    return;
  }
  /* Tool boxes, racks and steps are sold by bed width and cab config, not by make —
     a missing make is normal for those, so requiring one would park the entire
     accessories side of the catalogue in the review queue forever. */
  const UNIVERSAL_FIT = ['tool-boxes', 'truck-racks', 'running-boards'];
  const needsMake = !UNIVERSAL_FIT.includes(rec.cat);
  rec.universalFit = !needsMake;

  /* A Facebook album post tops out around 10 photos. More than that means the window
     still merged two posts, so the fitment on it cannot be trusted. */
  const bled = rec.images.length > 10 || rec.makes.length > 2 ||
               (rec.yearFrom && rec.yearTo - rec.yearFrom > 15);

  rec.status = (!rec.cat || !rec.images.length || bled || (needsMake && !rec.makes.length))
    ? 'needs-review' : 'ok';
  if (bled) rec.reviewReason = 'window may span two posts — verify fitment and photos';
  else if (!rec.images.length) rec.reviewReason = 'no photos found';
  else if (!rec.cat) rec.reviewReason = 'could not categorise';
  else if (needsMake && !rec.makes.length) rec.reviewReason = 'no make detected in copy';
  byText.set(key, rec);
  rows.push(rec);
});

const products = rows.filter(r => r.status === 'ok' || r.status === 'needs-review');
const dropped = rows.filter(r => r.status === 'not-a-product');
const dupes = rows.filter(r => String(r.status).startsWith('duplicate'));

fs.mkdirSync(OUT, { recursive: true });
fs.writeFileSync(path.join(OUT, 'facebook-image-urls.txt'),
  [...new Set(raw.flatMap(p => p.imageUrls || []))].join('\n'));

fs.writeFileSync(OUT + '/facebook-products.json', JSON.stringify({
  generated: new Date().toISOString(),
  source: path.basename(SRC),
  note: 'Image filenames map into assets/img/_facebook/. Facebook CDN URLs in the export expire 2026-08-19T10:18Z; the files were downloaded before then.',
  counts: { posts: rows.length, products: products.length, duplicates: dupes.length, notProducts: dropped.length },
  products
}, null, 1));

console.log('posts parsed      :', rows.length);
console.log('distinct products :', products.length,
  '(ok', products.filter(p => p.status === 'ok').length,
  '/ needs-review', products.filter(p => p.status === 'needs-review').length + ')');
console.log('reposts merged    :', dupes.length);
console.log('non-product posts :', dropped.length);
console.log('images referenced :', [...new Set(products.flatMap(p => p.images))].length);
console.log('bilingual (ES)    :', products.filter(p => p.spanish).length);
console.log('with a price      :', products.filter(p => p.price).length);

const tally = f => products.reduce((a, p) => { const k = f(p) || '—'; a[k] = (a[k] || 0) + 1; return a; }, {});
console.log('\nby category:', tally(p => p.cat));
console.log('by make    :', tally(p => p.makes.join('/')));
console.log('by brand   :', tally(p => p.brand));
