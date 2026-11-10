"""Redefine a senha de um usuario existente, direto no banco.

Uso: python -m scripts.reset_password <username>

Existe para o caso em que nao ha admin disponivel para usar
`POST /api/auth/usuarios/{id}/senha` -- por exemplo, quando o proprio admin perdeu a
senha. Nao apaga nem recria a conta: o id do usuario e referenciado por watchlist,
posicoes, alertas e historico, entao recriar a identidade descartaria esse historico.

Todas as sessoes ativas do usuario sao revogadas junto com a troca.
"""
from __future__ import annotations

import getpass
import sys
from datetime import datetime, timezone

from app.auth import hash_password
from app.db import SessionLocal
from app.models import RefreshToken, User


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python -m scripts.reset_password <username>")
        return 1

    username_norm = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username_norm).first()
        if user is None:
            print(f"Usuario '{username_norm}' nao encontrado.")
            return 1

        password = getpass.getpass("Nova senha: ")
        if len(password) < 8:
            print("A senha precisa ter pelo menos 8 caracteres.")
            return 1
        if password != getpass.getpass("Confirme a nova senha: "):
            print("As senhas nao coincidem.")
            return 1

        user.password_hash = hash_password(password)
        revoked = (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .update({RefreshToken.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
        )
        db.commit()
        print(f"Senha de '{username_norm}' redefinida. Sessoes revogadas: {revoked}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
