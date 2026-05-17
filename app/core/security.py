"""Security utilities: password hashing and session cookie helpers."""

import uuid

from fastapi import Response
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """将明文密码哈希为 bcrypt 字符串。"""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配已存储的哈希值。"""
    return pwd_context.verify(plain_password, hashed_password)


# ── Session token helpers ────────────────────────────────────────────────────

def generate_session_token() -> str:
    """使用 UUID4 生成无状态但可撤销的 Session Token。"""
    return str(uuid.uuid4())


# ── Cookie helpers ───────────────────────────────────────────────────────────

def set_session_cookie(response: Response, token: str, expires_days: int = 7) -> None:
    """设置 Session Cookie。"""
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=expires_days * 86400,
        httponly=True,
        samesite="lax",
        path="/",
        secure=False,
    )


def clear_session_cookie(response: Response) -> None:
    """清除 Session Cookie。"""
    response.delete_cookie(key="session_token", path="/")
