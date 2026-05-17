"""Authentication API routes."""

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import clear_session_cookie, set_session_cookie
from app.repositories.user_repo import SessionRepository, UserRepository
from app.schemas.user import UserCreate, UserLogin, LoginResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


def _get_service(db: AsyncSession) -> AuthService:
    return AuthService(db, UserRepository(db), SessionRepository(db))


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    service = _get_service(db)
    user = await service.register(user_data.username, user_data.password)
    return user


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="用户登录",
)
async def login(
    login_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    service = _get_service(db)
    session = await service.login(login_data.username, login_data.password)
    set_session_cookie(response, session.token)
    return LoginResponse(
        user=UserResponse.model_validate(session.user),
        message="登录成功",
    )


@router.post(
    "/logout",
    summary="用户登出",
)
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias="session_token"),
    db: AsyncSession = Depends(get_db),
):
    if session_token:
        session_repo = SessionRepository(db)
        session = await session_repo.get_by_token(session_token)
        if session:
            await session_repo.delete(session)

    resp = JSONResponse(content={"message": "已登出"})
    clear_session_cookie(resp)
    return resp


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
)
async def get_me(
    session_token: str | None = Cookie(default=None, alias="session_token"),
    db: AsyncSession = Depends(get_db),
):
    if not session_token:
        raise UnauthorizedError("未登录")

    service = _get_service(db)
    user = await service.get_current_user(session_token)
    return user
