"""
Live Tick Consumer: Queue-based WebSocket integration for Zerodha Kite Ticker.
Decouples tick ingestion from downstream processing.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timezone
import threading
import queue

logger = logging.getLogger("live_ticks")


class TickBuffer:
    """Thread-safe tick buffer with candle resampling."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue(maxsize=10000)
        self._subscribers: List[Callable] = []
        self._candle_builders: Dict[str, Dict[str, Any]] = {}

    def push_tick(self, tick: Dict[str, Any]):
        """Push a tick into the buffer (called from WebSocket thread)."""
        try:
            self._queue.put_nowait(tick)
        except queue.Full:
            self._queue.get()  # Drop oldest
            self._queue.put_nowait(tick)

    def get_tick(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Get a tick from the buffer (called from processing thread)."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_batch(self, max_items: int = 100) -> List[Dict[str, Any]]:
        """Get a batch of ticks."""
        batch = []
        for _ in range(max_items):
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    @property
    def size(self) -> int:
        return self._queue.qsize()

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    def build_candle(self, symbol: str, tick: Dict[str, Any], interval_seconds: int = 60) -> Optional[Dict[str, Any]]:
        """Resample ticks into candles. Returns completed candle or None."""
        price = tick.get("last_price", 0)
        volume = tick.get("volume", 0)
        timestamp = tick.get("timestamp", datetime.now(timezone.utc).isoformat())

        key = f"{symbol}:{interval_seconds}"
        if key not in self._candle_builders:
            self._candle_builders[key] = {
                "symbol": symbol, "open": price, "high": price, "low": price,
                "close": price, "volume": volume, "tick_count": 1,
                "start_time": timestamp, "interval": interval_seconds,
            }
            return None

        builder = self._candle_builders[key]
        builder["high"] = max(builder["high"], price)
        builder["low"] = min(builder["low"], price)
        builder["close"] = price
        builder["volume"] += volume
        builder["tick_count"] += 1

        # Check if interval elapsed
        try:
            start = datetime.fromisoformat(builder["start_time"].replace("Z", "+00:00"))
            now = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if isinstance(timestamp, str) else datetime.now(timezone.utc)
            if (now - start).total_seconds() >= interval_seconds:
                candle = {
                    "symbol": symbol,
                    "timestamp": builder["start_time"],
                    "open": builder["open"],
                    "high": builder["high"],
                    "low": builder["low"],
                    "close": builder["close"],
                    "volume": builder["volume"],
                    "tick_count": builder["tick_count"],
                }
                # Reset
                self._candle_builders[key] = {
                    "symbol": symbol, "open": price, "high": price, "low": price,
                    "close": price, "volume": 0, "tick_count": 0,
                    "start_time": timestamp, "interval": interval_seconds,
                }
                return candle
        except (ValueError, TypeError):
            pass
        return None


class LiveTickManager:
    """
    Manages WebSocket connections to Zerodha Kite Ticker.
    Uses queue-based design: WebSocket thread pushes ticks, processing thread consumes.
    """

    def __init__(self):
        self.tick_buffer = TickBuffer()
        self._running = False
        self._subscribed_tokens: List[int] = []
        self._ws_thread: Optional[threading.Thread] = None
        self._kws = None

    def start(self, api_key: str, access_token: str, instrument_tokens: List[int]):
        """Start WebSocket connection in a background thread."""
        if self._running:
            logger.warning("Tick manager already running")
            return

        self._subscribed_tokens = instrument_tokens
        self._running = True

        def _ws_worker():
            try:
                from kiteconnect import KiteTicker
                kws = KiteTicker(api_key, access_token)
                self._kws = kws

                def on_ticks(ws, ticks):
                    for tick in ticks:
                        self.tick_buffer.push_tick({
                            "instrument_token": tick.get("instrument_token"),
                            "last_price": tick.get("last_price", 0),
                            "volume": tick.get("volume_traded", 0),
                            "open": tick.get("ohlc", {}).get("open", 0),
                            "high": tick.get("ohlc", {}).get("high", 0),
                            "low": tick.get("ohlc", {}).get("low", 0),
                            "close": tick.get("ohlc", {}).get("close", 0),
                            "bid": tick.get("depth", {}).get("buy", [{}])[0].get("price", 0),
                            "ask": tick.get("depth", {}).get("sell", [{}])[0].get("price", 0),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                def on_connect(ws, response):
                    logger.info(f"Ticker connected, subscribing to {len(instrument_tokens)} tokens")
                    ws.subscribe(instrument_tokens)
                    ws.set_mode(ws.MODE_FULL, instrument_tokens)

                def on_close(ws, code, reason):
                    logger.warning(f"Ticker closed: {code} {reason}")

                def on_error(ws, code, reason):
                    logger.error(f"Ticker error: {code} {reason}")

                def on_reconnect(ws, attempts_count):
                    logger.info(f"Ticker reconnecting: attempt {attempts_count}")

                kws.on_ticks = on_ticks
                kws.on_connect = on_connect
                kws.on_close = on_close
                kws.on_error = on_error
                kws.on_reconnect = on_reconnect
                kws.connect(threaded=False)
            except ImportError:
                logger.error("kiteconnect not installed. Live ticks unavailable.")
            except Exception as e:
                logger.error(f"Ticker thread error: {e}")
            finally:
                self._running = False

        self._ws_thread = threading.Thread(target=_ws_worker, daemon=True, name="kite-ticker")
        self._ws_thread.start()
        logger.info(f"Tick manager started for {len(instrument_tokens)} instruments")

    def stop(self):
        """Stop WebSocket connection."""
        self._running = False
        if self._kws:
            try:
                self._kws.close()
            except Exception:
                pass
        self._kws = None
        logger.info("Tick manager stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def buffer_size(self) -> int:
        return self.tick_buffer.size

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "subscribed_tokens": len(self._subscribed_tokens),
            "buffer_size": self.tick_buffer.size,
        }


# Global tick manager
live_tick_manager = LiveTickManager()
