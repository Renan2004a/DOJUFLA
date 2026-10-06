"""Usuário autenticado e hierarquia de cargos.

Níveis: usuario < moderador < admin < super_admin.
Cada usuário só gerencia quem está estritamente abaixo dele.
"""
from flask_login import UserMixin

from database import db

ROLE_LEVELS = {
    "usuario": 1,
    "moderador": 2,
    "admin": 3,
    "super_admin": 4,
}


class User(UserMixin):
    def __init__(self, id, username, role="usuario", llm_preference="ollama"):
        self.id = id
        self.username = username
        self.role = role if role in ROLE_LEVELS else "usuario"
        self.llm_preference = llm_preference

    def level(self) -> int:
        return ROLE_LEVELS.get(self.role, 1)

    def is_moderator_or_above(self) -> bool:
        return self.level() >= ROLE_LEVELS["moderador"]

    def is_admin_or_above(self) -> bool:
        return self.level() >= ROLE_LEVELS["admin"]

    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    def can_manage(self, other_role: str) -> bool:
        """True se este usuário pode gerenciar alguém com ``other_role``."""
        return self.level() > ROLE_LEVELS.get(other_role, 0)


def user_from_row(row) -> User:
    keys = row.keys()
    return User(
        id=row["id"],
        username=row["username"],
        role=row["role"] if "role" in keys else "usuario",
        llm_preference=row["llm_preference"] if "llm_preference" in keys else "ollama",
    )


def get_user(user_id):
    """Callback do flask-login: carrega o usuário pelo id."""
    with db() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    return user_from_row(row) if row else None
