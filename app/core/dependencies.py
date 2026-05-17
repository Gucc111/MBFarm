"""FastAPI dependencies: database session, auth, and service factories."""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="session_token"),
) -> "User":  # type: ignore[name-defined]
    """FastAPI dependency: returns the authenticated User or raises 401."""
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
            headers={"WWW-Authenticate": "Cookie"},
        )

    from app.models.user import User
    from app.repositories.user_repo import SessionRepository, UserRepository

    session_repo = SessionRepository(db)
    session = await session_repo.get_by_token(session_token)
    if not session or session.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已过期或无效",
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(session.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user


# ── Repository factories ─────────────────────────────────────────────────────

def get_user_repo(db: AsyncSession = Depends(get_db)) -> "UserRepository":  # type: ignore[name-defined]
    """Dependency: UserRepository bound to the current db session."""
    from app.repositories.user_repo import UserRepository
    return UserRepository(db)


def get_session_repo(db: AsyncSession = Depends(get_db)) -> "SessionRepository":  # type: ignore[name-defined]
    """Dependency: SessionRepository bound to the current db session."""
    from app.repositories.user_repo import SessionRepository
    return SessionRepository(db)


def get_farm_repo(db: AsyncSession = Depends(get_db)) -> "FarmRepo":  # type: ignore[name-defined]
    """Dependency: FarmRepo bound to the current db session."""
    from app.repositories.farm_repo import FarmRepo
    return FarmRepo(db)


# ── Service factories ────────────────────────────────────────────────────────

def get_auth_service(
    user_repo: "UserRepository" = Depends(get_user_repo),  # type: ignore[name-defined]
    session_repo: "SessionRepository" = Depends(get_session_repo),  # type: ignore[name-defined]
    db: AsyncSession = Depends(get_db),
) -> "AuthService":  # type: ignore[name-defined]
    """Dependency: AuthService wired with repositories and db session."""
    from app.services.auth_service import AuthService
    return AuthService(db, user_repo, session_repo)


def get_social_repo(db: AsyncSession = Depends(get_db)) -> "SocialRepo":  # type: ignore[name-defined]
    """Dependency: SocialRepo bound to the current db session."""
    from app.repositories.social_repo import SocialRepo
    return SocialRepo(db)


def get_friend_service(db: AsyncSession = Depends(get_db)) -> "FriendService":  # type: ignore[name-defined]
    """Dependency: FriendService bound to the current db session."""
    from app.services.friend import FriendService
    return FriendService(db)
