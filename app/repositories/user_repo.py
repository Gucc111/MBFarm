"""Repository layer for User and Session models."""

from datetime import datetime
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session as SessionModel
from app.models.user import User


class UserRepository:
    """用户数据访问层"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        user = User(**user_data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User, updates: dict) -> User:
        for key, value in updates.items():
            setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user


class SessionRepository:
    """会话数据访问层"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_token(self, token: str) -> SessionModel | None:
        stmt = select(SessionModel).where(SessionModel.token == token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, token: str, expires_at: datetime) -> SessionModel:
        session = SessionModel(user_id=user_id, token=token, expires_at=expires_at)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete(self, session: SessionModel) -> None:
        await self.db.delete(session)
        await self.db.commit()

    async def delete_all_by_user_id(self, user_id: int) -> None:
        stmt = delete(SessionModel).where(SessionModel.user_id == user_id)
        await self.db.execute(stmt)
        await self.db.commit()
