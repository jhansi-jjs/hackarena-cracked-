# 🛡️ TrustRAG — Privacy-First Local AI Agent
### Team Cracked | Mozilla.ai HackerArena 2.0

> **"Answer from your private documents first. Go to the internet only when you must."**

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-black?style=flat-square&logo=flask)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Guardrails](https://img.shields.io/badge/Guardrails-10%20Active-purple?style=flat-square)

---

## 🧠 What is TrustRAG?

TrustRAG is a **privacy-first AI agent** that:
- 🔒 Searches your **private local documents first** (runbooks, specs, internal notes)
- 🌐 Falls back to the **public internet only when local docs don't have the answer**
- 🛡️ Has **10 security guardrails** to block prompt injection, sensitive data leaks, and malicious queries
- 💬 Has a clean **dark-themed chat UI** accessible from any browser

Built for **Mozilla.ai HackerArena 2.0 — Track 2**.

---

## 🏗️ Architecture

```
User Question
     ↓
[Query Guardrail] → blocks malicious/injected queries
     ↓
[Local RAG Search] → searches private vector store via mcpd + rag-mcp-server
     ↓
[Retrieval Guardrail] → validates chunks for injection/toxic content
     ↓
[Confidence Guardrail] → scores how good the local results are
     ↓
[Router Guardrail] → decides: LOCAL / HYBRID / WEB FALLBACK
     ↓
[LLM via llamafile] → generates answer using gemma model
     ↓
[Privacy Guardrail] → scans output for API keys, secrets, PII
     ↓
Answer shown in UI with source tag (LOCAL ONLY ✅ / WEB FALLBACK 🌐)
```

---

## 🛡️ 10 TrustRAG Guardrails

| # | Guardrail | What it does |
|---|-----------|-------------|
| 1 | **File Upload** | Magic-byte + MIME + extension + size validation |
| 2 | **Malware** | ClamAV scan + known signature detection |
| 3 | **Document Sanitization** | Strips prompt injection from ingested docs |
| 4 | **Chunk-Level** | Scans every chunk before it enters the vector DB |
| 5 | **Embedding** | Detects poisoned/duplicate/adversarial embeddings |
| 6 | **Query** | Blocks malicious user prompts & injection attempts |
| 7 | **Privacy** | Detects API keys, passwords, tokens, PII in output |
| 8 | **Retrieval** | Validates retrieved chunks before sending to LLM |
| 9 | **Confidence** | Routes based on retrieval quality (local/hybrid/web) |
| 10 | **Router** | Controls when internet access is allowed |

---

## 🧰 Tech Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| 🧠 LLM | [llamafile](https://github.com/Mozilla-Oasis/llamafile) | Local language model (gemma-4-E4B) |
| 🔢 Embeddings | [encoderfile](https://github.com/Mozilla-Oasis/encoderfile) | Local sentence embeddings |
| 🗄️ Vector Store | ChromaDB (via rag-mcp-server) | Private document storage & retrieval |
| 🔧 MCP Daemon | [mcpd](https://github.com/Mozilla-Oasis/mcpd) | Orchestrates MCP servers |
| 🤖 Agent | [any-agent](https://github.com/Mozilla-Oasis/any-agent) | Multi-tool agent framework |
| 🌐 Web Search | ddgs-mcp-server (DuckDuckGo) | Internet fallback search |
| 🖥️ Backend | Flask (Python) | REST API server |
| 🎨 Frontend | HTML + CSS + JS | Chat UI |

---

## 📋 Prerequisites

- Ubuntu Linux (tested on 24.04)
- Python 3.12+
- Git

Download these from the Mozilla.ai Starter Kit:
- `llamafile` — local LLM binary
- `encoderfile` — local embeddings binary
- `mcpd` — MCP daemon

---

## ⚙️ Installation

### 1. Clone the repo
```bash
git clone https://github.com/jhansi-jjs/hackarena-cracked-.git
cd hackarena-cracked-
```

### 2. Create a virtual environment
```bash
python3 -m venv ~/agent-env
source ~/agent-env/bin/activate
```

### 3. Install dependencies
```bash
pip install flask any-agent mcpd
```

### 4. Start the Mozilla.ai stack
```bash
# Terminal 1 — Start llamafile (LLM)
./llamafile --server --port 8086

# Terminal 2 — Start encoderfile (embeddings)  
./encoderfile --server --port 8088

# Terminal 3 — Start mcpd (MCP daemon)
cd "Starter Kit"
mcpd dev --log-level=DEBUG --log-path /tmp/mcpd.log
```

### 5. Run TrustRAG
```bash
# Terminal 4
source ~/agent-env/bin/activate
python3 app.py
```

### 6. Open in browser
```
http://localhost:5050
```

---

## 💬 Usage

1. Open `http://localhost:5050` in your browser
2. Type your question and press **Enter** or click **Send**
3. The agent searches your private docs first
4. If local docs have the answer → `LOCAL ONLY ✅`
5. If not → falls back to web → `WEB FALLBACK 🌐`
6. Blocked queries show → `🛡️ BLOCKED by query guardrail`

### Example questions to try:
- ✅ `"What do I do for a duplicate charge?"` — answered from local runbook
- ✅ `"What is the circuit breaker configuration?"` — answered from local docs
- 🌐 `"What is the weather today?"` — falls back to web
- 🛡️ `"How do I hack a system?"` — instantly blocked by guardrail

---

## 📁 Project Structure

```
hackarena-cracked-/
├── app.py              # Flask backend with 10 guardrails
├── agent.py            # Terminal agent (CLI version)
├── static/
│   └── index.html      # Chat UI
├── corpus/
│   └── runbook.md      # Sample private document
├── .mcpd.toml          # mcpd server configuration
└── README.md           # This file
```

## 📄 License

MIT License — feel free to use and build on this!
