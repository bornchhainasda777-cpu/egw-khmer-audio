# Fix: wait (max 5 s) for the audio list before opening a chapter, so the play button
# uses the AI audio even when the chapter opens before the list has loaded. Run in ~/egw
import sys
p = 'public/app.js'
s = open(p).read()
if 'manifestReady' in s:
    print('already patched'); sys.exit(0)
a = "fetch(MANIFEST_URL, { cache: 'no-cache' })"
b = "const manifestReady = fetch(MANIFEST_URL, { cache: 'no-cache' })"
c = "  stopAll(); ch = c;\n"
d = "  if (!c.audio && book) { await Promise.race([manifestReady, new Promise(r => setTimeout(r, 5000))]); withAI(book.id, c); }\n" + c
assert s.count(a) == 1 and s.count(c) == 1, 'app.js not as expected'
open(p, 'w').write(s.replace(a, b).replace(c, d))
print('patched')
