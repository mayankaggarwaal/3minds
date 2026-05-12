# 3minds…

> **Think. Question. Validate.**

A multi-agent AI deliberation app where three AI agents — **Solver**, **Critic**, and **Validator** — debate to reach the best possible answer to your question.

🌐 **Live demo → [mayankaggarwaal.github.io/3minds](https://mayankaggarwaal.github.io/3minds)**

---

## How it works

| Agent | Role |
|-------|------|
| 🧠 **Solver** | Proposes an initial answer |
| 🔍 **Critic** | Challenges assumptions and pokes holes |
| ✅ **Validator** | Weighs both sides and delivers the final verdict |

Runs for 1–3 cycles so the agents can refine their thinking.

---

## Run locally

### 1. Clone the repo

```bash
git clone https://github.com/mayankaggarwaal/3minds.git
cd 3minds
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

> Requires **Python 3.9+**

### 3. Set up an API key (pick one)

**Gemini (free tier — recommended)**
- Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- Create a free key and paste it in the app's Settings panel

**OpenAI**
- Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Create a key and paste it in Settings

**Ollama (fully local, no key needed)**
- Install from [ollama.com](https://ollama.com)
- Pull a model: `ollama pull llama3`
- Set the Ollama URL to `http://localhost:11434` in Settings

### 4. (Optional) Use Claude CLI or Codex CLI for fully local, no-key runs

**Claude CLI**
```bash
npm install -g @anthropic-ai/claude-code
claude   # authenticate once
```
→ [Claude CLI docs](https://docs.anthropic.com/en/docs/claude-code)

**Codex CLI (OpenAI)**
```bash
npm install -g @openai/codex
codex     # authenticate once
```
→ [Codex CLI repo](https://github.com/openai/codex)

Once installed, relaunch the app — it auto-detects them and sets the default model accordingly (Claude › Codex › Gemini).

### 5. Launch the Streamlit app

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

---

## Use the browser version (no install)

Just open [mayankaggarwaal.github.io/3minds](https://mayankaggarwaal.github.io/3minds) — paste your API key in Settings and go. Works on mobile too.

---

## Contributing

Pull requests are welcome! Some ideas:

- 🌍 Add more AI providers (Mistral, Cohere, Groq…)
- 💾 Export conversation history as PDF / Markdown
- 🎨 Themes / light mode
- 🔁 Smarter multi-cycle debate strategies

```bash
# Fork, then:
git checkout -b feature/your-idea
# make changes
git push origin feature/your-idea
# open a PR
```

---

## Built by

**Mayank Aggarwal**  
[github.com/mayankaggarwaal](https://github.com/mayankaggarwaal) · [linkedin.com/in/mayank-a-2b4664149](https://www.linkedin.com/in/mayank-a-2b4664149/)

---

## License

MIT — use it, remix it, build on it.
