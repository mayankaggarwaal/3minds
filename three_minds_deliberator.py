"""
Three-Minds Deliberator
=======================
Runs a multi-agent deliberation loop over a problem statement.

Cycle structure
---------------
  Round N:
    1. Solver  — proposes / refines a solution
    2. Critic  — identifies weaknesses and improvement areas
    3. Validator — scores the solution and decides whether to continue

The Validator's verdict drives the next cycle:
  * "approved"       -> pipeline stops early (solution accepted)
  * "needs_revision" -> another cycle starts with full context
  * "rejected"       -> pipeline stops (unsolvable given constraints)

Usage
-----
  python three_minds_deliberator.py --problem "Your problem here" --cycles 3
  python three_minds_deliberator.py --test
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── constants ─────────────────────────────────────────────────────────────────

SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "runs"
DEFAULT_CLI_ORDER = ("claude", "codex", "agent")
LLM_EXECUTABLES = tuple(
    name.strip()
    for name in os.environ.get("THREE_MINDS_CLI_ORDER", ",".join(DEFAULT_CLI_ORDER)).split(",")
    if name.strip()
)
MAX_EXECUTION_RETRIES = 3
CLI_TIMEOUT_SECONDS = int(os.environ.get("THREE_MINDS_CLI_TIMEOUT", "240"))
DEFAULT_CYCLES = 2

TEST_PROMPT = "Return a JSON object with a single key 'message' whose value is '3minds ok'."

_MCP_ERROR_PATTERNS = (
    "transport channel closed",
    "connection refused",
    "stream disconnected",
    "invalid_token",
    "authentication failed",
    "auth required",
    "dns error",
    "failed to lookup address information",
    "handshaking with mcp server failed",
    "failed to initialize rollout recorder",
    "agent loop died unexpectedly",
    "internal error",
)

_TRANSIENT_ERROR_PATTERNS = (
    "stream disconnected before completion",
    "stream closed before response.completed",
    "response.completed",
    "retrying 1/5",
    "retrying 2/5",
    "retrying 3/5",
    "retrying 4/5",
    "retrying 5/5",
    "exceeded retry limit",
)

# Patterns that mean a CLI quota is exhausted, so that provider should be skipped.
_USAGE_LIMIT_PATTERNS = (
    "usage limit",
    "monthly usage limit",
    "rate limit exceeded",
    "quota exceeded",
    "you've hit",
    "billing",
    "402",
    "429",
)

# ── HTTP fallback LLM helpers ─────────────────────────────────────────────────

def _ai_provider_config() -> dict:
    """Load API keys — searches several candidate locations."""
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / "automation_dashboard" / "ai_provider_config.json",
        script_dir.parent.parent / "automation_dashboard" / "ai_provider_config.json",
        script_dir / "ai_provider_config.json",
        Path.home() / "ai_provider_config.json",
    ]
    for cfg_path in candidates:
        if cfg_path.exists():
            try:
                with open(cfg_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return {}

def _post_json_http(url: str, payload: dict, headers: dict = None, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {})
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def _http_groq(prompt: str, api_key: str) -> str:
    model = "llama-3.1-8b-instant"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
    }
    resp = _post_json_http("https://api.groq.com/openai/v1/chat/completions", payload, headers)
    return resp["choices"][0]["message"]["content"]

def _http_gemini(prompt: str, api_key: str) -> str:
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    resp = _post_json_http(url, payload)
    return resp["candidates"][0]["content"]["parts"][0]["text"]

def _http_ollama(prompt: str, base_url: str = "http://localhost:11434") -> str:
    # Pick first available model
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
    except Exception:
        raise RuntimeError("Ollama not running")
    if not models:
        raise RuntimeError("Ollama running but no models installed")
    preferred_model = os.environ.get("OLLAMA_MODEL", "").strip()
    model = preferred_model if preferred_model in models else models[0]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    resp = _post_json_http(f"{base_url}/api/chat", payload)
    return resp["message"]["content"]

def http_llm_fallback(prompt: str) -> Optional[str]:
    """
    Try Gemini first (primary HTTP fallback), then Groq, then Ollama.
    Returns the raw text response, or None if all fail.
    """
    cfg = _ai_provider_config()
    providers: List[Tuple[str, Any]] = []

    # ── Gemini — primary HTTP fallback ────────────────────────────────────
    gemini_key = cfg.get("gemini_key", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if gemini_key:
        providers.append(("Gemini", lambda: _http_gemini(prompt, gemini_key)))

    # ── Groq — secondary HTTP fallback ────────────────────────────────────
    groq_key = cfg.get("groq_key", "").strip() or os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        providers.append(("Groq", lambda: _http_groq(prompt, groq_key)))

    # ── Ollama — local last resort ─────────────────────────────────────────
    providers.append((
        "Ollama",
        lambda: _http_ollama(
            prompt,
            os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ),
    ))

    for name, fn in providers:
        try:
            print(f"  [agent] fallback -> {name}", flush=True)
            result = fn()
            if result:
                return result
        except Exception as exc:
            print(f"  [agent] {name} fallback failed: {exc}", flush=True)

    return None

def is_usage_limit(text: str) -> bool:
    """Return True if text indicates a CLI usage/rate limit was hit."""
    lowered = text.lower()
    return any(p in lowered for p in _USAGE_LIMIT_PATTERNS)

# ── agent role prompts ────────────────────────────────────────────────────────

SOLVER_SYSTEM = """\
You are the Solver agent in a three-minds deliberation system.
Your job is to produce the best possible solution to the given problem.

