"""Authentication business logic."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import INIT_USER
from app.core.exceptions import (
    AppValidationError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import hash_password, verify_password
from app.models.session import Session as SessionModel
from app.models.user import User
from app.repositories.user_repo import SessionRepository, UserRepository


class AuthService:
    """认证服务：处理注册、登录、登出等业务逻辑。"""

    def __init__(
        self,
        db: AsyncSession,
        user_repo: UserRepository,
        session_repo: SessionRepository,
    ):
        self.db = db
        self.user_repo = user_repo
        self.session_repo = session_repo

    async def register(self, username: str, password: str) -> User:
        """
        注册新用户。

        业务规则：
        1. 用户名不得重复
        2. 密码长度至少 6 个字符
        3. 密码需经 bcrypt 哈希后存储

        Args:
            username: 用户名（32 字符以内，由 Route 层 Pydantic 校验）
            password: 明文密码

        Returns:
            创建成功的 User 对象

        Raises:
            ConflictError: 用户名已存在
            AppValidationError: 密码强度不达标
        """
        # 1. 用户名唯一性校验
        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise ConflictError("用户名已存在")

        # 2. 密码强度校验（Schema 层已校验最小长度 6，此处为防御性检查）
        if len(password) < 6:
            raise AppValidationError("密码长度至少 6 个字符")

        # 3. 密码哈希 + 创建用户
        password_hash = hash_password(password)
        user = await self.user_repo.create({
            "username": username,
            "password_hash": password_hash,
            "coins": INIT_USER.gold,
            "xp": INIT_USER.xp,
            "level": INIT_USER.level,
            "stamina": INIT_USER.stamina,
        })

        return user

    async def login(self, username: str, password: str) -> SessionModel:
        """
        用户登录。

        业务规则：
        1. 用户必须存在
        2. 密码必须匹配
        3. 登录成功后创建新 Session（默认 7 天过期）
        4. 自动清理该用户的所有旧 Session（单设备限制）

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            创建成功的 Session 对象

        Raises:
            NotFoundError: 用户不存在
            UnauthorizedError: 密码错误
        """
        # 1. 查找用户
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise NotFoundError("用户不存在")

        # 2. 密码验证
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("用户名或密码错误")

        # 3. 清理该用户的所有旧 Session（单设备限制）
        await self.session_repo.delete_all_by_user_id(user.id)

        # 4. 生成 Token 并创建新 Session
        token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        session = await self.session_repo.create(user.id, token, expires_at)
        return session

    async def logout(self, session: SessionModel) -> None:
        """
        用户登出。

        Args:
            session: 当前 Session 对象
        """
        await self.session_repo.delete(session)

    async def get_current_user(self, session_token: str) -> User:
        """从 Cookie session_token 解析当前认证用户。"""
        session = await self.session_repo.get_by_token(session_token)
        if not session or session.is_expired():
            raise UnauthorizedError("会话已过期或无效")

        user = await self.user_repo.get_by_id(session.user_id)
        if not user:
            raise UnauthorizedError("用户不存在")

        return user
