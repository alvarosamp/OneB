"""Ajudantes de teste: cria um usuário real no banco de teste e o instala como o usuário logado."""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User


def install_test_user(app, SessionFactory, username: str = "test-user", plan: str = "pro", admin: bool = False) -> int:
    db = SessionFactory()
    user = User(username=username, password_hash="x", is_admin=admin, plan=plan, email=f"{username}@teste.com")
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    def current_user(db: Session = Depends(get_db)) -> User:
        return db.get(User, user_id)

    app.dependency_overrides[get_current_user] = current_user
    return user_id
