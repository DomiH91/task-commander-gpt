# Force redeploy marker
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pydantic.functional_validators import model_validator
from dotenv import load_dotenv
import requests

# 1) Lade .env ins Environment
load_dotenv()

app = FastAPI()

# 2) Token aus ENV rausziehen (kein Fallback mehr)
TODOIST_TOKEN = os.getenv("TODOIST_TOKEN")
if not TODOIST_TOKEN:
    raise RuntimeError("Missing TODOIST_TOKEN in environment")

# Health‐check
@app.get("/")
def root():
    return {"status": "alive"}

# Payload zum Abschließen
class CompleteTaskInput(BaseModel):
    task_id: str
    comment: str = ""

# Payload zum Hinzufügen
class AddTaskInput(BaseModel):
    content: str
    due_string: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    duration_minutes: int | None = None

    @model_validator(mode="after")
    def validate_input(cls, model):
        if not (model.project_id or model.project_name):
            raise ValueError("Either project_id or project_name must be provided")
        if not model.due_string and model.duration_minutes is None:
            raise ValueError(
                "If you don't specify a due date, you must provide an estimated duration_minutes"
            )
        return model

# Menü‐Endpoint
@app.get("/init_menu")
def init_menu():
    return {
        "options": [
            "top3_focus",
            "full_overview",
            "complete_task",
            "add_task",
            "get_projects"
        ]
    }

# Tasks abrufen und anreichern
@app.get("/get_tasks")
def get_tasks():
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    resp = requests.get("https://api.todoist.com/rest/v2/tasks", headers=headers, timeout=5)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")
    tasks = resp.json()

    enriched = []
    for t in tasks:
        tags = []
        if t.get("due"):
            tags.append("has_due")
        if "review" in t["content"].lower():
            tags.append("DeepWork")
        due_info = t.get("due") or {}
        enriched.append({
            "id": t["id"],
            "content": t["content"],
            "due": due_info.get("date"),
            "duration_minutes": None,
            "tags": tags
        })

    return {"tasks": enriched}

# Projekte abrufen
@app.get("/get_projects")
def get_projects():
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    resp = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers, timeout=5)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch projects")
    projs = resp.json()
    return {"projects": [{"id": p["id"], "name": p["name"]} for p in projs]}

# Task abschließen
@app.post("/complete_task")
def complete_task(data: CompleteTaskInput):
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    resp = requests.post(
        f"https://api.todoist.com/rest/v2/tasks/{data.task_id}/close",
        headers=headers,
        timeout=5
    )
    if resp.status_code != 204:
        raise HTTPException(status_code=500, detail="Failed to close task")
    return {"status": "completed", "task_id": data.task_id}

# Task anlegen
@app.post("/add_task")
def add_task(data: AddTaskInput):
    headers = {
        "Authorization": f"Bearer {TODOIST_TOKEN}",
        "Content-Type": "application/json"
    }

    # Projekt-ID per Name auflösen (falls nötig)
    if not data.project_id and data.project_name:
        proj_resp = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers, timeout=5)
        proj_resp.raise_for_status()
        match = next(
            (p for p in proj_resp.json() if p["name"].lower() == data.project_name.lower()),
            None
        )
        if not match:
            raise HTTPException(status_code=400, detail=f"Project '{data.project_name}' not found")
        project_id = match["id"]
    else:
        project_id = data.project_id

    # Payload aufbauen
    payload: dict = {
        "content": data.content,
        "project_id": project_id
    }
    if data.due_string:
        payload["due_string"] = data.due_string
    # duration_minutes tracken, aber nicht in Todoist übertragen
    # Du kannst es intern speichern oder später in Outlook blocken
    # Hier nur als Teil des Payloads sichtbar
    payload["duration_minutes"] = data.duration_minutes

    resp = requests.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers, timeout=5)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return resp.json()