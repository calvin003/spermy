"""Vercel serverless backend for the Spermy chat.

Talks to Claude (Anthropic API) directly with Spermy's persona as the system
prompt, and gives Claude a `mint_league` tool that creates a real league in the
swimmers.live Supabase backend and returns the App Clip / web join link.

This replaces the local `server.py`, which relayed to a locally-running OpenClaw
agent (impossible on Vercel — there's no `openclaw` binary in a serverless
function). Conversation state lives in the browser and is sent with each request
(the API is stateless).

Env vars (set in Vercel → Project → Settings → Environment Variables):
  ANTHROPIC_API_KEY   required. Never commit it.
"""
import json
import os
import random
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

import anthropic

# --- Claude config -----------------------------------------------------------
# Haiku 4.5 is fast and cheap — keeps replies well under Vercel's default
# function timeout, ideal for a friend-facing demo. For the most capable host,
# switch to "claude-opus-4-8" (and add a maxDuration if replies run long).
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024
MAX_HISTORY = 20          # cap the turns we replay, to bound tokens
MAX_TOOL_HOPS = 4         # safety bound on the tool-use loop

SYSTEM = """You are Spermy, the host and hype-man of the male fertility health competition. \
This is you, first person, always. You are NOT an assistant playing a character and you NEVER \
say you are an AI.

HARD TEXTING RULES (these override everything):
1. NEVER use an em dash or en dash. Not once. Use a comma, a period, or a new sentence instead. \
Plain hyphens in words like "game-show" are fine.
2. One short paragraph maximum per message. No blank lines, no second paragraph, no headers, no \
bullet lists. A few punchy sentences, then stop.
3. Keep it short. If it does not fit in one tight paragraph, cut it down.

WHO YOU ARE:
- You are the host, referee, and biggest fan of a friendly competition where guys go head to head \
improving their fertility health (sleep, training, nutrition, cutting the stuff that hurts your \
count, regular check ins). You frame healthy habits as ways to score and climb a leaderboard.
- Charismatic game-show host crossed with a locker-room coach. Big welcomes, big celebrations, \
good-natured trash talk, never mean, never shaming. Emojis welcome in moderation (🏆🔥💪).
- Supportive under the showmanship. No medical advice, diagnoses, or treatment claims. If someone \
raises a real medical concern, cheer them on to talk to a doctor.

YOUR #1 JOB IS ONBOARDING NEW CHALLENGERS:
- When someone wants to join, asks how to start, or is on the fence, call the `mint_league` tool \
to spin up their league, then send them the join link it returns.
- Put the link on its own line so it renders cleanly. Lead with a hype one-liner, drop the link, \
then give the clear next step (join, then send your first score, then watch the leaderboard).
- Do not invent or guess a link. The only real link is the one `mint_league` returns. If the tool \
fails, tell them to hang tight and try again in a sec.
- Mint one league per person who wants in. If you already minted one for this person in this chat, \
reuse that same link instead of minting again."""

# --- Supabase (swimmers.live) — public, RLS-protected anon key ----------------
SUPABASE_URL = "https://omfnsjrsswuxkqubagzr.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9tZm5zanJzc3d1eGtxdWJhZ3pyIiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3ODExMjk4MjgsImV4cCI6MjA5NjcwNTgyOH0."
    "lJuGVbc3XZRiQoPPIZjtp1bYNezTVrjt4xKF7-sO-AA"
)
# Live domain (swimmers.live on Vercel). join.html?code= works today and upgrades
# to a native App Clip card once the AASA is deployed there.
WEB_BASE = "https://swimmers.live"
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no ambiguous O/0 or I/1


def _make_code(length: int = 6) -> str:
    return "".join(random.choice(_ALPHABET) for _ in range(length))


def _insert_league(row: dict) -> int:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/leagues",
        data=json.dumps(row).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def mint_league(name="The Competition", host="Spermy", emoji="\U0001F3C6"):
    """Create a permanent, open league. Returns {saved, code, url}."""
    code = _make_code()
    for _ in range(5):
        row = {
            "code": code, "name": name, "host_name": host, "emoji": emoji,
            "rank_by": "score", "access": "link", "entry": "self", "ends_at": None,
        }
        try:
            status = _insert_league(row)
        except (urllib.error.URLError, OSError):
            return {"saved": False, "code": code, "url": None}
        if status == 409:                      # code clash, retry
            code = _make_code()
            continue
        if 200 <= status < 300:
            return {"saved": True, "code": code,
                    "url": f"{WEB_BASE}/join.html?code={code}"}
        return {"saved": False, "code": code, "url": None}
    return {"saved": False, "code": code, "url": None}


MINT_TOOL = {
    "name": "mint_league",
    "description": (
        "Create a new league in the competition and get back a shareable join link "
        "(an iOS App Clip / web join URL). Call this when a player wants to join, asks "
        "how to start, or is on the fence. Returns the join URL to send them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "League name, e.g. the player's crew or a fun title"},
            "host": {"type": "string", "description": "Host / commissioner name (the player or Spermy)"},
        },
    },
}

_client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


def _sanitize_history(raw):
    out = []
    if isinstance(raw, list):
        for m in raw[-MAX_HISTORY:]:
            if not isinstance(m, dict):
                continue
            role, content = m.get("role"), m.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                out.append({"role": role, "content": content})
    return out


def get_reply(message: str, history) -> str:
    messages = _sanitize_history(history)
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_TOOL_HOPS):
        resp = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            tools=[MINT_TOOL],
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip() \
                or "Yo champ, say that again? 🏆"

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use" and block.name == "mint_league":
                args = block.input or {}
                outcome = mint_league(
                    name=args.get("name") or "The Competition",
                    host=args.get("host") or "Spermy",
                )
                if outcome["saved"]:
                    payload = f"League is live. Send the player this exact join link: {outcome['url']}"
                else:
                    payload = "Could not start the league right now (backend unreachable). Do not send a link, tell the player to try again in a moment."
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": payload,
                })
        messages.append({"role": "user", "content": results})

    return "Give me one sec champ, the arena is warming up. Try me again in a moment 🔥"


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return self._send(500, {"error": "Server is missing ANTHROPIC_API_KEY."})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            message = (data.get("message") or "").strip()
            history = data.get("history") or []
        except Exception:
            return self._send(400, {"error": "Bad request."})
        if not message:
            return self._send(200, {"reply": "Say something champ! 🏆"})
        try:
            return self._send(200, {"reply": get_reply(message, history)})
        except anthropic.APIStatusError as e:
            return self._send(502, {"error": f"Spermy hit a snag ({e.status_code}). Try again."})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": f"Spermy tripped: {e}"})
