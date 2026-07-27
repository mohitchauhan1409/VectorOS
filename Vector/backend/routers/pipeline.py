"""Pipeline routes — READ-ONLY run history/status.

Triggering a run is a backend-only operation (see backend/manage.py); it is
intentionally NOT exposed over the API. The frontend can only observe runs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import PipelineRun, User
from backend.security import get_current_user
from backend.serializers import _iso

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _run_out(r: PipelineRun) -> dict:
    return {
        "id": r.id,
        "status": r.status,
        "stage": r.stage,
        "mode": r.mode,
        "companies_found": r.companies_found,
        "people_found": r.people_found,
        "enrolled": r.enrolled,
        "messages_sent": r.messages_sent,
        "error": r.error,
        "started_at": _iso(r.started_at),
        "finished_at": _iso(r.finished_at),
    }


@router.get("/runs")
def list_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PipelineRun)
        .where(PipelineRun.workspace_id == user.workspace_id)
        .order_by(PipelineRun.started_at.desc())
        .limit(20)
    ).all()
    return {"items": [_run_out(r) for r in rows]}


@router.get("/runs/{run_id}")
def get_run(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(PipelineRun, run_id)
    if not r or r.workspace_id != user.workspace_id:
        raise HTTPException(404, "Run not found")
    return _run_out(r)
