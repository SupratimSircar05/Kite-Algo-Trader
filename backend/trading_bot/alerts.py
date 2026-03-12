"""
Alert System: Telegram + Webhook notifications for trading events.
Functional without credentials — silently skips when unconfigured.
"""
import logging
import asyncio
from typing import Optional, Dict, Any
import json

logger = logging.getLogger("alerts")

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class AlertManager:
    """Sends alerts via Telegram and/or Webhook. Non-blocking, fire-and-forget."""

    def __init__(self, telegram_token: str = "", telegram_chat_id: str = "", webhook_url: str = ""):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.webhook_url = webhook_url
        self._enabled = bool(telegram_token and telegram_chat_id) or bool(webhook_url)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    @property
    def webhook_configured(self) -> bool:
        return bool(self.webhook_url)

    def update_config(self, telegram_token: str = "", telegram_chat_id: str = "", webhook_url: str = ""):
        self.telegram_token = telegram_token or self.telegram_token
        self.telegram_chat_id = telegram_chat_id or self.telegram_chat_id
        self.webhook_url = webhook_url or self.webhook_url
        self._enabled = bool(self.telegram_token and self.telegram_chat_id) or bool(self.webhook_url)

    async def send_signal_alert(self, signal_data: Dict[str, Any]):
        """Send alert for a new trading signal."""
        emoji = "🟢" if signal_data.get("side") == "BUY" else "🔴"
        msg = (
            f"{emoji} *{signal_data.get('side', '')} Signal*\n"
            f"Symbol: `{signal_data.get('symbol', '')}`\n"
            f"Strategy: {signal_data.get('strategy_name', '')}\n"
            f"Price: {signal_data.get('price', 0):.2f}\n"
            f"Confidence: {signal_data.get('confidence', 0) * 100:.0f}%\n"
            f"SL: {signal_data.get('stop_loss', 0):.2f} | TP: {signal_data.get('take_profit', 0):.2f}\n"
            f"Reason: {signal_data.get('reason', '')}"
        )
        await self._send(msg, signal_data)

    async def send_trade_alert(self, trade_data: Dict[str, Any]):
        """Send alert for a completed trade."""
        pnl = trade_data.get("net_pnl", 0)
        emoji = "💰" if pnl >= 0 else "📉"
        msg = (
            f"{emoji} *Trade Closed*\n"
            f"Symbol: `{trade_data.get('symbol', '')}`\n"
            f"Side: {trade_data.get('side', '')}\n"
            f"Entry: {trade_data.get('entry_price', 0):.2f} → Exit: {trade_data.get('exit_price', 0):.2f}\n"
            f"P&L: {'+' if pnl >= 0 else ''}{pnl:.2f}\n"
            f"Fees: {trade_data.get('fees', 0):.2f}"
        )
        await self._send(msg, trade_data)

    async def send_kill_switch_alert(self, active: bool, reason: str = ""):
        """Send alert for kill switch state change."""
        msg = (
            f"🚨 *KILL SWITCH {'ACTIVATED' if active else 'DEACTIVATED'}*\n"
            f"Reason: {reason or 'Manual'}\n"
            f"All trading {'halted' if active else 'resumed'}."
        )
        await self._send(msg, {"type": "kill_switch", "active": active, "reason": reason})

    async def send_bot_status_alert(self, status: str, strategy: str = "", mode: str = ""):
        """Send alert for bot start/stop."""
        emoji = "▶️" if status == "started" else "⏹️"
        msg = (
            f"{emoji} *Bot {status.upper()}*\n"
            f"Mode: {mode.upper()}\n"
            f"Strategy: {strategy}"
        )
        await self._send(msg, {"type": "bot_status", "status": status})

    async def send_risk_alert(self, rule: str, details: str = ""):
        """Send alert when a risk rule triggers."""
        msg = f"⚠️ *Risk Alert*\nRule: {rule}\n{details}"
        await self._send(msg, {"type": "risk_alert", "rule": rule})

    async def send_custom(self, title: str, message: str, data: Optional[Dict] = None):
        """Send a custom alert."""
        msg = f"📢 *{title}*\n{message}"
        await self._send(msg, data or {})

    async def _send(self, text: str, payload: Dict[str, Any]):
        """Send to all configured channels."""
        tasks = []
        if self.telegram_configured:
            tasks.append(self._send_telegram(text))
        if self.webhook_configured:
            tasks.append(self._send_webhook(text, payload))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_telegram(self, text: str):
        """Send message via Telegram Bot API."""
        if not HAS_HTTPX:
            logger.warning("httpx not installed, skipping Telegram alert")
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Telegram alert sent")
                else:
                    logger.warning(f"Telegram alert failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Telegram send error: {e}")

    async def _send_webhook(self, text: str, payload: Dict[str, Any]):
        """Send to webhook URL."""
        if not HAS_HTTPX:
            logger.warning("httpx not installed, skipping webhook alert")
            return
        try:
            data = {"text": text, "data": payload}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=data)
                logger.info(f"Webhook alert sent: {resp.status_code}")
        except Exception as e:
            logger.error(f"Webhook send error: {e}")


# Global singleton
alert_manager = AlertManager()
