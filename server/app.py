"""
Jira-to-PR OpenEnv Server
=========================
FastAPI application exposing the full OpenEnv HTTP + WebSocket interface.

Endpoints:
  GET  /health  →  {"status": "healthy"}
  POST /reset   →  StepResult JSON
  POST /step    →  StepResult JSON
  GET  /state   →  AgencyState JSON
  WS   /ws      →  Persistent WebSocket session
  GET  /web     →  Interactive HTML dashboard
  GET  /docs    →  Auto-generated OpenAPI docs
"""

import sys
import os
import json
import asyncio

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from env import MockAgencyEnv, TASKS
from models import AgencyAction, AgencyObservation, AgencyState, StepResult

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app = FastAPI(
    title="Jira-to-PR Mock Agency",
    description="An OpenEnv environment where an AI agent resolves Jira tickets by editing code and submitting PRs.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared environment instance for HTTP (stateless per-request)
_http_env = MockAgencyEnv()

# Mount the static dashboard
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy"}


# ─────────────────────────────────────────────
# RESET (HTTP POST)
# ─────────────────────────────────────────────

@app.post("/reset")
async def reset(request: Request):
    """Reset the environment, optionally with a specific task_id."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    task_id = body.get("task_id", None)
    result = await _http_env.reset(task_id=task_id)
    return result.model_dump()


# ─────────────────────────────────────────────
# STEP (HTTP POST)
# ─────────────────────────────────────────────

@app.post("/step")
async def step(request: Request):
    """Execute one agent action."""
    body = await request.json()

    # Accept either {"action": {...}} wrapper or flat action dict
    action_data = body.get("action", body)
    action = AgencyAction(**action_data)
    result = await _http_env.step(action)
    return result.model_dump()


# ─────────────────────────────────────────────
# STATE (HTTP GET)
# ─────────────────────────────────────────────

@app.get("/state")
async def get_state():
    """Return current environment state."""
    state = await _http_env.state()
    return state.model_dump()


# ─────────────────────────────────────────────
# TASKS LIST (bonus endpoint)
# ─────────────────────────────────────────────

@app.get("/tasks")
async def list_tasks():
    """List all available tasks with grader flags for the validator."""
    return [
        {
            "id": t["id"], 
            "title": t["name"], 
            "description": t["description"],
            "has_grader": True,
            "reward_type": "incremental"
        }
        for t in _http_env.tasks
    ]


# ─────────────────────────────────────────────
# WEBSOCKET SESSION
# ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Persistent WebSocket session — each connection gets its own env instance."""
    await websocket.accept()
    env = MockAgencyEnv()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "reset":
                task_id = data.get("task_id", None)
                result = await env.reset(task_id=task_id)
                await websocket.send_json({"type": "reset", **result.model_dump()})

            elif msg_type == "step":
                action_data = data.get("action", {})
                action = AgencyAction(**action_data)
                result = await env.step(action)
                await websocket.send_json({"type": "step", **result.model_dump()})

            elif msg_type == "state":
                state = await env.state()
                await websocket.send_json({"type": "state", **state.model_dump()})

            elif msg_type == "close":
                await env.close()
                await websocket.send_json({"type": "closed"})
                break

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        await env.close()
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        await env.close()


# ─────────────────────────────────────────────
# WEB DASHBOARD
# ─────────────────────────────────────────────

@app.get("/web", response_class=HTMLResponse)
async def web_dashboard():
    """Serve the interactive HTML dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard not found. Place index.html in /static/</h1>", status_code=404)


# ─────────────────────────────────────────────
# ROOT (redirect to /web)
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root to the web dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Jira-to-PR Mock Agency</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    """Entry point for openenv and direct execution."""
    import uvicorn

    port = int(os.getenv("PORT", "7860"))
    host = os.getenv("HOST", "0.0.0.0")
    workers = int(os.getenv("WORKERS", "1"))
    uvicorn.run("server.app:app", host=host, port=port, workers=workers, reload=False)


if __name__ == "__main__":
    main()
