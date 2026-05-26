import asyncio
import os
import time
from typing import Any

_STOCK_LIST_CACHE: dict[str, Any] = {"data": None, "ts": 0}
_STOCK_LIST_TTL = 1800  # 30分钟缓存


async def get_daily_data(
    symbol: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    def _fetch() -> list[dict[str, Any]]:
        with _no_proxy():
            data = _fetch_akshare(symbol, start_date, end_date)
            if data:
                return data
        with _no_proxy():
            data = _fetch_baostock(symbol, start_date, end_date)
            return data

    return await asyncio.to_thread(_fetch)


async def get_batch_daily_data(
    symbols: list[str], start_date: str, end_date: str
) -> dict[str, list[dict[str, Any]]]:

    def _fetch_batch() -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {}
        with _no_proxy():
            for sym in symbols:
                try:
                    data = _fetch_akshare(sym, start_date, end_date)
                    if len(data) >= 30:
                        results[sym] = data
                except Exception:
                    pass
        return results

    return await asyncio.wait_for(asyncio.to_thread(_fetch_batch), timeout=300)


async def get_all_a_stocks() -> list[dict]:
    now = time.time()
    if _STOCK_LIST_CACHE["data"] is not None and now - _STOCK_LIST_CACHE["ts"] < _STOCK_LIST_TTL:
        return _STOCK_LIST_CACHE["data"]

    def _fetch() -> list[dict]:
        import akshare as ak

        with _no_proxy():
            try:
                spot_df = ak.stock_zh_a_spot_em()
            except Exception:
                spot_df = None

        extra: dict[str, dict] = {}
        if spot_df is not None and not spot_df.empty:
            for _, row in spot_df.iterrows():
                code = str(row.get("代码", "")).strip()
                if not code:
                    continue
                cap_raw = row.get("总市值")
                try:
                    cap_billion = float(cap_raw) / 1e8 if cap_raw else None
                except (TypeError, ValueError):
                    cap_billion = None
                industry = str(row.get("所属行业", "") or "").strip() or None
                extra[code] = {"market_cap_billion": cap_billion, "industry": industry}

        with _no_proxy():
            sh = ak.stock_info_sh_name_code(symbol="主板A股")
            sz = ak.stock_info_sz_name_code(symbol="A股列表")

        stocks = []
        if sh is not None and not sh.empty:
            for _, row in sh.iterrows():
                code = str(row.iloc[0])
                name = str(row.iloc[1])
                if not code or not name:
                    continue
                if "ST" in name or "退" in name:
                    continue
                info = extra.get(code, {})
                stocks.append(
                    {
                        "symbol": f"sh.{code}",
                        "name": name,
                        "code": code,
                        "market_cap_billion": info.get("market_cap_billion"),
                        "industry": info.get("industry"),
                    }
                )

        if sz is not None and not sz.empty:
            for _, row in sz.iterrows():
                code = str(row.iloc[1])
                name = str(row.iloc[2])
                if not code or not name or code == "nan" or name == "nan":
                    continue
                if "ST" in name or "退" in name:
                    continue
                info = extra.get(code, {})
                stocks.append(
                    {
                        "symbol": f"sz.{code}",
                        "name": name,
                        "code": code,
                        "market_cap_billion": info.get("market_cap_billion"),
                        "industry": info.get("industry"),
                    }
                )

        return stocks

    result = await asyncio.to_thread(_fetch)
    _STOCK_LIST_CACHE["data"] = result
    _STOCK_LIST_CACHE["ts"] = time.time()
    return result


def _fetch_akshare(symbol: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    try:
        import akshare as ak

        code = _extract_code(symbol)
        market = symbol[:2].lower()
        code_sina = f"{market}{code}"

        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        df = ak.stock_zh_a_daily(
            symbol=code_sina,
            start_date=start,
            end_date=end,
            adjust="qfq",
        )

        if df is None or df.empty:
            return []

        data: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            data.append(
                {
                    "date": str(row.get("date", "")),
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": float(row.get("volume", 0) or 0),
                    "amount": float(row.get("amount", 0) or 0),
                }
            )

        data.sort(key=lambda x: x["date"])
        return data
    except Exception:
        return []


def _fetch_baostock(
    symbol: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    try:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            bs.logout()
            return []

        fields = "date,open,high,low,close,volume,amount"
        rs = bs.query_history_k_data_plus(
            symbol,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2",
        )

        if rs.error_code != "0":
            bs.logout()
            return []

        data: list[dict[str, Any]] = []
        while rs.next():
            row = rs.get_row_data()
            data.append(
                {
                    "date": row[0],
                    "open": float(row[1]) if row[1] else 0.0,
                    "high": float(row[2]) if row[2] else 0.0,
                    "low": float(row[3]) if row[3] else 0.0,
                    "close": float(row[4]) if row[4] else 0.0,
                    "volume": float(row[5]) if row[5] else 0.0,
                    "amount": float(row[6]) if len(row) > 6 and row[6] else 0.0,
                }
            )

        bs.logout()
        return data
    except Exception:
        return []


def _market_prefix(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith(("0", "3", "2")):
        return "sz"
    if code.startswith(("4", "8")):
        return "bj"
    return ""


def _extract_code(symbol: str) -> str:
    s = symbol.strip().lower()
    for prefix in ("sh.", "sz.", "bj."):
        if s.startswith(prefix):
            return s[len(prefix) :]
    if s.endswith(".sh") or s.endswith(".sz") or s.endswith(".bj"):
        return s[:-3]
    return s


class _no_proxy:
    def __enter__(self):
        self._old = {}
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            if k in os.environ:
                self._old[k] = os.environ.pop(k)
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
        return self

    def __exit__(self, *args):
        for k, v in self._old.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        os.environ.pop("NO_PROXY", None)
        os.environ.pop("no_proxy", None)
