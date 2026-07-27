"""Account provisioning — accounts are created from the backend only.

There is intentionally no public signup. Use `python -m backend.manage`
(or these helpers) to create accounts.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import User, Workspace
from backend.security import hash_password


def create_account(
    db: Session,
    *,
    email: str,
    password: str,
    name: str,
    role: str = "Owner",
    workspace_name: str | None = None,
    is_demo: bool = False,
) -> User:
    """Create a user in a fresh workspace. Raises ValueError if the email exists."""
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise ValueError(f"An account already exists for {email}")

    ws = Workspace(name=workspace_name or f"{name}'s Workspace", is_demo=is_demo)
    db.add(ws)
    db.flush()
    user = User(
        workspace_id=ws.id,
        email=email,
        password_hash=hash_password(password),
        name=name,
        role=role,
        is_demo=is_demo,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
