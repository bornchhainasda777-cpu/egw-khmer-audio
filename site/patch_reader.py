# Adds GitHub audio (manifest.json) support to the reader: run in ~/egw
import sys
p = 'public/app.js'
s = open(p).read()
if 'MANIFEST_URL' in s:
    print('already patched'); sys.exit(0)
a = "let book = null, chapters = [], unsubCh = null, ch = null;"
b = a + """
const AUDIO_REPO = 'bornchhainasda777-cpu/egw-khmer-audio';
const MANIFEST_URL = 'https://raw.githubusercontent.com/' + AUDIO_REPO + '/main/manifest.json';
const AUDIO_PREFIX = 'https://github.com/' + AUDIO_REPO + '/releases/download/';
let manifest = {};
const withAI = (bid, c) => { const m = manifest[bid + '/' + c.id]; if (!c.audio && m && typeof m.url === 'string' && m.url.startsWith(AUDIO_PREFIX)) c.audio = { urls: [m.url] }; return c; };
fetch(MANIFEST_URL, { cache: 'no-cache' }).then(r => r.ok ? r.json() : {}).then(j => { manifest = j && typeof j === 'object' ? j : {}; if (book && chapters.length) { chapters.forEach(c => withAI(book.id, c)); renderBook(); } }).catch(() => {});"""
c = "chapters = s.docs.map(d => cleanCh(d.id, d.data()));"
d = "chapters = s.docs.map(d => withAI(b.id, cleanCh(d.id, d.data())));"
assert s.count(a) == 1 and s.count(c) == 1, 'app.js not as expected'
open(p, 'w').write(s.replace(a, b).replace(c, d))
print('patched')
