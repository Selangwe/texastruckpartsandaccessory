/* Downloads every Facebook CDN image in the scraper export before the signed URLs
   expire (oe= param: 2026-08-19T10:18Z). Flat staging by media id; the post->image
   mapping is rebuilt separately from the same export, so grabbing first is safe.
   Resumable: files already on disk are skipped. */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.dirname(__dirname);
const LIST = path.join(ROOT, 'data', 'facebook-image-urls.txt');
const DEST = path.join(ROOT, 'assets', 'img', '_facebook');

if (!fs.existsSync(LIST)) {
  console.error('No ' + LIST + ' — run: node build/parse_facebook.js <export-file>');
  process.exit(1);
}

fs.mkdirSync(DEST, { recursive: true });
const urls = fs.readFileSync(LIST, 'utf8').split('\n').filter(Boolean);

let ok = 0, skip = 0, fail = 0, bytes = 0;
const failures = [];

urls.forEach((u, i) => {
  // filename core: <photoid>_<mediaid>_<hash>_n.jpg
  const m = u.split('?')[0].match(/\/([^/]+\.(?:jpg|jpeg|png|webp))$/i);
  const name = m ? m[1] : 'img' + i + '.jpg';
  const dest = DEST + '/' + name;

  if (fs.existsSync(dest) && fs.statSync(dest).size > 0) { skip++; return; }

  try {
    execFileSync('curl', ['-sL', '--fail', '--max-time', '45', '-o', dest, u], { stdio: 'pipe' });
    const sz = fs.statSync(dest).size;
    if (sz === 0) throw new Error('empty');
    bytes += sz; ok++;
  } catch (e) {
    fail++; failures.push(name);
    try { fs.unlinkSync(dest); } catch (_) {}
  }
  if ((i + 1) % 40 === 0) {
    console.log(`[${i + 1}/${urls.length}] ok=${ok} skip=${skip} fail=${fail} ${(bytes / 1048576).toFixed(1)}MB`);
  }
});

console.log(`\nDONE — ${ok} downloaded, ${skip} already present, ${fail} failed, ${(bytes / 1048576).toFixed(1)} MB`);
if (failures.length) console.log('failed:', failures.slice(0, 15).join(', '));
fs.writeFileSync(path.join(ROOT, 'data', 'facebook-image-failures.txt'), failures.join('\n'));
