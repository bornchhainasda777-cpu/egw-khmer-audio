# Faster audio start: connect to GitHub early, remember the audio list on the phone,
# and pre-load the chapter audio for people who listen. Run in ~/egw
import sys
p = 'public/app.js'; h = 'public/index.html'
s = open(p).read(); x = open(h).read()
if 'egw-ai-manifest' in s:
    print('already patched'); sys.exit(0)
R = [
  ("let manifest = {};",
   "let manifest = (() => { try { return JSON.parse(localStorage.getItem('egw-ai-manifest') || '{}') || {}; } catch (e) { return {}; } })();"),
  ("manifest = j && typeof j === 'object' ? j : {};",
   "manifest = j && typeof j === 'object' ? j : {}; try { localStorage.setItem('egw-ai-manifest', JSON.stringify(manifest)); } catch (e) {}"),
  (".then(u => { if (ch !== c) return; aud.src = u;",
   ".then(u => { if (ch !== c) return; try { aud.preload = localStorage.getItem('egw-listens') ? 'auto' : 'metadata'; } catch (e) {} aud.src = u;"),
  ("aud.playbackRate = opt.rate; aud.play().catch(",
   "aud.playbackRate = opt.rate; try { localStorage.setItem('egw-listens', '1'); } catch (e) {} aud.play().catch("),
]
for a, b in R:
    assert s.count(a) == 1, 'app.js not as expected: ' + a[:40]
    s = s.replace(a, b)
a = '<link rel="preconnect" href="https://fonts.googleapis.com">'
assert x.count(a) == 1, 'index.html not as expected'
x = x.replace(a, a + '\n<link rel="preconnect" href="https://github.com">\n<link rel="preconnect" href="https://release-assets.githubusercontent.com">\n<link rel="preconnect" href="https://raw.githubusercontent.com" crossorigin>')
open(p, 'w').write(s); open(h, 'w').write(x)
print('patched')
