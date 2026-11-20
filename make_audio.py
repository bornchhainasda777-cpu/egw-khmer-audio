#!/usr/bin/env python3
"""Makes Khmer audio for new chapters of egw-khmer.web.app.

Each run: finds the next chapter that has text but no audio, reads it with Kiri TTS
(several pieces at once), joins the pieces into one MP3 with ffmpeg, mixes in music.mp3
(if present) quietly underneath, uploads it to a GitHub Release, and records the link
in manifest.json. The website reads manifest.json and shows a play button.
"""
import concurrent.futures as cf, hashlib, json, os, re, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from datetime import datetime, timezone

PROJECT = os.environ.get('FIREBASE_PROJECT', 'egw-khmer')
FB_KEY = os.environ.get('FIREBASE_API_KEY', 'AIzaSyA8-PpJgl5q3Hbkr05vx6bFls17z7BWTi8')  # public web key
REPO = os.environ.get('GITHUB_REPOSITORY', 'bornchhainasda777-cpu/egw-khmer-audio')
KIRI_KEY = os.environ.get('KIRI_API_KEY', '')
VOICE = os.environ.get('KIRI_VOICE') or 'Maly'
MODEL = os.environ.get('KIRI_MODEL') or 'kiritts'
MAX_CHARS = int(os.environ.get('KIRI_CHARS') or 1000)
PARALLEL = int(os.environ.get('PARALLEL') or 4)
MONTHLY_LIMIT = int(os.environ.get('MONTHLY_LIMIT') or 6)      # chapters per month (credits!)
PRIORITY = [b for b in (os.environ.get('PRIORITY_BOOKS') or 'desire-of-ages').split(',') if b]
MUSIC_VOLUME = os.environ.get('MUSIC_VOLUME') or '0.12'
BITRATE = os.environ.get('BITRATE') or '64k'
DRY = os.environ.get('DRY_RUN') == '1'
BUCKET = os.environ.get('STORAGE_BUCKET', '')   # Firebase Storage bucket (fast streaming); empty = GitHub only
NOTE_RE = re.compile(r'^\(ជំពូកនេះបកប្រែដោយម៉ាស៊ីន')
KM = str.maketrans('0123456789', '០១២៣៤៥៦៧៨៩')

def log(*a): print(*a, flush=True)

# ---------------------------------------------------------------- Firestore (public read)
def fs(path, params=None):
    q = {'key': FB_KEY, **(params or {})}
    url = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/{path}?' + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)

def val(f, k):
    v = (f or {}).get(k) or {}
    for t in ('stringValue', 'integerValue', 'doubleValue', 'booleanValue'):
        if t in v: return v[t]
    return None

def find_todo(manifest):
    books = fs('books', {'pageSize': 300}).get('documents', [])
    books.sort(key=lambda b: (0 if b['name'].split('/')[-1] in PRIORITY else 1,
                              PRIORITY.index(b['name'].split('/')[-1]) if b['name'].split('/')[-1] in PRIORITY else 0,
                              float(val(b.get('fields'), 'createdAt') or 0)))
    for b in books:
        bid = b['name'].split('/')[-1]
        chs = fs(f'books/{bid}/chapters', {'pageSize': 300}).get('documents', [])
        chs.sort(key=lambda c: float(val(c.get('fields'), 'n') or 0))
        for c in chs:
            f, cid = c.get('fields', {}), c['name'].split('/')[-1]
            if not float(val(f, 'chars') or 0) or val(f, 'audioId') or val(f, 'noAudio'):
                continue  # no text, has a real recording, or switched off
            m = manifest.get(f'{bid}/{cid}')
            if m and m.get('chars') == int(float(val(f, 'chars') or 0)):
                continue  # already done for this text
            text = val(fs(f'books/{bid}/texts/{cid}').get('fields'), 'text') or ''
            h = hashlib.sha1(text.encode()).hexdigest()[:12]
            if m and m.get('hash') == h:
                continue
            return dict(book=bid, book_title=val(b.get('fields'), 'title') or bid, id=cid,
                        n=int(float(val(f, 'n') or 0)), title=val(f, 'title') or '', text=text, hash=h,
                        chars=int(float(val(f, 'chars') or 0)))
    return None

# ---------------------------------------------------------------- text → pieces
def pieces(n, title, text):
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip() and not NOTE_RE.match(p.strip())]
    allt = '\n'.join([f'ជំពូកទី {str(n).translate(KM)}។ {title}។'] + paras)
    sents = [s.strip() for s in re.split(r'(?<=[។៕?!])\s*|\n+', allt) if s and s.strip()]
    out, cur = [], ''
    def push(s):
        nonlocal cur
        if cur and len(cur) + 1 + len(s) > MAX_CHARS: out.append(cur); cur = ''
        cur = f'{cur} {s}' if cur else s
    for s in sents:
        while len(s) > MAX_CHARS:
            cut = s.rfind(' ', 0, MAX_CHARS)
            if cut < MAX_CHARS // 2: cut = MAX_CHARS
            push(s[:cut]); s = s[cut:].strip()
        push(s)
    if cur: out.append(cur)
    return out

# ---------------------------------------------------------------- Kiri TTS
class OutOfCredits(Exception): pass

