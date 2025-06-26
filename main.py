# Force redeploy marker
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI()

TODOIST_TOKEN = "067a491221f78bb9d45b8e30f275399f5c932652"  # Nur lokal – später via secrets/env

class CompleteTaskInput(BaseModel):
    task_id: str
    comment: str = ""

class AddTaskInput(BaseModel):
    content: str
    due_string: str
    project_id: str

@app.get("/init_menu")
def init_menu():
    return {"options": ["top3_focus", "full_overview", "complete_task", "add_task"]}

@app.get("/get_tasks")
def get_tasks():
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    response = requests.get("https://api.todoist.com/rest/v2/tasks", headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")

    tasks = response.json()
    # Basic enrichment: Dummy tags for demo
    enriched = []
    for t in tasks:
        tags = []
        if t.get("due"):
            tags.append("has_due")
        if "review" in t["content"].lower():
            tags.append("DeepWork")
        enriched.append({
            "id": t["id"],
            "content": t["content"],
            "due": t.get("due", {}).get("date"),
            "tags": tags
        })

    return {"tasks": enriched}

@app.post("/complete_task")
def complete_task(data: CompleteTaskInput):
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    response = requests.post(
        f"https://api.todoist.com/rest/v2/tasks/{data.task_id}/close",
        headers=headers
    )
    if response.status_code != 204:
        raise HTTPException(status_code=500, detail="Failed to close task")
    return {"status": "completed", "task_id": data.task_id}

@app.post("/add_task")
def add_task(data: AddTaskInput):
    headers = {
        "Authorization": f"Bearer {TODOIST_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "content": data.content,
        "due_string": data.due_string,
        "project_id": data.project_id
    }
    response = requests.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return response.json()