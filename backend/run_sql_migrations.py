import asyncio
from pathlib import Path

from sqlalchemy import text

from app.core.database import engine


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    in_single_quote = False
    prev = ""
    for ch in sql:
        if ch == "'" and prev != "\\":
            in_single_quote = not in_single_quote
        if ch == ";" and not in_single_quote:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
        prev = ch
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


async def apply_migrations() -> None:
    root = Path(__file__).resolve().parent.parent
    migrations_dir = root / "supabase" / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("No SQL migration files found.")
        return

    async with engine.begin() as conn:
        for file in files:
            sql = file.read_text(encoding="utf-8")
            statements = _split_sql_statements(sql)
            for stmt in statements:
                await conn.execute(text(stmt))
            print(f"Applied: {file.name}")

    await engine.dispose()
    print("All migrations applied.")


if __name__ == "__main__":
    asyncio.run(apply_migrations())
