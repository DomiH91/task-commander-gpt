# services/todoist.py

import httpx
import uuid
import json
from fastapi import HTTPException
from core.config import AppConfig
from fastapi import Depends, Request

class TodoistService:
    def __init__(self, client: httpx.AsyncClient, config: AppConfig):
        self.client = client
        self.base_url = config.todoist_api_url
        self.headers = {
            "Authorization": f"Bearer {config.todoist_token}",
            "Content-Type": "application/json",
        }
        self.timeout = config.todoist_timeout

    async def get_tasks(self, limit: int = 50, offset: int = 0):
        r = await self.client.get(
            f"{self.base_url}/tasks",
            headers=self.headers,
            params={"limit": limit, "offset": offset},
            timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    async def close_task(self, task_id: str):
        r = await self.client.post(
            f"{self.base_url}/tasks/{task_id}/close",
            headers=self.headers,
            timeout=self.timeout
        )
        r.raise_for_status()

    async def add_task(self, payload: dict):
        if "duration_minutes" in payload:
            payload["duration"] = {
                "amount": payload.pop("duration_minutes"),
                "unit": "minute"
            }

        r = await self.client.post(
            f"{self.base_url}/tasks",
            headers=self.headers,
            json=payload,
            timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    async def update_task(self, task_id: str, payload: dict):
        if "duration_minutes" in payload:
            payload["duration"] = {
                "amount": payload.pop("duration_minutes"),
                "unit": "minute"
            }

        r = await self.client.patch(
            f"{self.base_url}/tasks/{task_id}",
            headers=self.headers,
            json=payload,
            timeout=self.timeout
        )
        r.raise_for_status()

    async def sync_update_labels(self, task_id: str, label_names: list[str]):
        # 1. Labels laden
        r_labels = await self.client.get(
            "https://api.todoist.com/rest/v2/labels",
            headers=self.headers,
            timeout=self.timeout
        )
        r_labels.raise_for_status()
        label_map = {l["name"].strip().lower(): l["id"] for l in r_labels.json()}

        # 2. IDs sammeln
        label_ids = [int(label_map[n.lower()]) for n in label_names if n.lower() in label_map]
        print("🔎 Mapped label_ids:", label_ids)

        if not label_ids:
            raise HTTPException(status_code=400, detail="Keines der angegebenen Labels gefunden.")

        # 3. Sync-Command definieren
        commands = [{
            "type": "item_update",
            "uuid": str(uuid.uuid4()),
            "args": {
                "id": task_id,
                "label_ids": label_ids
            }
        }]
        print("📦 Commands payload:", commands)

        # 4. Sync-Aufruf—korrekt als JSON
        sync_url = "https://api.todoist.com/sync/v9/sync"
        payload = {
            "sync_token": "*",
            "commands": commands
        }

        r = await self.client.post(
            sync_url,
            headers=self.headers,
            json=payload,
            timeout=self.timeout
        )
        print("🔁 Sync-Response status:", r.status_code, "body:", r.text)
        r.raise_for_status()
        return r.json()

async def get_todoist_service(
    request: Request,
    config: AppConfig = Depends(),
) -> TodoistService:
    return request.app.state.todoist_service