import httpx
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        
    async def send_slack_alert(self, message: str, level: str = "info"):
        """Send a message to Slack via Incoming Webhook"""
        if not self.webhook_url:
            logger.warning("Slack notification skipped: SLACK_WEBHOOK_URL not set")
            return False
            
        colors = {
            "info": "#36a64f",    # Green
            "warning": "#ecb22e", # Yellow/Orange
            "error": "#e01e5a"     # Red/Pink
        }
        
        payload = {
            "attachments": [
                {
                    "fallback": message,
                    "color": colors.get(level, colors["info"]),
                    "title": "Dumpty Backup Alert",
                    "text": message,
                    "footer": "Dumpty Backup System",
                    "ts": int(__import__('time').time())
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                if response.status_code == 200:
                    logger.info("Slack notification sent successfully")
                    return True
                else:
                    logger.error(f"Slack API error: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

notification_service = NotificationService()
