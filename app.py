"""
3minds — Streamlit App
Think. Question. Validate.
Multi-agent deliberation: Solver -> Critic -> Validator
"""

import json, time, re, subprocess, shutil
import streamlit as st

st.set_page_config(page_title="3minds", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html,body,[data-testid="stApp"]{
  background: radial-gradient(ellipse at 50% -10%, #1a2a5e 0%, #0a0f28 35%, #070b18 70%, #050810 100%) !important;
  font-family:'Inter',sans-serif!important;
}
#MainMenu,footer{visibility:hidden;}
[data-testid="stToolbar"]{display:none;}
[data-testid="stSidebar"]{background:#0d1528!important;border-right:1px solid #1a2a4a!important;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:#111827!important;border:1px solid #1a2a4a!important;color:#e8e8f0!important;border-radius:8px!important;}
[data-testid="stButton"]>button{background:linear-gradient(135deg,#4f72f5,#82a8ff)!important;border:none!important;color:white!important;font-weight:700!important;border-radius:10px!important;width:100%;}
.hero-wrap{text-align:center;padding:60px 20px 40px;}
.hero-logo{font-size:clamp(3.5rem,10vw,6.5rem);font-weight:900;letter-spacing:-.03em;color:#ffffff;display:inline-block;line-height:1.05;margin-bottom:8px;}
.hero-tag{font-size:clamp(2rem,5vw,3.8rem);color:#e8e8f0;margin-top:4px;letter-spacing:-.02em;font-weight:900;line-height:1.1;}
.hero-validate{font-size:clamp(2rem,5vw,3.8rem);font-weight:900;letter-spacing:-.02em;line-height:1.1;background:linear-gradient(135deg,#5b7fff,#7dd4f8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;display:inline-block;}
.validate-word{background:linear-gradient(135deg,#5b7fff,#7dd4f8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.pipe-row{display:flex;gap:10px;align-items:center;margin-bottom:18px;}
.pipe-step{flex:1;background:#0d1528;border:1px solid #1a2a4a;border-radius:12px;padding:14px 10px;text-align:center;transition:all .3s;}
.pipe-step.thinking{border-color:#4f72f5;box-shadow:0 0 18px rgba(79,114,245,.35);}
.pipe-step.done-solver{border-color:#4f72f5;}
.pipe-step.done-critic{border-color:#f59e0b;}
.pipe-step.done-validator{border-color:#10b981;}
.pipe-step.error{border-color:#ef4444;}
.pipe-icon{font-size:1.5rem;}
.pipe-label{font-weight:700;font-size:.9rem;color:#e8e8f0;margin-top:4px;}
.pipe-status{font-size:.75rem;color:#8899bb;margin-top:2px;}
.pipe-arrow{color:#1e3050;font-size:1.3rem;flex:0;}
.log-box{background:#060c18;border:1px solid #1a2a4a;border-radius:10px;padding:12px 16px;font-family:monospace;font-size:.8rem;max-height:200px;overflow-y:auto;line-height:1.6;}
.log-info{color:#8899bb;}.log-ok{color:#10b981;}.log-warn{color:#f59e0b;}.log-err{color:#ef4444;}
.agent-card{background:#0b1220;border:1px solid #1a2a4a;border-radius:12px;padding:18px 20px;margin-bottom:12px;}
.agent-header{display:flex;align-items:center;gap:10px;margin-bottom:12px;font-weight:700;font-size:.95rem;}
.badge{padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:700;}
.badge-solver{background:rgba(79,114,245,.15);color:#4f72f5;}
.badge-critic{background:rgba(245,158,11,.15);color:#f59e0b;}
.badge-validator{background:rgba(16,185,129,.15);color:#10b981;}
.field-label{font-size:.7rem;color:#8899bb;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;}
.field-value{color:#e8e8f0;font-size:.9rem;line-height:1.6;margin-bottom:12px;}
.tag{display:inline-block;padding:2px 8px;margin:2px;border-radius:20px;font-size:.75rem;background:#1a2640;color:#c8d8f0;}
.final-card{background:linear-gradient(135deg,rgba(79,114,245,.08),rgba(130,168,255,.08));border:1px solid #4f72f5;border-radius:16px;padding:28px;margin-top:16px;}
.final-title{font-size:.9rem;font-weight:700;color:#4f72f5;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;}
.final-text{font-size:1.05rem;color:#e8e8f0;line-height:1.8;}
.score-pill{display:inline-block;padding:3px 12px;border-radius:20px;font-weight:700;font-size:.82rem;background:rgba(16,185,129,.15);color:#10b981;margin-left:8px;}
.verdict-approved{color:#10b981;font-weight:700;}
.verdict-needs_revision{color:#f59e0b;font-weight:700;}
.verdict-rejected{color:#ef4444;font-weight:700;}
.local-badge{display:inline-block;padding:1px 7px;border-radius:10px;font-size:.65rem;font-weight:700;background:rgba(245,158,11,.15);color:#f59e0b;margin-left:4px;vertical-align:middle;}

/* ── Mobile responsive ─────────────────────────────────────── */
@media (max-width: 768px) {
  .hero-logo { font-size: 2.8rem !important; }
  .hero-tag  { font-size: 1.6rem !important; }
  .hero-validate { font-size: 1.6rem !important; }
  .hero-wrap { padding: 32px 12px 20px !important; }

  /* Stack expander columns */
  [data-testid="column"] {
    width: 100% !important;
    flex: 1 1 100% !important;
    min-width: 100% !important;
  }

  /* Full width inputs */
  [data-testid="stTextInput"],
  [data-testid="stTextArea"],
  [data-testid="stSelectbox"] {
    width: 100% !important;
  }
  [data-testid="stTextInput"] input,
  [data-testid="stTextArea"] textarea {
    width: 100% !important;
    font-size: 16px !important; /* prevent iOS zoom on focus */
    box-sizing: border-box !important;
  }

  /* Pipeline steps wrap on mobile */
  .pipe-row {
    flex-wrap: wrap !important;
    gap: 8px !important;
  }
  .pipe-step { min-width: 80px !important; }
  .pipe-arrow { display: none !important; }

  /* Agent cards */
  .agent-card, .final-card { padding: 14px !important; }

  /* Main container padding */
  .main .block-container {
    padding: 1rem !important;
  }
}
</style>
""", unsafe_allow_html=True)

# ── Model list ────────────────────────────────────────────────────────────────
ALL_MODELS = [
    ("gemini-2.5-flash (free)",      "gemini-2.5-flash"),
    ("gemini-2.5-flash-lite (free)", "gemini-2.5-flash-lite-preview-06-17"),
    ("gemini-2.5-pro",               "gemini-2.5-pro-preview-06-05"),
    ("gpt-4o (OpenAI)",              "gpt-4o"),
    ("gpt-4o-mini (OpenAI)",         "gpt-4o-mini"),
    ("o3-mini (OpenAI)",             "o3-mini"),
    ("Claude CLI ⚡ local only",     "claude-cli"),
    ("Codex CLI ⚡ local only",      "codex-cli"),
    ("Ollama (local)",               "ollama"),
]
LABELS = [m[0] for m in ALL_MODELS]
VALUES = [m[1] for m in ALL_MODELS]

# ── Session state ─────────────────────────────────────────────────────────────
for k,v in [("log",[]),("history",[]),("running",False),("done",False),
            ("pipe_state",{"solver":"waiting","critic":"waiting","validator":"waiting"}),
            ("rpm_ts",[])]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
claude_avail = shutil.which("claude") is not None
codex_avail  = shutil.which("codex")  is not None

with st.expander("⚙️  Settings", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div style='font-size:.75rem;color:#8899bb;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px'>API Keys</div>", unsafe_allow_html=True)
        gemini_key   = st.text_input("Gemini API Key",  type="password", placeholder="AIza…", help="aistudio.google.com — free tier")
        openai_key   = st.text_input("OpenAI API Key",  type="password", placeholder="sk-…")
        st.markdown("<div style='font-size:.75rem;color:#8899bb;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin:10px 0 6px'>Local Providers</div>", unsafe_allow_html=True)
        ollama_url   = st.text_input("Ollama URL",   value="http://localhost:11434")
        ollama_model = st.text_input("Ollama model", value="llama3.2")
        st.markdown(f"""<div style='font-size:.75rem;color:#8899bb;background:#0b1220;border:1px solid #1a2a4a;border-radius:8px;padding:8px 12px;margin-top:8px;line-height:1.9;'>
          {"✅" if claude_avail else "❌"} Claude CLI &nbsp;{"ready" if claude_avail else "not installed"}<br>
          {"✅" if codex_avail  else "❌"} Codex CLI &nbsp;{"ready" if codex_avail  else "not installed"}<br>
          <span style='color:#f59e0b;'>⚡ CLI options only work locally</span>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("<div style='font-size:.75rem;color:#8899bb;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px'>Model per role</div>", unsafe_allow_html=True)
        # Default: Claude CLI > Codex CLI > Gemini
        if claude_avail:
            _default = LABELS.index("Claude CLI ⚡ local only")
        elif codex_avail:
            _default = LABELS.index("Codex CLI ⚡ local only")
        else:
            _default = 0  # gemini-2.5-flash (free)
        sm = VALUES[LABELS.index(st.selectbox("🧠 Solver",    LABELS, index=_default))]
        cm = VALUES[LABELS.index(st.selectbox("🔍 Critic",    LABELS, index=_default))]
        vm = VALUES[LABELS.index(st.selectbox("✅ Validator", LABELS, index=_default))]
        cycles = st.select_slider("Cycles", [1,2,3], value=2)
        st.markdown("<div style='color:#8899bb;font-size:.73rem;margin-top:8px;'><a href='https://github.com/mayankaggarwaal/3minds' style='color:#4f72f5;'>GitHub</a> · <code style='color:#4f72f5;'>streamlit run app.py</code></div>", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-wrap">
  <div class="hero-logo">3minds…</div>
  <div class="hero-tag">Think Question <span class="validate-word">Validate</span></div>
</div>
""", unsafe_allow_html=True)

# ── Input ─────────────────────────────────────────────────────────────────────
problem = st.text_area(
    "What do you want the three minds to deliberate on?",
    value="I built 3minds — 3 AI agents that challenge each other to find the best answer. I genuinely want to know: how much of a difference does this actually make for real people?",
    height=90
)
c1,_ = st.columns([1,3])
with c1:
    run_btn = st.button("▶  Run Deliberation", disabled=st.session_state.running)

# ── Pipeline ──────────────────────────────────────────────────────────────────
pipe_ph = st.empty()

def render_pipeline(states):
    def step(icon, label, state):
        status = {"waiting":"Waiting","thinking":"Thinking…","done-solver":"Done ✓","done-critic":"Done ✓","done-validator":"Done ✓","error":"Error ✗"}.get(state,"Waiting")
        return f'<div class="pipe-step {state}"><div class="pipe-icon">{icon}</div><div class="pipe-label">{label}</div><div class="pipe-status">{status}</div></div>'
    pipe_ph.markdown(
        f'<div class="pipe-row">{step("🧠","Solver",states["solver"])}<div class="pipe-arrow">→</div>{step("🔍","Critic",states["critic"])}<div class="pipe-arrow">→</div>{step("✅","Validator",states["validator"])}</div>',
        unsafe_allow_html=True)

render_pipeline(st.session_state.pipe_state)

log_ph = st.empty()

def render_log():
    if not st.session_state.log: return
    html = "".join(f'<div class="log-{t}">[{ts}] {m}</div>' for ts,m,t in st.session_state.log[-40:])
    log_ph.markdown(f'<div class="log-box">{html}</div>', unsafe_allow_html=True)

def log(msg, t="info"):
    st.session_state.log.append((time.strftime("%H:%M:%S"), msg, t))
    render_log()

# ── Rate limiter ──────────────────────────────────────────────────────────────
def rpm_acquire():
    now = time.time()
    st.session_state.rpm_ts = [x for x in st.session_state.rpm_ts if x > now-60]
    if len(st.session_state.rpm_ts) >= 14:
        wait = int(st.session_state.rpm_ts[0] + 61 - time.time())
        if wait > 0:
            log(f"🚦 RPM cap — waiting {wait}s for a free slot…", "warn")
            time.sleep(wait)
    st.session_state.rpm_ts.append(time.time())
    log(f"📊 RPM {len(st.session_state.rpm_ts)}/14 — dispatched", "info")

# ── CLI helpers ───────────────────────────────────────────────────────────────
def _parse_cli_output(stdout, cli_name):
    """Extract text response from claude/codex JSON-lines output."""
    messages = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line: continue
        try:
            ev = json.loads(line)
            ev_type = ev.get("type","")
            # Claude stream-json format
            if ev_type == "result":
                text = ev.get("result","")
                if text: return text
            if ev_type == "assistant":
                for block in ev.get("message",{}).get("content",[]):
                    if block.get("type") == "text":
                        messages.append(block.get("text",""))
            # Codex JSON-lines format
            if ev_type == "item.completed":
                item = ev.get("item",{})
                if item.get("type") == "agent_message":
                    text = item.get("text","") or "".join(b.get("text","") for b in item.get("content",[]) if b.get("text"))
                    if text: messages.append(text)
        except json.JSONDecodeError:
            messages.append(line)

    return messages[-1] if messages else ""

def call_claude_cli(prompt):
    exe = shutil.which("claude")
    if not exe:
        raise FileNotFoundError("Claude CLI not found. Install it: npm install -g @anthropic-ai/claude-code")
    log("⚡ Calling Claude CLI…", "info")
    result = subprocess.run(
        [exe, "-p", "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"],
        input=prompt, capture_output=True, text=True, timeout=180
    )
    text = _parse_cli_output(result.stdout, "claude")
    if not text:
        raise RuntimeError(f"Claude CLI returned no output. stderr: {result.stderr[:200]}")
    return text

def call_codex_cli(prompt):
    exe = shutil.which("codex")
    if not exe:
        raise FileNotFoundError("Codex CLI not found. Install it: npm install -g @openai/codex")
    log("⚡ Calling Codex CLI…", "info")
    result = subprocess.run(
        [exe, "exec", "--skip-git-repo-check", "--json",
         "--dangerously-bypass-approvals-and-sandbox", "-c", "mcp_servers={}", "-"],
        input=prompt, capture_output=True, text=True, timeout=180
    )
    text = _parse_cli_output(result.stdout, "codex")
    if not text:
        raise RuntimeError(f"Codex CLI returned no output. stderr: {result.stderr[:200]}")
    return text

# ── API calls ─────────────────────────────────────────────────────────────────
def call_gemini(prompt, model_id, retry=0):
    import google.generativeai as genai
    if not gemini_key:
        raise ValueError("Gemini API key missing — add it in the sidebar")
    rpm_acquire()
    genai.configure(api_key=gemini_key)
    m = genai.GenerativeModel(model_id, generation_config=genai.GenerationConfig(
        temperature=0.7, max_output_tokens=4096, response_mime_type="application/json"))
    try:
        return m.generate_content(prompt).text
    except Exception as e:
        msg = str(e)
        if re.search(r"per.?day|daily.?quota|resource.*exhausted", msg, re.I):
            raise ValueError("Daily Gemini quota exhausted — resets at midnight Pacific. Switch to Ollama or Claude CLI locally.")
        if "429" in msg or "quota" in msg.lower():
            if retry >= 4: raise
            found = re.search(r"retry[^0-9]*(after|in)\s*([\d.]+)\s*s", msg, re.I)
            wait = int(float(found.group(2)))+8 if found else min(120,15*(2**retry))
            log(f"⏳ Rate limited — waiting {wait}s (attempt {retry+1}/4)…", "warn")
            time.sleep(wait)
            return call_gemini(prompt, model_id, retry+1)
        raise

def call_openai(prompt, model_id):
    from openai import OpenAI
    if not openai_key:
        raise ValueError("OpenAI API key missing — add it in the sidebar")
    client = OpenAI(api_key=openai_key)
    is_o = bool(re.match(r"^o\d", model_id))
    kwargs = dict(model=model_id, messages=[{"role":"user","content":prompt}], max_completion_tokens=4096)
    if not is_o:
        kwargs["temperature"]=0.7; kwargs["response_format"]={"type":"json_object"}
    return client.chat.completions.create(**kwargs).choices[0].message.content

def call_ollama(prompt):
    import requests as rq
    r = rq.post(ollama_url.rstrip("/")+"/api/chat",
                json={"model":ollama_model,"messages":[{"role":"user","content":prompt}],"stream":False,"format":"json"},
                timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]

def call_model(prompt, model_id):
    if model_id == "ollama":     return call_ollama(prompt)
    if model_id == "claude-cli": return call_claude_cli(prompt)
    if model_id == "codex-cli":  return call_codex_cli(prompt)
    if model_id.startswith("gpt-") or re.match(r"^o\d", model_id):
        return call_openai(prompt, model_id)
    return call_gemini(prompt, model_id)

# ── JSON parser ───────────────────────────────────────────────────────────────
def parse_json(text, role):
    t = re.sub(r"^```json\s*","",text.strip(),flags=re.I)
    t = re.sub(r"^```\s*","",t); t = re.sub(r"\s*```$","",t).strip()
    try: return json.loads(t)
    except: pass
    s,e = t.find("{"),t.rfind("}")
    if s!=-1 and e>s:
        try: return json.loads(t[s:e+1])
        except: pass
    return {"solver":{"role":"solver","cycle":0,"solution":text,"reasoning":"(raw)","changes_from_previous":"N/A","confidence":5},
            "critic":{"role":"critic","cycle":0,"strengths":[],"weaknesses":[text],"missing_cases":[],"improvement_suggestions":[],"overall_critique":text},
            "validator":{"role":"validator","cycle":0,"verdict":"needs_revision","score":5,"criteria_met":[],"criteria_failed":[],"rationale":text,"final_answer":text}
           }.get(role,{"role":"unknown","raw":text})

# ── Prompts ───────────────────────────────────────────────────────────────────
SOLVER_SYS = """You are the Solver agent in a three-minds deliberation system. You are known for producing intellectually rich, research-backed answers that surprise people with depth.
RULES:
- Anchor every major claim to a real-world example — name it specifically (e.g. "Warren Buffett did X", "Studies like Kahneman's System 1/2 show…", "SpaceX solved this by…").
- Use at least 2 vivid, concrete examples — one well-known, one surprising or counter-intuitive.
- After each example, explain WHY it proves your point (don't just list).
- Go one level deeper than the obvious answer — what do most people miss?
- On later cycles, substantially revise based on Critic feedback and show examples they hadn't considered.
Respond ONLY with JSON: {"role":"solver","cycle":<int>,"solution":"<rich solution with inline examples>","reasoning":"<reasoning with named examples>","changes_from_previous":"<changes or N/A>","confidence":<0-10>}"""

CRITIC_SYS = """You are the Critic agent in a three-minds deliberation system. You are a rigorous, intellectually fearless contrarian who finds what everyone else misses.
RULES:
- For every weakness you raise, cite a real counter-example or failure case (e.g. "Kodak ignored this exact advice and…", "This failed for Blockbuster because…").
- Find at least one angle the Solver completely missed — illustrate it with a surprising real-world case.
- Use analogies from different fields when they sharpen the critique (e.g. "This is like a bridge engineer who only tested for weight but not wind — the Tacoma Narrows Bridge collapsed that way").
- Don't list vague concerns — make each weakness concrete and story-driven.
- Comfort is a red flag: if the Solver's answer sounds too clean, dig harder.
Respond ONLY with JSON: {"role":"critic","cycle":<int>,"strengths":["..."],"weaknesses":["..."],"missing_cases":["..."],"improvement_suggestions":["..."],"overall_critique":"..."}"""

VALIDATOR_SYS = """You are the Validator agent in a three-minds deliberation system. You are the final arbiter — rigorous, fair, focused on real-world usefulness.
RULES:
- Score honestly. If examples were weak or generic, penalise the score.
- In your rationale, reference 1-2 of the best examples from the debate and explain whether they held up to scrutiny.
- Write final_answer as a punchy, memorable insight — the kind of thing someone would screenshot and share. Ground it in at least one vivid real-world example so it lands, not just floats.
- If you approve, your final_answer should feel like the distilled wisdom of the whole debate.
- Verdict: approved / needs_revision / rejected.
Respond ONLY with JSON: {"role":"validator","cycle":<int>,"verdict":"approved|needs_revision|rejected","score":<0-10>,"criteria_met":["..."],"criteria_failed":["..."],"rationale":"...","final_answer":"..."}"""

def build_solver(problem, cycle, history):
    p = SOLVER_SYS + f"\n\n## Problem\n\n{problem}"
    if history:
        p += "\n\n## Previous feedback\n" + "".join(
            f"\nCycle {h['cycle']} Critic: {json.dumps(h['critic'])}\nCycle {h['cycle']} Validator: {json.dumps(h['validator'])}"
            for h in history)
    return p + f"\n\nProduce cycle {cycle} {'initial' if cycle==1 else 'revised'} solution."

def build_critic(problem, cycle, solver):
    return CRITIC_SYS + f"\n\n## Problem\n\n{problem}\n\n## Solver (cycle {cycle})\n\n{json.dumps(solver)}\n\nCritique now."

def build_validator(problem, cycle, solver, critic):
    return VALIDATOR_SYS + f"\n\n## Problem\n\n{problem}\n\n## Solver (cycle {cycle})\n{json.dumps(solver)}\n\n## Critic (cycle {cycle})\n{json.dumps(critic)}\n\nValidate now."

# ── Results ───────────────────────────────────────────────────────────────────
res_ph = st.empty()

def render_results(history):
    if not history: return
    last = history[-1]
    def tags(items): return "".join(f'<span class="tag">{x}</span>' for x in (items or []))
    s,c,v = last["solver"],last["critic"],last["validator"]
    verdict = v.get("verdict","?"); score = v.get("score","?")
    cycle_tabs = "".join(
        f'<span style="padding:5px 14px;border-radius:20px;font-size:.78rem;font-weight:700;background:{("#4f72f5" if i==len(history)-1 else "#1a2640")};color:{("white" if i==len(history)-1 else "#8899bb")};margin-right:6px;">Cycle {h["cycle"]}</span>'
        for i,h in enumerate(history))
    html = f'<div style="margin-bottom:14px">{cycle_tabs}</div>'
    html += f'''
    <div class="agent-card">
      <div class="agent-header"><span class="badge badge-solver">SOLVER</span> Confidence: {s.get("confidence","?")}/10</div>
      <div class="field-label">Solution</div><div class="field-value">{s.get("solution","")}</div>
      <div class="field-label">Reasoning</div><div class="field-value" style="color:#8899bb;font-size:.85rem">{s.get("reasoning","")}</div>
    </div>
    <div class="agent-card">
      <div class="agent-header"><span class="badge badge-critic">CRITIC</span></div>
      <div class="field-label">Strengths</div><div class="field-value">{tags(c.get("strengths",[]))}</div>
      <div class="field-label">Weaknesses</div><div class="field-value">{tags(c.get("weaknesses",[]))}</div>
      <div class="field-label">Missing cases</div><div class="field-value">{tags(c.get("missing_cases",[]))}</div>
      <div class="field-label">Overall</div><div class="field-value" style="color:#f59e0b">{c.get("overall_critique","")}</div>
    </div>
    <div class="agent-card">
      <div class="agent-header"><span class="badge badge-validator">VALIDATOR</span>
        <span class="verdict-{verdict}">{verdict.upper()}</span>
        <span class="score-pill">{score}/10</span>
      </div>
      <div class="field-label">Criteria met</div><div class="field-value">{tags(v.get("criteria_met",[]))}</div>
      <div class="field-label">Criteria failed</div><div class="field-value">{tags(v.get("criteria_failed",[]))}</div>
      <div class="field-label">Rationale</div><div class="field-value" style="color:#8899bb;font-size:.85rem">{v.get("rationale","")}</div>
    </div>'''
    if v.get("final_answer"):
        html += f'<div class="final-card"><div class="final-title">⭐ Final Answer</div><div class="final-text">{v["final_answer"]}</div></div>'
    res_ph.markdown(html, unsafe_allow_html=True)

# ── Run ───────────────────────────────────────────────────────────────────────
if run_btn:
    if not problem.strip():
        st.warning("Enter a problem first.")
    else:
        st.session_state.update(running=True, log=[], history=[], done=False,
                                pipe_state={"solver":"waiting","critic":"waiting","validator":"waiting"})
        res_ph.empty()
        try:
            for cycle in range(1, cycles+1):
                log(f"── Cycle {cycle}/{cycles} ──")
                ps = st.session_state.pipe_state

                ps["solver"]="thinking"; render_pipeline(ps)
                log("🧠 Solver thinking…")
                solver = parse_json(call_model(build_solver(problem, cycle, st.session_state.history), sm), "solver")
                solver["cycle"] = cycle
                ps["solver"]="done-solver"; render_pipeline(ps)
                log(f"Solver confidence: {solver.get('confidence','?')}/10", "ok")

                ps["critic"]="thinking"; render_pipeline(ps)
                log("🔍 Critic reviewing…")
                critic = parse_json(call_model(build_critic(problem, cycle, solver), cm), "critic")
                critic["cycle"] = cycle
                ps["critic"]="done-critic"; render_pipeline(ps)
                log(f"Critic found {len(critic.get('weaknesses',[]))} weaknesses", "warn")

                ps["validator"]="thinking"; render_pipeline(ps)
                log("✅ Validator deciding…")
                validator = parse_json(call_model(build_validator(problem, cycle, solver, critic), vm), "validator")
                validator["cycle"] = cycle
                ps["validator"]="done-validator"; render_pipeline(ps)
                verdict = validator.get("verdict","?")
                log(f"Verdict: {verdict.upper()}  Score: {validator.get('score','?')}/10",
                    "ok" if verdict=="approved" else "warn")

                st.session_state.history.append({"cycle":cycle,"solver":solver,"critic":critic,"validator":validator})
                render_results(st.session_state.history)

                if verdict == "approved":
                    log(f"✅ Approved on cycle {cycle}. Done!", "ok"); break
                if cycle < cycles:
                    log("⏸ Brief pause before next cycle…"); time.sleep(3)

            log("🎉 Deliberation complete!", "ok")
            st.session_state.done = True
        except Exception as e:
            log(f"Error: {e}", "err"); st.error(str(e))
        finally:
            st.session_state.running = False

if st.session_state.history and not st.session_state.running:
    render_results(st.session_state.history)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:56px;padding:36px 0 20px;border-top:1px solid #1a2a4a;text-align:center;">

  <div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.12em;color:#556688;font-weight:600;margin-bottom:12px;">Run Locally</div>

  <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:20px;">
    <a href="https://github.com/mayankaggarwaal/3minds#run-locally" target="_blank"
       style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:8px;background:#0d1528;border:1px solid #1e2d52;color:#8899cc;font-size:.76rem;text-decoration:none;">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
      Clone &amp; setup guide
    </a>
    <a href="https://docs.anthropic.com/en/docs/claude-code" target="_blank"
       style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:8px;background:#0d1528;border:1px solid #1e2d52;color:#8899cc;font-size:.76rem;text-decoration:none;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9l6 3-6 3V9z"/></svg>
      Install Claude CLI
    </a>
    <a href="https://github.com/openai/codex" target="_blank"
       style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:8px;background:#0d1528;border:1px solid #1e2d52;color:#8899cc;font-size:.76rem;text-decoration:none;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01"/></svg>
      Install Codex CLI
    </a>
    <a href="https://github.com/mayankaggarwaal/3minds/blob/main/CONTRIBUTING.md" target="_blank"
       style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:8px;background:#0d1528;border:1px solid #1e2d52;color:#8899cc;font-size:.76rem;text-decoration:none;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
      Contribute
    </a>
  </div>

  <div style="width:50px;height:1px;background:#1a2a4a;margin:0 auto 18px;"></div>

  <div style="display:flex;gap:20px;justify-content:center;align-items:center;flex-wrap:wrap;">
    <a href="https://github.com/mayankaggarwaal" target="_blank"
       style="display:inline-flex;align-items:center;gap:7px;color:#556688;font-size:.8rem;text-decoration:none;">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
      mayankaggarwaal
    </a>
    <a href="https://www.linkedin.com/in/mayank-a-2b4664149/" target="_blank"
       style="display:inline-flex;align-items:center;gap:7px;color:#556688;font-size:.8rem;text-decoration:none;">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
      Mayank Aggarwal
    </a>
  </div>

  <div style="margin-top:14px;font-size:.68rem;color:#33445a;">Built with 3 agents · open source · MIT</div>
</div>
""", unsafe_allow_html=True)
