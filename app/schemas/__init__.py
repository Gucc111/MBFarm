"""Pydantic v2 schemas for all endpoints."""

from app.schemas.farm import (
    FarmInfoResponse,
    HarvestResult,
    PlantRequest,
    PlotResponse,
    UnlockResult,
    WaterRequest,
    WaterResult,
)
from app.schemas.item import (
    InventoryItem,
    InventoryResponse,
)
from app.schemas.shop import (
    BuySeedRequest,
    BuySeedResponse,
    ShopItem,
    ShopListResponse,
)
from app.schemas.user import UserCreate, UserLogin, LoginResponse, UserResponse
from app.schemas.social import (
    ActionResponse,
    AddFriendRequest,
    BlockUserRequest,
    FriendListResponse,
    FriendStats,
    FriendshipResponse,
    PendingRequestItem,
    PendingRequestsResponse,
    RespondFriendRequest,
    UserBrief,
)

from app.schemas.steal import (
    StealHistoryResponse,
    StealRecord,
    StealRequest,
    StealResult,
)

__all__ = [
    # Farm
    "FarmInfoResponse",
    "HarvestResult",
    "PlantRequest",
    "PlotResponse",
    "UnlockResult",
    "WaterRequest",
    "WaterResult",
    # Item / Inventory
    "InventoryItem",
    "InventoryResponse",
    # Shop
    "BuySeedRequest",
    "BuySeedResponse",
    "ShopItem",
    "ShopListResponse",
    # User / Auth
    "UserCreate",
    "UserLogin",
    "LoginResponse",
    "UserResponse",
    # Social
    "ActionResponse",
    "AddFriendRequest",
    "BlockUserRequest",
    "FriendListResponse",
    "FriendStats",
    "FriendshipResponse",
    "PendingRequestItem",
    "PendingRequestsResponse",
    "RespondFriendRequest",
    "UserBrief",
    # Steal
    "StealHistoryResponse",
    "StealRecord",
    "StealRequest",
    "StealResult",
]
