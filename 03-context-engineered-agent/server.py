"""
Web server for Example 3.

- Starts the MCP travel server (mcp_server.py) as a subprocess over stdio and
  connects to it as an MCP client.
- Exposes a small JSON API used by the React front end.
- Serves the front end from ./frontend.

Run:  python server.py   then open http://localhost:8000
"""
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from mcp import Client, StdioServerParameters
from pydantic import BaseModel

from agent import TravelAgent, TurnOptions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(BASE_DIR, "mcp_server.py")], cwd=BASE_DIR)
    async with Client(params) as mcp_client:
        # Read the server's resource so the agent knows which airports exist
        resource = await mcp_client.read_resource("travel://locations")
        locations = json.loads(resource.contents[0].text)

        llm = None
        if os.environ.get("OPENAI_API_KEY"):
            from openai import AsyncOpenAI
            llm = AsyncOpenAI()
        agent = TravelAgent(mcp_client, locations, llm, model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"))
        await agent.start()
        state["agent"] = agent
        state["lock"] = asyncio.Lock()   # one turn at a time: the MCP session and sessions dict are shared
        print(f"Agent ready in {agent.mode} mode with {len(agent.mcp_tools)} MCP tools: "
              f"{', '.join(t.name for t in agent.mcp_tools)}")
        yield


app = FastAPI(title="Example 3 - Context-engineered travel agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    traveller_id: str | None = None
    use_rag: bool = True
    use_graph: bool = True
    use_skills: bool = True


class ResetRequest(BaseModel):
    session_id: str


@app.get("/api/config")
async def config():
    agent: TravelAgent = state["agent"]
    travellers = [{"id": n["id"], "name": n["label"], **n["props"]}
                  for n in agent.graph.nodes.values() if n["type"] == "Traveller"]
    return {
        "mode": agent.mode,
        "model": agent.model if agent.llm else None,
        "airports": [{"code": c, **{k: a[k] for k in ("name", "city", "country")}} for c, a in agent.locations["airports"].items()],
        "travellers": travellers,
        "mcp_tools": [{"name": t.name, "description": (t.description or "").split("\n")[0]} for t in agent.mcp_tools],
        "skills": [{"name": s["name"], "description": s["description"]} for s in agent.skills.skills.values()],
        "knowledge_chunks": len(agent.kb.chunks),
        "graph": {"nodes": len(agent.graph.nodes), "edges": len(agent.graph.edges)},
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    agent: TravelAgent = state["agent"]
    opts = TurnOptions(use_rag=req.use_rag, use_graph=req.use_graph, use_skills=req.use_skills)
    async with state["lock"]:
        try:
            return await agent.chat(req.session_id, req.message, req.traveller_id or None, opts)
        except Exception as e:
            return {"reply": f"⚠️ The agent hit an error: `{e}`", "mode": agent.mode, "trace": [
                {"kind": "error", "title": type(e).__name__, "detail": str(e)}],
                "context": {"rag": [], "graph": None, "skills_loaded": []}, "new_bookings": [],
                "bookings": agent.session(req.session_id)["bookings"]}


@app.post("/api/reset")
async def reset(req: ResetRequest):
    state["agent"].reset(req.session_id)
    return {"ok": True}


app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
