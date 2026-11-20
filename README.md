# EGW Khmer audio

Makes Khmer audio for new chapters of https://egw-khmer.web.app automatically, every hour.

1. Reads the next chapter that has text but no audio (from the app's database).
2. Reads it aloud with Kiri TTS, joins the pieces into one MP3 with ffmpeg and adds `music.mp3` quietly underneath (if the file is here).
3. Uploads the MP3 to this repository's Releases and adds its link to `manifest.json`. The website shows a play button.

## Settings
- **Secret `KIRI_API_KEY`** (Settings → Secrets and variables → Actions → Secrets): your Kiri API key. Required.
- Variables (same page → Variables), all optional:
  - `KIRI_VOICE` – Kiri voice name (default `Maly`)
  - `MONTHLY_LIMIT` – most chapters per month, to protect your credits (default `6`)
  - `MUSIC_VOLUME` – music loudness under the voice (default `0.12`)
  - `PRIORITY_BOOKS` – book ids to do first (default `desire-of-ages`)
- **Music:** upload a file named `music.mp3` (music you are allowed to use). Without it, the audio is voice only.

To pause: Actions → "Make Khmer audio" → ⋯ → Disable workflow.
