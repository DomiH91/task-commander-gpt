# models/schemas.py
from pydantic import BaseModel
from typing import Optional, List

class CompleteTaskInput(BaseModel):
    task_id: str
    comment: Optional[str] = ""

class LabelUpdateInput(BaseModel):
    task_id: str
    labels: List[str]

class AddTaskInput(BaseModel):
    content: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    due_string: Optional[str] = None
    duration_minutes: Optional[int] = None

class UpdateTaskInput(BaseModel):
    task_id: str
    content: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    due_string: Optional[str] = None
    duration_minutes: Optional[int] = None
    priority: Optional[int] = None
    labels: Optional[List[str]] = None

class QuickAddInput(BaseModel):
    content: str

class AcceptLabelsInput(BaseModel):
    accept: List[str]  # Liste von task_ids