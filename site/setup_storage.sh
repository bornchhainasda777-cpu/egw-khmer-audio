#!/bin/bash
# Run in Cloud Shell after Firebase Storage is turned on (Blaze plan).
# 1) lets the GitHub uploader write audio, 2) public read rules for audio/, 3) reader accepts Storage links.
set -e
P=egw-khmer
B=egw-khmer.firebasestorage.app
SA=egw-audio-uploader@$P.iam.gserviceaccount.com
cd ~/egw
gcloud storage buckets describe gs://$B --project $P --format='value(location)'
gcloud storage buckets add-iam-policy-binding gs://$B --project $P --member=serviceAccount:$SA --role=roles/storage.objectAdmin >/dev/null
echo "uploader can write"
cat > storage.rules <<'RULES'
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /audio/{rest=**} {
      allow read: if true;
      allow write: if false;
    }
    match /{all=**} {
      allow read, write: if false;
    }
  }
}
RULES
python3 - <<'PY'
import json, sys
j = json.load(open('firebase.json'))
j['storage'] = {'rules': 'storage.rules'}
json.dump(j, open('firebase.json', 'w'), indent=2)
p = 'public/app.js'; s = open(p).read()
pre = "https://firebasestorage.googleapis.com/v0/b/egw-khmer.firebasestorage.app/o/audio%2F"
if pre not in s:
    a = "m.url.startsWith(AUDIO_PREFIX)"
    assert s.count(a) == 1, 'app.js not as expected'
    s = s.replace(a, "(m.url.startsWith(AUDIO_PREFIX) || m.url.startsWith('" + pre + "'))")
    open(p, 'w').write(s)
h = 'public/index.html'; x = open(h).read()
if 'firebasestorage.googleapis.com' not in x:
    a = '<link rel="preconnect" href="https://github.com">'
    assert x.count(a) == 1, 'index.html not as expected'
    x = x.replace(a, '<link rel="preconnect" href="https://firebasestorage.googleapis.com">\n' + a)
    open(h, 'w').write(x)
print('reader updated')
PY
firebase deploy --only storage,hosting --project $P --non-interactive 2>&1 | tail -3
echo STORAGE-READY