def speak(text, path):
    body = {'model': MODEL, 'voice': VOICE, 'input': text, 'response_format': 'mp3'}
    for attempt in range(6):
        req = urllib.request.Request('https://api.kiritts.com/v1/audio/speech', data=json.dumps(body).encode(), method='POST',
                                     headers={'Authorization': 'Bearer ' + KIRI_KEY, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data, ctype = r.read(), r.headers.get('Content-Type', '')
            if 'json' in ctype or 'text' in ctype or len(data) < 500:
                raise RuntimeError('Kiri returned no audio: ' + data[:200].decode('utf-8', 'replace'))
            open(path, 'wb').write(data); return
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode('utf-8', 'replace')
            if e.code == 402 or re.search(r'credit|quota|insufficient', msg, re.I): raise OutOfCredits(msg)
            if e.code == 400 and 'format' in msg and 'response_format' in body:
                body.pop('response_format'); continue
            if e.code == 429 or e.code >= 500:
                time.sleep(10 * (attempt + 1)); continue
            raise RuntimeError(f'Kiri {e.code}: {msg}')
        except (urllib.error.URLError, TimeoutError) as e:
            time.sleep(10 * (attempt + 1))
    raise RuntimeError('Kiri kept failing, will try again next run')

# ---------------------------------------------------------------- ffmpeg
def run(cmd): subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
def duration(p): return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).decode().strip())

def build(parts, out, tmp):
    lst = os.path.join(tmp, 'list.txt')
    open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
    voice = os.path.join(tmp, 'voice.wav')
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-ac', '1', '-ar', '44100', voice])
    d = duration(voice)
    if os.path.exists('music.mp3'):
        fade = max(0, d - 5)
        run(['ffmpeg', '-y', '-i', voice, '-stream_loop', '-1', '-i', 'music.mp3', '-filter_complex',
             f'[1:a]volume={MUSIC_VOLUME},afade=t=in:d=3[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={fade:.2f}:d=5',
             '-ac', '1', '-b:a', BITRATE, out])
    else:
        run(['ffmpeg', '-y', '-i', voice, '-ac', '1', '-b:a', BITRATE, out])
    return d

# ---------------------------------------------------------------- Firebase Storage (fast streaming)
def storage_url(obj):
    return f'https://firebasestorage.googleapis.com/v0/b/{BUCKET}/o/' + urllib.parse.quote(obj, safe='') + '?alt=media'

def to_storage(path, book, name, h):
    obj = f"audio/{book}/{name[:-4]}-{h}.mp3"   # new name for every new recording, so caches never serve an old one
    run(['gcloud', 'storage', 'cp', path, f'gs://{BUCKET}/{obj}', '--content-type=audio/mpeg',
         '--cache-control=public, max-age=31536000'])
    return storage_url(obj)

def migrate(manifest):
    # move chapters that are still only on GitHub to Firebase Storage (no Kiri credits used)
    moved = 0
    for key, m in manifest.items():
        if 'firebasestorage' in m.get('url', ''):
            continue
        book = key.split('/')[0]
        name = m['url'].rsplit('/', 1)[-1]
        tmp = tempfile.mkdtemp()
        run(['gh', 'release', 'download', 'audio-' + book, '-p', name, '-D', tmp])
        m['github'] = m['url']
        m['url'] = to_storage(os.path.join(tmp, name), book, name, m.get('hash', 'x'))
        moved += 1
        log('Moved to Firebase Storage:', key)
    return moved

# ---------------------------------------------------------------- main
def main():
    manifest = json.load(open('manifest.json')) if os.path.exists('manifest.json') else {}
    state = json.load(open('state.json')) if os.path.exists('state.json') else {}
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    if state.get('month') != month: state = {'month': month, 'count': 0}
    if BUCKET and not DRY and migrate(manifest):
        json.dump(manifest, open('manifest.json', 'w'), ensure_ascii=False, indent=1, sort_keys=True)
    if not KIRI_KEY and not DRY: log('No KIRI_API_KEY secret yet — nothing to do.'); return
    if state['count'] >= MONTHLY_LIMIT: log(f'Monthly limit reached ({MONTHLY_LIMIT} chapters). Waiting for next month.'); return
    todo = find_todo(manifest)
    if not todo: log('Every chapter already has audio.'); return
    ps = pieces(todo['n'], todo['title'], todo['text'])
    log(f"Chapter {todo['n']} of {todo['book']} ({todo['id']}): {len(ps)} pieces, voice {VOICE}")
    if DRY: log('Dry run — first piece:', ps[0][:120]); return
    tmp = tempfile.mkdtemp()
    paths = [os.path.join(tmp, f'{i:03d}.mp3') for i in range(len(ps))]
    try:
        with cf.ThreadPoolExecutor(PARALLEL) as ex:
            list(ex.map(lambda a: speak(*a), zip(ps, paths)))
    except OutOfCredits as e:
        log('Kiri: out of credits — stopping until credits are added.', e); return
    name = f"{todo['book']}-{todo['id']}.mp3"
    out = os.path.join(tmp, name)
    secs = build(paths, out, tmp)
    tag = 'audio-' + todo['book']
    if subprocess.run(['gh', 'release', 'view', tag], capture_output=True).returncode != 0:
        run(['gh', 'release', 'create', tag, '--title', 'Audio: ' + todo['book_title'], '--notes', 'Khmer audio for ' + todo['book_title']])
    run(['gh', 'release', 'upload', tag, out, '--clobber'])
    gh_url = f'https://github.com/{REPO}/releases/download/{tag}/{name}'
    url = to_storage(out, todo['book'], name, todo['hash']) if BUCKET else gh_url
    manifest[f"{todo['book']}/{todo['id']}"] = {
        'url': url, 'github': gh_url, 'hash': todo['hash'], 'chars': todo['chars'],
        'secs': round(secs), 'voice': VOICE, 'made': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    state['count'] += 1
    json.dump(manifest, open('manifest.json', 'w'), ensure_ascii=False, indent=1, sort_keys=True)
    json.dump(state, open('state.json', 'w'), indent=1)
    log(f"DONE: {name} ({secs/60:.1f} min). {state['count']}/{MONTHLY_LIMIT} chapters this month.")

if __name__ == '__main__':
    main()
