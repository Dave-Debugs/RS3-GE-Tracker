from __future__ import annotations

from fastapi import Request

from .collector.scheduler import CollectorScheduler
from .db.repository import Repository

def get_repo(request: Request) -> Repository:
    return request.app.state.repo

def get_scheduler(request: Request) -> CollectorScheduler:
    return request.app.state.scheduler
