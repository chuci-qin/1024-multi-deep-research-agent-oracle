"""
Crypto Price Tools — Yahoo Finance, Binance & CoinGecko for precise price data.

Provides two tools for Gemini function calling:
  - get_crypto_price_at_timestamp: Historical candle data
  - get_crypto_price_current: Real-time ticker price

Data source priority: Yahoo Finance > Binance > CoinGecko
All are free — no API key required.
"""

import asyncio
import urllib.request
import json
from datetime import datetime, timezone, timedelta

import structlog

from oracle.tools.base import BaseTool

logger = structlog.get_logger()

BINANCE_BASE = "https://api.binance.com"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Yahoo Finance symbol mapping
_YAHOO_SYMBOLS = {
    "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD", "SOLUSDT": "SOL-USD",
    "BNBUSDT": "BNB-USD", "XRPUSDT": "XRP-USD", "ADAUSDT": "ADA-USD",
    "DOGEUSDT": "DOGE-USD", "AVAXUSDT": "AVAX-USD", "DOTUSDT": "DOT-USD",
    "MATICUSDT": "MATIC-USD", "LINKUSDT": "LINK-USD", "UNIUSDT": "UNI-USD",
    "ATOMUSDT": "ATOM-USD", "LTCUSDT": "LTC-USD", "FILUSDT": "FIL-USD",
}


class CryptoPriceAtTimestamp(BaseTool):
    """Get historical crypto price at a specific timestamp."""

    name = "get_crypto_price_at_timestamp"
    description = (
        "Get the historical cryptocurrency price at a specific timestamp. "
        "Returns OHLCV candle data (open/high/low/close/volume). "
        "Use this for prediction markets that resolve at a specific time. "
        "The symbol should be like BTCUSDT, ETHUSDT, SOLUSDT."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading pair symbol, e.g. BTCUSDT, ETHUSDT, SOLUSDT",
            },
            "timestamp": {
                "type": "string",
                "description": "ISO 8601 timestamp for the price lookup, e.g. 2026-02-19T00:26:51Z",
            },
        },
        "required": ["symbol", "timestamp"],
    }

    async def execute(self, **kwargs) -> dict:
        symbol = kwargs.get("symbol", "BTCUSDT").upper()
        ts_str = kwargs.get("timestamp", "")

        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return {"error": f"Invalid timestamp format: {ts_str}"}

        # Priority 1: Yahoo Finance (most reliable, no geo-blocking)
        result = await self._query_yahoo(symbol, dt)
        if result and "error" not in result:
            return result

        # Priority 2: Binance (best granularity but geo-blocked in some regions)
        result = await self._query_binance(symbol, dt)
        if result and "error" not in result:
            return result

        # Priority 3: CoinGecko (always available, lower precision)
        return await self._query_coingecko(symbol, dt)

    async def _query_yahoo(self, symbol: str, dt: datetime) -> dict | None:
        yahoo_sym = _YAHOO_SYMBOLS.get(symbol, symbol.replace("USDT", "-USD"))
        try:
            import yfinance as yf
            def _fetch():
                ticker = yf.Ticker(yahoo_sym)
                start = dt - timedelta(minutes=5)
                end = dt + timedelta(minutes=5)
                df = ticker.history(start=start, end=end, interval="1m")
                if df.empty:
                    # Try wider range with 5m interval
                    start = dt - timedelta(hours=1)
                    end = dt + timedelta(hours=1)
                    df = ticker.history(start=start, end=end, interval="5m")
                return df

            df = await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=15.0)
            if df.empty:
                logger.warning("Yahoo Finance returned empty data", symbol=yahoo_sym)
                return None

            # Find the candle closest to the target timestamp
            target_ts = dt.timestamp()
            df_ts = df.index.map(lambda x: x.timestamp())
            closest_idx = (abs(df_ts - target_ts)).argmin()
            row = df.iloc[closest_idx]
            candle_time = df.index[closest_idx]

            result = {
                "source": "yahoo_finance",
                "symbol": yahoo_sym,
                "interval": "1m",
                "candle_time": str(candle_time),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": round(float(row["Volume"]), 2),
                "time_diff_seconds": abs(candle_time.timestamp() - target_ts),
            }
            logger.info("Yahoo Finance data fetched", symbol=yahoo_sym, close=result["close"], time=result["candle_time"])
            return result
        except Exception as e:
            logger.warning("Yahoo Finance fetch failed", symbol=yahoo_sym, error=str(e))
            return None

    async def _query_binance(self, symbol: str, dt: datetime) -> dict | None:
        ms = int(dt.timestamp() * 1000)
        url = f"{BINANCE_BASE}/api/v3/klines?symbol={symbol}&interval=1m&startTime={ms}&limit=1"
        try:
            data = await _fetch_json(url)
            if not data or not isinstance(data, list) or len(data) == 0:
                return None
            candle = data[0]
            open_time = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
            result = {
                "source": "binance",
                "symbol": symbol,
                "interval": "1m",
                "candle_time": open_time.isoformat(),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
            }
            logger.info("Binance kline fetched", symbol=symbol, close=result["close"])
            return result
        except Exception as e:
            logger.warning("Binance kline failed", symbol=symbol, error=str(e))
            return None

    async def _query_coingecko(self, symbol: str, dt: datetime) -> dict:
        coin_id = _symbol_to_coingecko_id(symbol)
        start = int(dt.timestamp()) - 300
        end = int(dt.timestamp()) + 300
        url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart/range?vs_currency=usd&from={start}&to={end}"
        try:
            data = await _fetch_json(url)
            prices = data.get("prices", [])
            if prices:
                closest = min(prices, key=lambda p: abs(p[0] / 1000 - dt.timestamp()))
                ts = datetime.fromtimestamp(closest[0] / 1000, tz=timezone.utc)
                return {
                    "source": "coingecko",
                    "symbol": symbol,
                    "price": closest[1],
                    "candle_time": ts.isoformat(),
                    "note": "CoinGecko fallback — lower time precision",
                }
        except Exception as e:
            logger.warning("CoinGecko failed", error=str(e))
        return {"error": f"All sources failed for {symbol} at {dt.isoformat()}"}


