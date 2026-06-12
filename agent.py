"""
local_first_agent.py
=====================
Mozilla.ai track — "Answer from private local documents first, reach the public
internet only when needed." Ties together:

    llamafile     -> local LLM (OpenAI-compatible server, default :8086)
    mcpd          -> manages your MCP servers and exposes them over HTTP (:8090)
                       - rag-mcp-server  : search your private vector store
                       - ddgs-mcp-server : DuckDuckGo web search (the fallback)
    encoderfile   -> embeddings behind the RAG server (nothing to wire here;
                       rag-mcp-server already uses it)
    any-agent     -> the agent runtime; gets BOTH toolsets and is told, via the
                       system prompt, to always try local docs first.

The "local-first" rule is enforced in INSTRUCTIONS below. The agent has access
to web search, but is instructed to only use it when the private documents can't
answer the question.

Run:
    uv add any-agent mcpd          # or: pip install any-agent mcpd
    python local_first_agent.py
"""

from any_agent import AgentConfig, AnyAgent
from any_agent.tracing.attributes import GenAI
from mcpd import McpdClient, McpdError

# ---------------------------------------------------------------------------
# CONFIG  — confirm these three against your own setup (see CHECKLIST at bottom)
# ---------------------------------------------------------------------------
MCPD_ENDPOINT   = "http://localhost:8090"        # mcpd daemon REST API
LLAMAFILE_BASE  = "http://localhost:8086/v1"     # llamafile OpenAI-compatible API
LLAMAFILE_MODEL = "openai/local-model"           # provider must be 'openai'; name is ignored by llamafile
FRAMEWORK       = "tinyagent"                     # ships with bare any-agent, ideal for local LLMs

# If your mcpd servers are registered under different names than these, the
# script still works (it passes ALL tools). These are only used to make the
# system prompt name the right tools. Adjust if `client.servers()` prints
# something different (e.g. "rag" / "ddgs").
RAG_HINTS = ("rag", "vector", "doc")             # substrings that identify the local-docs server
WEB_HINTS = ("ddgs", "duck")    # substrings that identify the web-search server


# ---------------------------------------------------------------------------
# 1. Connect to mcpd and pull tools as any-agent callables
# ---------------------------------------------------------------------------
def build_tools_and_prompt():
    client = McpdClient(api_endpoint=MCPD_ENDPOINT)

    try:
        servers = client.servers()
    except McpdError as e:
        raise SystemExit(
            f"Could not reach mcpd at {MCPD_ENDPOINT}.\n"
            f"Is the daemon running?  ->  mcpd daemon --dev\nError: {e}"
        )

    print(f"mcpd servers: {servers}")

    # Identify which registered server is the local RAG one and which is web.
    rag_servers = [s for s in servers if any(h in s.lower() for h in RAG_HINTS)]
    web_servers = [s for s in servers if any(h in s.lower() for h in WEB_HINTS)]
    print(f"  -> local/RAG server(s): {rag_servers or '??? (none matched RAG_HINTS)'}")
    print(f"  -> web/search server(s): {web_servers or '??? (none matched WEB_HINTS)'}")

    # Pull every tool from every healthy server as plain callables.
    # (agent_tools() already filters out unhealthy servers.)
    # Web search tools (the fallback), straight from mcpd.
    web_tools = client.agent_tools(servers=["ddgs"])

    # Local-docs tool, WRAPPED so it returns a trimmed amount of text.
    # The raw rag tool dumps every chunk and overflows the small local
    # model, making it hang. We cap the text here.
    def search_docs(query: str) -> str:
        """Search the user's PRIVATE local documents (runbooks, specs,
        internal notes). Returns the most relevant text. Use this FIRST."""
        result = client.call.rag.search_docs(query=query)
        return str(result)[:4000]

    tools = [search_docs] + web_tools
    tool_names = [getattr(t, "__name__", str(t)) for t in tools]
    print(f"  -> tools wired into agent: {tool_names}\n")

    # Describe the tools to the model so the local-first rule is concrete.
    rag_tool_names = [n for n in tool_names if any(h in n.lower() for h in RAG_HINTS)]
    web_tool_names = [n for n in tool_names if any(h in n.lower() for h in WEB_HINTS)]

    instructions = f"""You are a privacy-first research assistant.

You have access to a PRIVATE local document collection (via the RAG / vector-store
tools) and, as a last resort, the PUBLIC internet (via the web-search tool).

Local document tools (search these FIRST): {rag_tool_names or 'the RAG / vector-store tool'}
Web search tool (fallback ONLY): {web_tool_names or 'the web search tool'}

STRICT PROTOCOL — follow in order for EVERY question:
1. ALWAYS begin by calling a local document tool to search the private collection.
2. Read the retrieved passages. If they fully answer the question, answer using
   ONLY that information and DO NOT call any web tool.
3. Only if the local documents are empty, irrelevant, or clearly insufficient,
   THEN call the web search tool to fill the gap.
4. End every answer with a source line:
     "Source: local documents"        (if step 2 answered it), or
     "Source: local documents were insufficient; supplemented with web search".
   When you used local docs, name the document(s) you drew from if available.

Never skip step 1. Never touch the internet when the private documents already
contain the answer. Be concise and accurate."""

    return tools, instructions


