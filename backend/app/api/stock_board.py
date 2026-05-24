import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user
from app.schemas.market import MarketDailyResponse
from app.schemas.stock_board import (
    MarketSentimentRequest,
    MarketSentimentResponse,
    StockScanRequest,
    StockScanResponse,
    ShortTermSignalRequest,
    ShortTermSignalResponse,
    SwingSignalRequest,
    SwingSignalResponse,
)
from app.services.data.baostock import get_daily_data
from app.services.strategy.short_term import evaluate_market_sentiment, evaluate_short_term_signal
from app.services.strategy.swing import evaluate_swing_signal

router = APIRouter()


@router.get("/daily", response_model=MarketDailyResponse)
async def daily(
    symbol: str,
    start_date: str,
    end_date: str,
    user=Depends(get_current_user),
) -> MarketDailyResponse:
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    data = await get_daily_data(symbol=symbol, start_date=start_date, end_date=end_date)
    return MarketDailyResponse(symbol=symbol, data=data)


@router.post("/swing/signal", response_model=SwingSignalResponse)
async def swing_signal(
    payload: SwingSignalRequest,
    user=Depends(get_current_user),
) -> SwingSignalResponse:
    data = [item.model_dump() for item in payload.data]
    result = evaluate_swing_signal(data=data, meta=payload.meta.model_dump())
    return SwingSignalResponse(**result)


@router.post("/short-term/signal", response_model=ShortTermSignalResponse)
async def short_term_signal(
    payload: ShortTermSignalRequest,
    user=Depends(get_current_user),
) -> ShortTermSignalResponse:
    result = evaluate_short_term_signal(
        context=payload.context.model_dump(),
        meta=payload.meta.model_dump(),
    )
    return ShortTermSignalResponse(**result)


@router.post("/sentiment", response_model=MarketSentimentResponse)
async def sentiment(
    payload: MarketSentimentRequest,
    user=Depends(get_current_user),
) -> MarketSentimentResponse:
    result = evaluate_market_sentiment(payload.model_dump())
    return MarketSentimentResponse(**result)


@router.post("/scan", response_model=StockScanResponse)
async def scan(
    payload: StockScanRequest,
    user=Depends(get_current_user),
) -> StockScanResponse:
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="symbols is required")

    mode = payload.mode.lower()
    if mode not in {"swing", "short_term"}:
        raise HTTPException(status_code=400, detail="mode must be swing or short_term")
    meta_map = payload.meta_map or {}
    context_map = payload.short_term_context_map or {}
    semaphore = asyncio.Semaphore(payload.max_concurrency)

    async def _scan_symbol(symbol: str) -> dict:
        async with semaphore:
            if mode == "short_term":
                context = context_map.get(symbol)
                if context is None:
                    raise HTTPException(status_code=400, detail=f"missing short_term_context for {symbol}")
                meta = meta_map.get(symbol)
                meta_payload = meta.model_dump() if meta else {}
                result = evaluate_short_term_signal(
                    context=context.model_dump(),
                    meta=meta_payload,
                )
                return {"symbol": symbol, **result}

            data = await get_daily_data(
                symbol=symbol,
                start_date=payload.start_date,
                end_date=payload.end_date,
            )
            meta = meta_map.get(symbol)
            meta_payload = meta.model_dump() if meta else {}
            result = evaluate_swing_signal(
                data=data,
                meta=meta_payload,
            )
            return {"symbol": symbol, **result}

    results = await asyncio.gather(*[_scan_symbol(symbol) for symbol in payload.symbols])
    return StockScanResponse(results=results)
