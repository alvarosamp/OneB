"""Promove um usuario existente a administrador.

Uso: python -m scripts.promote_admin <username>

Cadastro público (POST /api/auth/cadastro) nunca concede is_admin — o primeiro
admin vem de ADMIN_BOOTSTRAP_USERNAME/PASSWORD no .env (ver app/config.py e
app.auth.ensure_admin_bootstrap). Depois do bootstrap inicial, este script é o
único jeito de promover outros usuarios a admin.
"""
from __future__ import annotations

import sys

from app.db import SessionLocal
from app.models import User


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python -m scripts.promote_admin <username>")
        return 1

    username_norm = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username_norm).first()
        if user is None:
            print(f"Usuario '{username_norm}' nao encontrado.")
            return 1
        if user.is_admin:
            print(f"Usuario '{username_norm}' ja e admin.")
            return 0
        user.is_admin = True
        db.commit()
        print(f"Usuario '{username_norm}' promovido a admin.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