On the first cycle you will only see the raw problem.
On subsequent cycles you will also receive the Critic's feedback and the
Validator's assessment from the previous round — use them to improve your answer.

Always respond with a JSON object in exactly this shape:
{
  "role": "solver",
  "cycle": <integer>,
  "solution": "<your full proposed solution>",
  "reasoning": "<step-by-step reasoning behind the solution>",
  "changes_from_previous": "<what you changed vs last cycle, or 'N/A' on cycle 1>",
  "confidence": <integer 0-10>
}
"""

CRITIC_SYSTEM = """\
You are the Critic agent in a three-minds deliberation system.
Your job is to rigorously challenge the Solver's proposed solution and surface
every weakness, gap, assumption, or edge-case that could cause it to fail.
Be constructive — your goal is to make the solution better, not to reject it.

You will receive the original problem and the Solver's latest response.

Always respond with a JSON object in exactly this shape:
{
  "role": "critic",
  "cycle": <integer>,
  "strengths": ["<strength 1>", ...],
  "weaknesses": ["<weakness 1>", ...],
  "missing_cases": ["<edge case or gap 1>", ...],
  "improvement_suggestions": ["<concrete suggestion 1>", ...],
  "overall_critique": "<concise narrative summary of your critique>"
}
"""

VALIDATOR_SYSTEM = """\
You are the Validator agent in a three-minds deliberation system.
Your job is to independently evaluate the Solver's solution against the original
problem AND the Critic's feedback, and to decide whether the solution is ready.

You will receive:
  - the original problem
  - the Solver's solution
  - the Critic's critique

Reach one of three verdicts:
  * "approved"       — solution fully satisfies the problem requirements
  * "needs_revision" — solution is on the right track but requires further work
  * "rejected"       — solution is fundamentally flawed and cannot be salvaged