# ---------------------------------------------------------------------------
# 2. Build the agent (llamafile as the LLM, mcpd tools attached)
# ---------------------------------------------------------------------------
def build_agent():
    tools, instructions = build_tools_and_prompt()

    agent = AnyAgent.create(
        FRAMEWORK,
        AgentConfig(
            model_id=LLAMAFILE_MODEL,
            api_base=LLAMAFILE_BASE,
            api_key="sk-no-key-required",   # llamafile accepts any key; this just
                                            # stops any-llm from hunting for OPENAI_API_KEY
            instructions=instructions,
            tools=tools,
            model_args={"temperature": 0.0},
        ),
    )
    return agent


# ---------------------------------------------------------------------------
# 3. Inspect a run so you can SEE local-first behaviour (great for the demo)
# ---------------------------------------------------------------------------
def report_sources(trace):
    used = []
    for span in trace.spans:
        if span.is_tool_execution():
            used.append(span.attributes.get(GenAI.TOOL_NAME, "unknown"))
    if not used:
        print("   [tools called: none — answered from model knowledge]")
        return
    hit_web = any(any(h in t.lower() for h in WEB_HINTS) for t in used)
    hit_rag = any(any(h in t.lower() for h in RAG_HINTS) for t in used)
    tag = ("LOCAL ONLY ✅" if hit_rag and not hit_web else
           "WEB FALLBACK 🌐" if hit_web else
           "OTHER")
    print(f"   [tools called: {used}  ->  {tag}]")


# ---------------------------------------------------------------------------
# 4. REPL
# ---------------------------------------------------------------------------
def main():
    print("Building local-first agent...\n")
    agent = build_agent()
    print("Ready. Ask a question (Ctrl-C or 'quit' to exit).\n")

    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break
        if q.lower() in {"quit", "exit", ""}:
            print("bye")
            break

        trace = agent.run(q)
        print(f"\nagent> {trace.final_output}")
        report_sources(trace)
        print()


if __name__ == "__main__":
    main()


# ===========================================================================
# CHECKLIST — confirm before running
# ---------------------------------------------------------------------------
# 1. mcpd is up and shows your two servers:
#       curl -s http://localhost:8090/api/v1/servers | python -m json.tool
#    (or just run this script — it prints client.servers() on startup)
#
# 2. llamafile is serving on the port in LLAMAFILE_BASE:
#       curl http://localhost:8086/v1/models
#    If it lists a model, you're good. Adjust the port if yours differs.
#
# 3. The RAG_HINTS / WEB_HINTS match your actual mcpd server names. If the
#    startup print shows "??? (none matched)", edit those tuples so they
#    contain a substring of your real server names.
#
# 4. If you'd rather HARD-force local-first (not trust the prompt), see the
#    deterministic variant note in the chat — call the RAG tool yourself first,
#    then only invoke the agent with web tools if RAG returns nothing.
# ===========================================================================
