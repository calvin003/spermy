#!/usr/bin/env python3
"""Local Apple-style landing page for the Spermy OpenClaw agent.

Serves a dummy marketing site on http://localhost:7337 with a chat widget in
the center that relays to the OpenClaw 'calvin' agent (persona = Spermy) via
`openclaw agent --json`. No iMessage / Twilio — purely local sandbox.
"""
import json
import subprocess
import time
import http.server
import socketserver

PORT = 7337
OPENCLAW = "/opt/homebrew/bin/openclaw"
AGENT = "calvin"  # persona is Spermy
SESSION_ID = "webchat-" + str(int(time.time()))  # fresh session => latest persona

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spermy — The Male Fertility Health Competition</title>
<style>
  :root{
    --ink:#1d1d1f; --muted:#6e6e73; --line:#d2d2d7;
    --bg:#fbfbfd; --bg2:#f5f5f7; --card:#ffffff;
    --blue:#0071e3; --blue-h:#0077ed;
    --nav:rgba(251,251,253,.72);
    --shadow:0 8px 40px rgba(0,0,0,.10);
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;line-height:1.47;}
  a{color:var(--blue);text-decoration:none}
  a:hover{text-decoration:underline}

  /* glass nav */
  nav{position:sticky;top:0;z-index:50;height:48px;display:flex;align-items:center;
    justify-content:center;gap:34px;background:var(--nav);
    -webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);
    border-bottom:1px solid rgba(0,0,0,.08);font-size:14px;}
  nav .brand{font-weight:600;letter-spacing:-.01em}
  nav a{color:#1d1d1fcc;font-weight:400}
  nav a:hover{color:#1d1d1f;text-decoration:none}
  nav .pill{background:var(--blue);color:#fff;padding:5px 13px;border-radius:980px;font-size:13px}
  nav .pill:hover{background:var(--blue-h);color:#fff}

  section{padding:0 22px}
  .wrap{max-width:980px;margin:0 auto}

  /* hero */
  .hero{text-align:center;padding:84px 22px 30px}
  .eyebrow{color:var(--blue);font-size:21px;font-weight:600;letter-spacing:-.01em;margin:0 0 6px}
  .hero h1{font-size:clamp(40px,7vw,80px);line-height:1.05;letter-spacing:-.025em;
    font-weight:700;margin:0 0 18px}
  .hero p.sub{font-size:clamp(19px,2.4vw,26px);color:var(--muted);max-width:640px;
    margin:0 auto 22px;letter-spacing:-.01em}
  .ctas{display:flex;gap:26px;justify-content:center;flex-wrap:wrap;font-size:19px}
  .ctas a .chev{font-weight:400}
  .btn{background:var(--blue);color:#fff;padding:11px 22px;border-radius:980px}
  .btn:hover{background:var(--blue-h);color:#fff;text-decoration:none}

  /* centered chat — the focal point */
  .stage{padding:30px 22px 70px;display:flex;justify-content:center}
  .chat{width:100%;max-width:560px;background:var(--card);border-radius:28px;
    box-shadow:var(--shadow);overflow:hidden;border:1px solid rgba(0,0,0,.06)}
  .chat .head{padding:20px 24px;border-bottom:1px solid var(--line);
    display:flex;align-items:center;gap:13px;background:#fff}
  .chat .avatar{width:44px;height:44px;border-radius:50%;flex:0 0 44px;
    background:linear-gradient(135deg,#0071e3,#34c0eb);display:flex;align-items:center;
    justify-content:center;color:#fff;font-weight:700;font-size:19px}
  .chat .head h3{margin:0;font-size:17px;letter-spacing:-.01em}
  .chat .head span{font-size:13px;color:var(--muted)}
  .dot{width:8px;height:8px;border-radius:50%;background:#34c759;display:inline-block;margin-right:5px;vertical-align:middle}
  #log{height:430px;overflow-y:auto;padding:22px;display:flex;flex-direction:column;gap:11px;background:var(--bg2)}
  .row{display:flex}
  .row.me{justify-content:flex-end}
  .bubble{max-width:80%;padding:10px 15px;border-radius:20px;font-size:15.5px;line-height:1.4;
    white-space:pre-wrap;word-wrap:break-word;letter-spacing:-.01em}
  .me .bubble{background:var(--blue);color:#fff;border-bottom-right-radius:6px}
  .bot .bubble{background:#fff;color:var(--ink);border:1px solid var(--line);border-bottom-left-radius:6px}
  .bot .bubble a{color:var(--blue)}
  .typing{color:var(--muted);font-style:italic}
  form{display:flex;gap:10px;padding:14px;background:#fff;border-top:1px solid var(--line)}
  #msg{flex:1;padding:11px 16px;border-radius:980px;border:1px solid var(--line);
    background:var(--bg2);color:var(--ink);font-size:15.5px;font-family:inherit}
  #msg:focus{outline:none;border-color:var(--blue);background:#fff;box-shadow:0 0 0 3px rgba(0,113,227,.18)}
  #send{flex:0 0 auto;border:0;border-radius:50%;width:40px;height:40px;background:var(--blue);
    color:#fff;cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center}
  #send:hover{background:var(--blue-h)}
  #send:disabled{opacity:.4;cursor:default}

  /* features */
  .features{background:var(--bg2);padding:72px 22px}
  .grid{max-width:980px;margin:0 auto;display:grid;grid-template-columns:repeat(3,1fr);gap:26px}
  .feature{text-align:center}
  .feature h4{font-size:21px;letter-spacing:-.01em;margin:0 0 8px}
  .feature p{color:var(--muted);font-size:16px;margin:0}
  .feature .ic{width:46px;height:46px;margin:0 auto 14px;color:var(--blue)}

  /* stats */
  .stats{text-align:center;padding:74px 22px}
  .stats h2{font-size:clamp(30px,4.5vw,48px);letter-spacing:-.02em;font-weight:700;margin:0 0 40px}
  .statrow{display:flex;justify-content:center;gap:64px;flex-wrap:wrap}
  .stat .n{font-size:clamp(34px,5vw,56px);font-weight:700;letter-spacing:-.02em;color:var(--blue)}
  .stat .l{color:var(--muted);font-size:16px}

  footer{background:var(--bg2);border-top:1px solid var(--line);color:var(--muted);
    font-size:12px;padding:26px 22px}
  footer .wrap{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}

  @media (max-width:720px){ .grid{grid-template-columns:1fr} nav{gap:18px} nav .hide{display:none} }
  @media (prefers-reduced-motion:reduce){ html{scroll-behavior:auto} *{transition:none!important} }
</style></head>
<body>
  <nav aria-label="Primary">
    <span class="brand">🏆 Spermy</span>
    <a class="hide" href="#chat">The Host</a>
    <a class="hide" href="#how">How it Works</a>
    <a class="hide" href="#stats">Champions</a>
    <a class="pill" href="#chat">Join</a>
  </nav>

  <header class="hero">
    <p class="eyebrow">The Competition</p>
    <h1>Compete.<br>Improve. Win.</h1>
    <p class="sub">The male fertility health competition. Track your moves, climb the leaderboard, and get crowned champion.</p>
    <div class="ctas">
      <a class="btn" href="#chat">Join the competition</a>
      <a href="#how">Learn more <span class="chev">&rsaquo;</span></a>
    </div>
  </header>

  <!-- CENTER: chat with Spermy -->
  <div class="stage" id="chat">
    <div class="chat">
      <div class="head">
        <div class="avatar" aria-hidden="true">S</div>
        <div><h3>Spermy</h3><span><span class="dot"></span>Host · online</span></div>
      </div>
      <div id="log" aria-live="polite"></div>
      <form id="f" autocomplete="off">
        <label for="msg" class="sr" style="position:absolute;left:-9999px">Message Spermy</label>
        <input id="msg" placeholder="Text Spermy…" autofocus>
        <button id="send" type="submit" aria-label="Send message">&uarr;</button>
      </form>
    </div>
  </div>

  <section class="features" id="how">
    <div class="grid">
      <div class="feature">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/><circle cx="12" cy="12" r="4"/></svg>
        <h4>Score your habits</h4>
        <p>Sleep, training, nutrition, and check-ins all earn you points on the board.</p>
      </div>
      <div class="feature">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></svg>
        <h4>Climb the leaderboard</h4>
        <p>Stack streaks, pass the competition, and watch your rank rise week over week.</p>
      </div>
      <div class="feature">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9a6 6 0 0 0 12 0V3H6zM4 5h2M18 5h2M9 21h6M12 15v6"/></svg>
        <h4>Get crowned champion</h4>
        <p>Spermy hypes every win, keeps score, and crowns the guys who go the distance.</p>
      </div>
    </div>
  </section>

  <section class="stats" id="stats">
    <h2>Guys are already winning.</h2>
    <div class="statrow">
      <div class="stat"><div class="n">1,200+</div><div class="l">Challengers</div></div>
      <div class="stat"><div class="n">38k</div><div class="l">Healthy moves logged</div></div>
      <div class="stat"><div class="n">92%</div><div class="l">Came back next round</div></div>
    </div>
  </section>

  <footer><div class="wrap">
    <span>Spermy is a demo. Not medical advice. Talk to your doctor about real health concerns.</span>
    <span>Local sandbox · localhost</span>
  </div></footer>

<script>
const log=document.getElementById('log'), f=document.getElementById('f'),
      msg=document.getElementById('msg'), send=document.getElementById('send');
function esc(s){return s.replace(/[<>]/g,c=>({"<":"&lt;",">":"&gt;"}[c]));}
function linkify(t){return esc(t).replace(/(https?:\/\/[^\s]+)/g,'<a href="$1" target="_blank" rel="noopener">$1</a>');}
function add(text, who){
  const row=document.createElement('div'); row.className='row '+who;
  const b=document.createElement('div'); b.className='bubble';
  if(who==='bot') b.innerHTML=linkify(text); else b.textContent=text;
  row.appendChild(b); log.appendChild(row); log.scrollTop=log.scrollHeight; return b;
}
add("Yo champ 🏆 it's Spermy. Text me to test things out. Ask how it works or say you're ready to join.","bot");
f.addEventListener('submit', async e=>{
  e.preventDefault(); const text=msg.value.trim(); if(!text) return;
  add(text,'me'); msg.value=''; send.disabled=true;
  const t=add("Spermy is typing…",'bot'); t.classList.add('typing');
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    const d=await r.json();
    t.classList.remove('typing'); t.innerHTML=linkify(d.reply||d.error||'(no reply)');
  }catch(err){ t.classList.remove('typing'); t.textContent='⚠️ '+err; }
  log.scrollTop=log.scrollHeight; send.disabled=false; msg.focus();
});
</script>
</body></html>"""


def ask_spermy(message: str) -> str:
    try:
        out = subprocess.run(
            [OPENCLAW, "agent", "--agent", AGENT, "--session-id", SESSION_ID,
             "-m", message, "--json"],
            capture_output=True, text=True, timeout=120,
        )
        raw = out.stdout.strip() or out.stderr.strip()
        data = json.loads(raw)
        payloads = data.get("result", {}).get("payloads", [])
        texts = [p.get("text", "") for p in payloads if p.get("text")]
        return "\n".join(texts).strip() or "(Spermy gave an empty reply)"
    except subprocess.TimeoutExpired:
        return "Spermy took too long to respond (timeout)."
    except Exception as e:  # noqa: BLE001
        return f"Error talking to Spermy: {e}"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/chat":
            self.send_error(404); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            msg = json.loads(self.rfile.read(n) or b"{}").get("message", "")
        except Exception:
            msg = ""
        reply = ask_spermy(msg) if msg else "(say something!)"
        body = json.dumps({"reply": reply}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Spermy site on http://localhost:{PORT}  (session {SESSION_ID})")
        httpd.serve_forever()
