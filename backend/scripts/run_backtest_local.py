import asyncio
import sys
import os

# Ensure backend package is importable
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from app.services.strategy.backtest import run_swing_backtest

async def main():
    symbol = "sh.600519"  # 茅台示例，可修改
    start_date = "2024-01-01"
    end_date = "2026-05-20"
    print(f"Running backtest for {symbol} {start_date}~{end_date} ...")
    result = await run_swing_backtest(symbol, start_date, end_date)
    print("Result:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
