# services/todoist.py

import httpx
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
        # Konvertiere duration_minutes in Todoist-kompatibles Format
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
        # Konvertiere duration_minutes in Todoist-kompatibles Format
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

    async def update_labels(self, task_id: str, labels: list[str]):
        # Schritt 1: Lade Label-IDs von Todoist
        r_labels = await self.client.get(
            f"{self.base_url}/labels",
            headers=self.headers,
            timeout=self.timeout
        )
        r_labels.raise_for_status()
        label_map = {l["name"].strip().lower(): l["id"] for l in r_labels.json()}
        label_ids = [label_map[l.lower()] for l in labels if l.lower() in label_map]

        # Schritt 2: Setze neue Labels (überschreibt bestehende)
        r = await self.client.post(
            f"{self.base_url}/tasks/{task_id}/labels",
            headers=self.headers,
            json={"label_ids": label_ids},
            timeout=self.timeout
        )
        r.raise_for_status()

async def get_todoist_service(
    request: Request,
    config: AppConfig = Depends(),
) -> TodoistService:
    """
    FastAPI dependency that retrieves the shared TodoistService
    instance from the app state.
    """
    return request.app.state.todoist_service