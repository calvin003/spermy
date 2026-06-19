# Spermy 🏆

A chatbot that hosts **the male fertility health competition**. Spermy welcomes
challengers, explains the rules, keeps score, and onboards new players by minting
a real league and texting back the **swimmers.live App Clip / web join link**.

This repo is the **deployable web version**: an Apple-style landing page with a
chat widget that talks to **Claude** (Anthropic API) directly, with Spermy's
persona as the system prompt. It runs as a Vercel project — no servers to manage.

## How it works

```
Browser (index.html)  ──POST /api/chat──▶  Vercel Python function (api/chat.py)
                                              │  Claude (claude-opus-4-8) + persona
                                              │  mint_league tool ─▶ Supabase `leagues`
                                              ▼
                                          { reply }  (with a https://swimmers.live/join.html?code=… link)
```

- `index.html` — static landing page + chat UI. Keeps the conversation in the
  browser and sends it with each request (the API is stateless).
- `api/chat.py` — Vercel serverless function. Runs Spermy on Claude, and gives
  Claude a `mint_league` tool that creates a league in the shared swimmers.live
  Supabase backend and returns the join link.
- `server.py` — the original **local** version that relays to a locally-running
  OpenClaw agent. Kept for reference; it does **not** run on Vercel (no `openclaw`
  binary in a serverless function). Use the Vercel path above for hosting.

## Deploy to Vercel

1. Push this repo to GitHub (already at `github.com/calvin003/spermy`).
2. In Vercel: **Add New → Project → Import** this repo. Framework preset: **Other**
   (Vercel auto-detects the static site + the Python function in `api/`).
3. **Settings → Environment Variables**, add:
   - `ANTHROPIC_API_KEY` = your Anthropic API key  *(required, never commit it)*
4. **Deploy.** Share the URL with your friend.

That's it. The Supabase anon key in `api/chat.py` is the public, RLS-protected
key (same one shipped in the swimmers.live site) — safe to commit; it can only
insert leagues, not read anyone's data.

## Config

- **Model** — `MODEL` in `api/chat.py` (`claude-opus-4-8`). For a snappier and
  cheaper demo, switch to `claude-haiku-4-5`.
- **Join link domain** — `WEB_BASE` (`https://swimmers.live`). The link works as
  a web join today and upgrades to a native iOS App Clip card once the
  apple-app-site-association is deployed at `swimmers.live/.well-known/` and the
  App Clip Experience is registered in App Store Connect.

## Local dev

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
vercel dev        # runs the static site + the Python function locally
```

(`vercel dev` needs the Vercel CLI: `npm i -g vercel`.)

## Note

Spermy is a demo and not medical advice.
