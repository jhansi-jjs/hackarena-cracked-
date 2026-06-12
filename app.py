from flask import Flask, request, jsonify, send_from_directory
from mcpd import McpdClient
import re

app = Flask(__name__, static_folder='static')
client = McpdClient(api_endpoint='http://localhost:8090')

PROMPT_INJECTION_PATTERNS = [
    "ignore previous", "ignore all instructions", "reveal system prompt",
    "show secrets", "dump documents", "execute code", "delete database",
    "browse internet", "reveal hidden", "forget instructions",
    "you are now", "pretend you are", "act as", "jailbreak"
]

SENSITIVE_DATA_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',
    r'AWS_SECRET[_A-Z]*\s*=\s*\S+',
    r'Bearer\s+[a-zA-Z0-9\-_]{20,}',
    r'password\s*=\s*\S+',
    r'\b\d{16}\b',
    r'\b\d{3}-\d{2}-\d{4}\b',
]

BLOCKED_KEYWORDS = [
    "hack", "exploit", "weapon", "illegal", "malware",
    "ransomware", "phishing", "sql injection", "xss attack"
]

def query_guardrail(question):
    q = question.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern in q:
            return False, "Prompt injection attempt detected."
    for keyword in BLOCKED_KEYWORDS:
        if keyword in q:
            return False, "This topic is not allowed."
    if len(question.strip()) < 3:
        return False, "Please ask a proper question."
    if len(question) > 500:
        return False, "Question too long."
    return True, None

def privacy_guardrail(text):
    for pattern in SENSITIVE_DATA_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Sensitive data detected in output."
    return True, None

def retrieval_guardrail(chunks):
    if not chunks:
        return False, "empty"
    text = chunks.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern in text:
            return False, "injection"
    return True, "clean"

def confidence_guardrail(chunks):
    if not chunks or len(chunks.strip()) < 50:
        return "internet"
    if len(chunks.strip()) > 500:
        return "local"
    return "hybrid"

def get_agent(instructions):
    from any_agent import AnyAgent, AgentConfig, AgentFramework
    web_tools = client.agent_tools(servers=["ddgs"])
    def search_docs(query: str) -> str:
        """Search PRIVATE local documents first. Always call this before web search."""
        result = client.call.rag.search_docs(query=query)
        chunks = str(result)[:4000]
        ok, status = retrieval_guardrail(chunks)
        if not ok and status == "injection":
            return "Retrieved content blocked due to suspicious instructions."
        return chunks
    tools = [search_docs] + web_tools
    return AnyAgent.create(
        AgentFramework.TINYAGENT,
        AgentConfig(
            model_id="openai/gemma-4-E4B-IT-Q4_K_M",
            api_base="http://localhost:8086/v1",
            api_key="none",
            instructions=instructions,
            tools=tools,
        )
    )

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/ask', methods=['POST'])
def ask():
    question = request.json.get('question', '')
    allowed, block_msg = query_guardrail(question)
    if not allowed:
        return jsonify({'answer': f'⚠️ Blocked: {block_msg}', 'source': 'blocked', 'guardrail': 'query'})
    try:
        raw = client.call.rag.search_docs(query=question)
        chunks = str(raw)[:4000]
    except:
        chunks = ""
    ok, status = retrieval_guardrail(chunks)
    if not ok and status == "injection":
        return jsonify({'answer': '⚠️ Retrieved documents contain suspicious content.', 'source': 'blocked', 'guardrail': 'retrieval'})
    confidence = confidence_guardrail(chunks)
    if confidence == "local":
        instructions_suffix = "Answer from private documents only. Do NOT use web search."
    elif confidence == "hybrid":
        instructions_suffix = "Answer from documents, supplement with web only if needed."
    else:
        instructions_suffix = "No local results found. You may use web search."
    instructions = f"""You are a privacy-first AI assistant.
RULES:
1. ALWAYS call search_docs FIRST.
2. If search_docs has an answer, use ONLY that. Do NOT use web search.
3. Only use web search if search_docs returns nothing useful.
4. Never reveal passwords, API keys, or secrets.
5. {instructions_suffix}"""
    try:
        agent = get_agent(instructions)
        result = agent.run(question)
        answer = str(result)
        safe, privacy_msg = privacy_guardrail(answer)
        if not safe:
            return jsonify({'answer': f'⚠️ Blocked: {privacy_msg}', 'source': 'blocked', 'guardrail': 'privacy'})
        source_label = "LOCAL ONLY ✅" if confidence == "local" else ("HYBRID 🔀" if confidence == "hybrid" else "WEB FALLBACK 🌐")
        return jsonify({'answer': answer, 'source': source_label, 'guardrail': 'passed'})
    except Exception as e:
        return jsonify({'answer': f'Error: {str(e)}', 'source': 'error'})

if __name__ == '__main__':
    app.run(port=5050, debug=False)