Always respond with a JSON object in exactly this shape:
{
  "role": "validator",
  "cycle": <integer>,
  "verdict": "approved" | "needs_revision" | "rejected",
  "score": <integer 0-10>,
  "criteria_met": ["<criterion 1>", ...],
  "criteria_failed": ["<criterion 1>", ...],
  "rationale": "<explanation of your verdict>",
  "final_answer": "<the best answer derived from this cycle, in plain language>"
}
"""

# ── LLM plumbing (mirrors reference script) ──────────────────────────────────

def _find_executable(name: str) -> Optional[str]:
    """Find an executable by name, handling Windows .cmd wrappers."""
    # Direct lookup first
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32":
        found = shutil.which(name + ".exe")
        if found:
            return found
        if name == "codex":
            candidates = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin" / "codex.exe",
                Path.home() / "AppData" / "Local" / "OpenAI" / "Codex" / "bin" / "codex.exe",
            ]
            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)
    # On Windows, npm installs CLIs as <name>.cmd — try that
    if sys.platform == "win32":
        found = shutil.which(name + ".cmd")
        if found:
            return found
        # Also try discovering via npm global bin directory
        try:
            result = subprocess.run(
                ["npm", "config", "get", "prefix"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            )
            if result.returncode == 0:
                npm_prefix = result.stdout.strip()
                candidate = os.path.join(npm_prefix, name + ".cmd")
                if os.path.isfile(candidate):
                    return candidate
                candidate = os.path.join(npm_prefix, "bin", name)
                if os.path.isfile(candidate):
                    return candidate
        except Exception:
            pass
    return None


# Cache resolved paths so we only probe once per session
_EXEC_CACHE: Dict[str, Optional[str]] = {}


def available_executables(cli_order: Tuple[str, ...] = LLM_EXECUTABLES) -> List[str]:
    result = []
    for name in cli_order:
        path = _find_executable(name)
        _EXEC_CACHE[name] = path
        if path:
            result.append(name)
    return result


def build_exec_command(executable: str) -> List[str]:
    """Build the CLI invocation for each supported executable."""
    # Resolve the full path (handles Windows .cmd wrappers)
    exe_path = _EXEC_CACHE.get(executable) or _find_executable(executable) or executable

    if executable == "claude":
        # Claude Code CLI: -p reads prompt from stdin, --output-format stream-json
        # gives us structured JSON-lines output we can parse.
        return [exe_path, "-p", "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"]
    if executable == "codex":
        return [
            exe_path, "exec", "--skip-git-repo-check", "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "-c", "mcp_servers={}",
            "-",
        ]
    # agent / other
    return [exe_path, "exec", "--skip-git-repo-check", "--json", "-"]


def build_llm_env(executable: str) -> Dict[str, str]:
    env = os.environ.copy()
    for prefix in ("CODEX", "AGENT"):
        env[f"{prefix}_IGNORE_MCP_CLIENTS"] = ""
        env[f"{prefix}_DISABLE_CLIENTS"] = ""
        env.setdefault(f"{prefix}_SKIP_CLIENT_START_FAILURES", "1")
        env.setdefault(f"{prefix}_DISABLE_ROLLOUT_RECORDER", "1")
    return env


def should_retry_same_executor(stdout: str, stderr: str) -> bool:
    combined = "\n".join(filter(None, [stdout, stderr])).lower()
    return any(p in combined for p in _TRANSIENT_ERROR_PATTERNS)


def should_retry_next_executor(stdout: str, stderr: str) -> bool:
    combined = "\n".join(filter(None, [stdout, stderr])).lower()
    return any(p in combined for p in _MCP_ERROR_PATTERNS)


def _brief_failure(stdout: str, stderr: str, limit: int = 240) -> str:
    text = (stderr or stdout or "").strip().replace("\r", " ")
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if not text:
        return "no output"
    return text[:limit] + ("..." if len(text) > limit else "")


def parse_agent_payload(text: str) -> Any:
    """Extract the first valid JSON object/array from agent text output."""
    raw = text.strip()

    # Strip markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].startswith("```") else lines
        raw = "\n".join(lines).strip()

    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Scan for first JSON object/array
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(raw[i:])
            return payload
        except json.JSONDecodeError:
            continue

    # Bracket extraction fallback
    for opener, closer in (("{", "}"), ("[", "]")):
        s, e = raw.find(opener), raw.rfind(closer)
        if s != -1 and e > s:
            try:
                return json.loads(raw[s:e + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No parseable JSON found in agent response:\n{text[:300]}")


def run_agent(
    prompt: str,
    cwd: Path,
    cli_order: Tuple[str, ...] = LLM_EXECUTABLES,
) -> Tuple[Any, str, str]:
    """
    Invoke the best available LLM CLI with `prompt`, return (payload, stdout, stderr).
    Mirrors the retry / fallback logic from the reference pipeline script.
    """
    detected_executables = available_executables(cli_order)
    if not detected_executables:
        checked = ", ".join(cli_order) or "(none configured)"
        print(
            f"  [agent] No CLI executable found on PATH. Checked: {checked}. "
            "Trying fallback providers...",
            flush=True,
        )

    last_error: Optional[BaseException] = None
    attempts: List[str] = [
        f"{name}: not found"
        for name in cli_order
        if name not in detected_executables
    ]

    for executable in cli_order:
        for retry in range(1, MAX_EXECUTION_RETRIES + 1):
            print(
                f"  [agent] {executable} attempt {retry}/{MAX_EXECUTION_RETRIES}",
                flush=True,
            )
            try:
                result = subprocess.run(
                    build_exec_command(executable),
                    input=prompt,
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True,
                    cwd=str(cwd),
                    env=build_llm_env(executable),
                    timeout=CLI_TIMEOUT_SECONDS,
                )
            except FileNotFoundError as exc:
                attempts.append(f"{executable}: not found")
                last_error = exc
                break
            except subprocess.TimeoutExpired as exc:
                attempts.append(f"{executable}#{retry}: timed out after {CLI_TIMEOUT_SECONDS}s")
                last_error = exc
                print(
                    f"  [agent] {executable} timed out; trying the next provider",
                    flush=True,
                )
                break

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()

            # If a CLI is out of quota, skip that provider and try the next one.
            if is_usage_limit(stdout) or is_usage_limit(stderr):
                attempts.append(f"{executable}#{retry}: usage limit hit")
                print(f"  [agent] {executable} usage limit detected; trying the next provider", flush=True)
                last_error = RuntimeError(f"{executable} usage limit hit")
                break

            # Extract the final text response from JSON-lines stdout.
            # claude --output-format stream-json  -> events with type="assistant" / "result"
            # codex/agent --json                  -> events with type="item.completed"
            agent_messages: List[str] = []
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    # Plain-text line (claude fallback without stream-json)
                    agent_messages.append(line)
                    continue

                ev_type = event.get("type", "")

                # ── claude stream-json format ──────────────────────────────
                if ev_type == "result":
                    # Final result event; "result" key holds the full text
                    text = event.get("result") or ""
                    if text:
                        agent_messages = [text]   # replace, this is the canonical answer
                    break
                if ev_type == "assistant":
                    msg = event.get("message") or {}
                    for block in msg.get("content", []):
                        if block.get("type") == "text":
                            agent_messages.append(block.get("text", ""))

                # ── codex / agent JSON-lines format ───────────────────────
                if ev_type == "item.completed":
                    item = event.get("item") or {}
                    if item.get("type") == "agent_message":
                        text = item.get("text") or ""
                        if not text and "content" in item:
                            text = "\n".join(
                                b.get("text", "") for b in item["content"] if b.get("text")
                            )
                        if text:
                            agent_messages.append(text)

            if not agent_messages:
                reason = _brief_failure(stdout, stderr)
                attempts.append(f"{executable}#{retry}: no agent_message ({reason})")
                print(f"  [agent] {executable} produced no parseable message: {reason}", flush=True)
                last_error = RuntimeError(
                    f"{executable} produced no parseable output (exit={result.returncode})"
                )
                if retry < MAX_EXECUTION_RETRIES and should_retry_same_executor(stdout, stderr):
                    continue
                if should_retry_next_executor(stdout, stderr):
                    break
                continue

            try:
                payload = parse_agent_payload(agent_messages[-1])
                return payload, stdout, stderr
            except Exception as exc:
                attempts.append(f"{executable}#{retry}: JSON parse failure")
                print(f"  [agent] {executable} response was not valid JSON: {exc}", flush=True)
                last_error = exc
                if retry < MAX_EXECUTION_RETRIES and should_retry_same_executor(stdout, stderr):
                    continue
                if should_retry_next_executor(stdout, stderr):
                    break

    # ── HTTP fallback: Groq / Gemini / Ollama ────────────────────────────────
    print("  [agent] Trying fallback providers (Ollama/Groq/Gemini)...", flush=True)
    http_text = http_llm_fallback(prompt)
    if http_text:
        try:
            payload = parse_agent_payload(http_text)
            return payload, http_text, ""
        except Exception as exc:
            attempts.append(f"http_fallback: JSON parse failure ({exc})")
    else:
        attempts.append("http_fallback: all HTTP providers failed")

    summary = "; ".join(attempts) if attempts else "no attempts recorded"
    if last_error:
        raise RuntimeError(f"All LLM executables failed (CLI + HTTP). {summary}") from last_error
    raise FileNotFoundError(f"No LLM provider worked. Checked CLI: {', '.join(cli_order)}")


# ── stage persistence ─────────────────────────────────────────────────────────

def save_stage(run_dir: Path, cycle: int, role: str, prompt: str, payload: Any, stdout: str, stderr: str) -> Path:
    stage_dir = run_dir / f"cycle_{cycle:02d}" / role
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    (stage_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if stdout:
        (stage_dir / "stdout.jsonl").write_text(stdout, encoding="utf-8")
    if stderr:
        (stage_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    return stage_dir


# ── prompt builders ───────────────────────────────────────────────────────────

def build_solver_prompt(problem: str, cycle: int, history: List[Dict[str, Any]]) -> str:
    lines = [SOLVER_SYSTEM, "", f"## Problem", "", problem, ""]
    if history:
        lines += ["## Context from previous cycles", ""]
        for entry in history:
            c = entry["cycle"]
            lines += [
                f"### Cycle {c} — Critic feedback",
                json.dumps(entry["critic"], indent=2),
                "",
                f"### Cycle {c} — Validator assessment",
                json.dumps(entry["validator"], indent=2),
                "",
            ]
    lines += [f"## Your task", f"Produce your {'initial' if cycle == 1 else 'revised'} solution for cycle {cycle}."]
    return "\n".join(lines)


def build_critic_prompt(problem: str, cycle: int, solver_result: Any) -> str:
    return "\n".join([
        CRITIC_SYSTEM, "",
        "## Problem", "", problem, "",
        "## Solver's proposed solution (cycle {})".format(cycle), "",
        json.dumps(solver_result, indent=2), "",
        "## Your task",
        "Critique the solution above.",
    ])


def build_validator_prompt(problem: str, cycle: int, solver_result: Any, critic_result: Any) -> str:
    return "\n".join([
        VALIDATOR_SYSTEM, "",
        "## Problem", "", problem, "",
        "## Solver's solution (cycle {})".format(cycle), "",
        json.dumps(solver_result, indent=2), "",
        "## Critic's feedback (cycle {})".format(cycle), "",
        json.dumps(critic_result, indent=2), "",
        "## Your task",
        "Validate the solution and return your verdict.",
    ])


# ── main deliberation loop ────────────────────────────────────────────────────

def run_deliberation(
    problem: str,
    cycles: int,
    run_dir: Path,
    cwd: Path,
) -> Dict[str, Any]:
    history: List[Dict[str, Any]] = []
    final_validator: Optional[Dict[str, Any]] = None

    for cycle in range(1, cycles + 1):
        print(f"\n{'='*60}", flush=True)
        print(f"[3Minds] Cycle {cycle}/{cycles}", flush=True)
        print(f"{'='*60}", flush=True)

        # ── Solver ────────────────────────────────────────────────────
        print("[3Minds] -> Solver thinking...", flush=True)
        solver_prompt = build_solver_prompt(problem, cycle, history)
        solver_payload, s_out, s_err = run_agent(solver_prompt, cwd)
        save_stage(run_dir, cycle, "solver", solver_prompt, solver_payload, s_out, s_err)
        print(f"  Solver confidence: {solver_payload.get('confidence', '?')}/10", flush=True)

        # ── Critic ────────────────────────────────────────────────────
        print("[3Minds] -> Critic reviewing...", flush=True)
        critic_prompt = build_critic_prompt(problem, cycle, solver_payload)
        critic_payload, c_out, c_err = run_agent(critic_prompt, cwd)
        save_stage(run_dir, cycle, "critic", critic_prompt, critic_payload, c_out, c_err)
        weaknesses = critic_payload.get("weaknesses", [])

        # ── Validator ─────────────────────────────────────────────────
        print("[3Minds] -> Validator deciding...", flush=True)
        validator_prompt = build_validator_prompt(problem, cycle, solver_payload, critic_payload)
        validator_payload, v_out, v_err = run_agent(validator_prompt, cwd)
        save_stage(run_dir, cycle, "validator", validator_prompt, validator_payload, v_out, v_err)

        verdict = validator_payload.get("verdict", "needs_revision")
        score   = validator_payload.get("score", 0)
        print(f"  Validator verdict: {verdict.upper()}  score: {score}/10", flush=True)

        history.append({
            "cycle":     cycle,
            "solver":    solver_payload,
            "critic":    critic_payload,
            "validator": validator_payload,
        })
        final_validator = validator_payload

        if verdict == "approved":
            print(f"[3Minds] Approved on cycle {cycle}. Stopping early.", flush=True)
            break

    # ── Build summary ─────────────────────────────────────────────────────────
    best_validator = final_validator or {}
    summary: Dict[str, Any] = {
        "problem":           problem,
        "cycles_run":        len(history),
        "cycles_requested":  cycles,
        "final_verdict":     best_validator.get("verdict", "needs_revision"),
        "final_score":       best_validator.get("score", 0),
        "final_answer":      best_validator.get("final_answer", ""),
        "run_dir":           str(run_dir),
        "history":           history,
    }
    # Also write summary.json to disk
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Three-Minds deliberation engine")
    parser.add_argument("--problem",    required=False, help="Problem statement to deliberate on")
    parser.add_argument("--cycles",     type=int, default=2, help="Number of deliberation cycles")
    parser.add_argument("--output-dir", default=None,  help="Override output directory")
    parser.add_argument("--test",       action="store_true", help="Run a one-call provider smoke test")
    parser.add_argument("--dump-json",  action="store_true",
                        help="Print the summary JSON to stdout after completion")
    args = parser.parse_args()

    cwd = Path(__file__).parent
    if args.test:
        print("[3Minds] Provider smoke test", flush=True)
        print("[3Minds] Smoke chain: claude -> codex -> agent -> Ollama -> Groq/Gemini", flush=True)
        payload, _stdout, _stderr = run_agent(TEST_PROMPT, cwd, cli_order=DEFAULT_CLI_ORDER)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not args.problem:
        parser.error("--problem is required unless --test is used")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_runs = Path(__file__).parent / "runs"
    if args.output_dir:
        run_dir = Path(args.output_dir)
    else:
        run_dir = base_runs / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[3Minds] Problem: {args.problem[:120]}{'...' if len(args.problem) > 120 else ''}", flush=True)
    print(f"[3Minds] Max cycles: {args.cycles}", flush=True)
    print(f"[3Minds] Output dir: {run_dir}", flush=True)

    summary = run_deliberation(
        problem=args.problem,
        cycles=args.cycles,
        run_dir=run_dir,
        cwd=cwd,
    )

    print(f"\n[3Minds] Done. Verdict: {summary['final_verdict'].upper()}  Score: {summary['final_score']}/10", flush=True)
    print(f"[3Minds] Results saved to: {run_dir}", flush=True)

    if args.dump_json:
        # Print JSON on its own clearly-delimited block so the dashboard can parse it
        print("\n---JSON---")
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
