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

## Rate limits & costs
- Free tier: enough to test (limited posts/month)
- Basic ($200/mo): comfortable for daily streaming volume
- Media uploads are chunked at 4MB; a 45s 1080x1920 clip is typically 8–15MB

## Security
- `.env` is gitignored. Never commit keys. Never post screenshots of the
  Keys & Tokens page (yes, people do this).
- The access token can post as you. Treat it like a password.
