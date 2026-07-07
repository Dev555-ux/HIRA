"""Business settings API (/api/v1/settings).

Currently exposes just the AI Reply Mode (`Business.mode`): "assisted" (a human
approves every reply before it sends) or "autonomous" (the AI sends replies
immediately). See app/ai/processing.py for where this flag is read.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.models import Business

router = APIRouter(prefix="/api/v1", tags=["settings"])


class UpdateSettingsRequest(BaseModel):
    mode: Literal["assisted", "autonomous"]


def _serialize(business: Business) -> dict:
    return {"mode": business.mode}


def _get_business(db: Session, principal: Principal) -> Business:
    business = db.get(Business, principal.business_id)
    if business is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return business


@router.get("/settings")
def get_settings(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    business = _get_business(db, principal)
    return {"data": _serialize(business)}


@router.patch("/settings")
def update_settings(
    payload: UpdateSettingsRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    business = _get_business(db, principal)
    business.mode = payload.mode
    db.commit()
    return {"data": _serialize(business)}
