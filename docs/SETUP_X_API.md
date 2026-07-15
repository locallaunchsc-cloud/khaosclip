# X API setup

You need four credentials so KhaosClip can post to YOUR account.

## 1. Get developer access
1. Go to https://developer.x.com and sign in with the account that will post clips
2. Create a Project + App (Free tier works for testing; Basic recommended for daily streaming)

## 2. Set app permissions (critical)
- App settings → **User authentication settings** → Set up
- App permissions: **Read and write**
- Type of App: Native App / Web App (either works)
- Callback URL: `http://localhost` (required field, unused by us)

## 3. Generate keys
Keys & Tokens tab:
- **API Key and Secret** → `X_API_KEY`, `X_API_SECRET`
- **Access Token and Secret** → `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`
  - If you generated the access token BEFORE setting Read+Write, regenerate it —
    tokens are stamped with the permission level at creation time.

## 4. Fill in `.env` and verify
```
khaosclip doctor          # credentials check
khaosclip test some.mp4 --post   # full end-to-end: process + post for real
```

## Costs (2026 pay-per-use — the free tier is gone)
X moved to pay-per-use in Feb 2026. New developers load credits in the
Developer Console (card required) and pay per call:
- Plain post (video, no link): ~$0.015 → 100 clips/month ≈ $1.50
- ⚠️ Post containing ANY link: ~$0.20 (13x) — keep captions link-free
- Reading your own posts (khaosclip stats): ~$0.001 each — pennies
- Media uploads are chunked at 4MB; a 60s 1080x1920 clip is typically 8–15MB

**Don't want a dev account at all?** Use cloud mode — connect once via the
relay's OAuth page, no keys, no card, no dev account. See cloud/README.md.

## Security
- `.env` is gitignored. Never commit keys. Never post screenshots of the
  Keys & Tokens page (yes, people do this).
- The access token can post as you. Treat it like a password.