class CryptoPriceCurrent(BaseTool):
    """Get the current real-time cryptocurrency price."""

    name = "get_crypto_price_current"
    description = (
        "Get the current real-time cryptocurrency price. "
        "Returns the latest ticker price. "
        "Use this when you need the 'current' or 'latest' price, not a historical one. "
        "The symbol should be like BTCUSDT, ETHUSDT, SOLUSDT."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading pair symbol, e.g. BTCUSDT, ETHUSDT, SOLUSDT",
            },
        },
        "required": ["symbol"],
    }

    async def execute(self, **kwargs) -> dict:
        symbol = kwargs.get("symbol", "BTCUSDT").upper()
        now = datetime.now(tz=timezone.utc)

        # Priority 1: Yahoo Finance
        yahoo_sym = _YAHOO_SYMBOLS.get(symbol, symbol.replace("USDT", "-USD"))
        try:
            import yfinance as yf
            def _fetch():
                ticker = yf.Ticker(yahoo_sym)
                info = ticker.fast_info
                return float(info.last_price)
            price = await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=15.0)
            logger.info("Yahoo Finance current price", symbol=yahoo_sym, price=price)
            return {"source": "yahoo_finance", "symbol": yahoo_sym, "price": round(price, 2), "timestamp": now.isoformat()}
        except Exception as e:
            logger.warning("Yahoo current price failed", error=str(e))

        # Priority 2: Binance
        try:
            data = await _fetch_json(f"{BINANCE_BASE}/api/v3/ticker/price?symbol={symbol}")
            price = float(data.get("price", 0))
            logger.info("Binance current price", symbol=symbol, price=price)
            return {"source": "binance", "symbol": symbol, "price": price, "timestamp": now.isoformat()}
        except Exception as e:
            logger.warning("Binance ticker failed", error=str(e))

        # Priority 3: CoinGecko
        coin_id = _symbol_to_coingecko_id(symbol)
        try:
            data = await _fetch_json(f"{COINGECKO_BASE}/simple/price?ids={coin_id}&vs_currencies=usd")
            price = float(data.get(coin_id, {}).get("usd", 0))
            return {"source": "coingecko", "symbol": symbol, "price": price, "timestamp": now.isoformat()}
        except Exception as e:
            return {"error": f"All sources failed for {symbol}: {e}"}


# --- Helpers ---

async def _fetch_json(url: str, timeout: int = 10) -> dict | list:
    """Fetch JSON from a URL using urllib (no external deps)."""
    def _do_fetch():
        req = urllib.request.Request(url, headers={"User-Agent": "1024-Oracle/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    return await asyncio.to_thread(_do_fetch)


def _symbol_to_coingecko_id(symbol: str) -> str:
    """Convert trading pair symbol to CoinGecko coin ID."""
    mapping = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
        "DOGE": "dogecoin", "AVAX": "avalanche-2", "DOT": "polkadot",
        "MATIC": "matic-network", "LINK": "chainlink", "UNI": "uniswap",
        "ATOM": "cosmos", "LTC": "litecoin", "FIL": "filecoin",
    }
    base = symbol.replace("USDT", "").replace("USDC", "").replace("USD", "").replace("-", "")
    return mapping.get(base, base.lower())
