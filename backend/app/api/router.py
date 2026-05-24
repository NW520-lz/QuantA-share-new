from fastapi import APIRouter

from app.api import (
    ai_chat,
    auth,
    billing,
    market,
    portfolio,
    review,
    skills,
    stock_board,
    system_settings,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(ai_chat.router, prefix="/ai", tags=["ai"])
api_router.include_router(
    stock_board.router, prefix="/stock-board", tags=["stock-board"]
)
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(review.router, prefix="/review", tags=["review"])
api_router.include_router(system_settings.router, prefix="/system", tags=["system"])
api_router.include_router(skills.router, prefix="", tags=["skills"])
