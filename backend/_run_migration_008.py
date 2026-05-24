import asyncio
from sqlalchemy import text
from app.core.database import engine


async def run():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS signal_type VARCHAR(32)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_scan_results_signal_type ON scan_results (signal_type) WHERE signal_type IS NOT NULL"
            )
        )
        print("Migration 000008 applied")
    await engine.dispose()


asyncio.run(run())
