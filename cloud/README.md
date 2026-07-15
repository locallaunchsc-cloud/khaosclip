# NameiT Cloud Relay

The hosted posting layer. Streamers connect their X account ONCE with OAuth —
no developer account, no API keys on their side. Their local agent uploads
clips here; the relay posts to X as them.

## Setup

1. In YOUR X developer app (developer.x.com), enable OAuth 2.0:
   - Type: Web App
   - Callback URL: `https://your-relay-domain.com/auth/callback`
   - Scopes needed: tweet.read, tweet.write, users.read, media.write, offline.access
   - Copy the OAuth 2.0 Client ID and Client Secret

2. Deploy (Railway is the fastest):
   ```
   railway init && railway up
   railway variables set X_CLIENT_ID=... X_CLIENT_SECRET=... RELAY_BASE_URL=https://your-domain
   ```
   Or Fly.io / Render — anything that runs the Dockerfile with a persistent volume
   for relay.db (or swap sqlite3 for Postgres in app.py when you outgrow it).

3. Streamer onboarding = send them one link:
   `https://your-relay-domain.com/auth/login`
   They click Connect, copy two lines into their .env, done. 60 seconds.

## Local agent side

In the streamer's `.env`:
```
CLOUD_MODE=true
NAMEIT_API_KEY=nameit_xxxxx
RELAY_URL=https://your-relay-domain.com
```

The agent now posts through the relay — their clips, their account, your app.

## This is the business

Local mode is free and open — it proves the product. Cloud mode is the
subscription: no setup, plus (roadmap) cloud caption AI, analytics dashboard,
priority processing. $20-30/mo per streamer.
