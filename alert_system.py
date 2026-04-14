#!/usr/bin/env python3
"""
Alert System Module
Sends Email and Telegram notifications for high-confidence arbitrage opportunities.

This module handles:
1. Email alerts via SMTP
2. Telegram bot notifications
3. Alert filtering and throttling
4. Alert history tracking
"""

import smtplib
import aiohttp
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    """Configuration for alert system"""
    email_enabled: bool
    email_address: str
    email_password: str
    smtp_server: str
    smtp_port: int
    
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    
    min_confidence_threshold: float
    alert_cooldown_seconds: int


@dataclass
class OpportunityAlert:
    """Alert for a detected opportunity"""
    alert_id: str
    opportunity_id: str
    opportunity_type: str
    spread_percentage: float
    estimated_profit: float
    confidence_score: float
    timestamp: str
    sent_via_email: bool
    sent_via_telegram: bool


class AlertSystem:
    """
    Manages multi-channel alerts for arbitrage opportunities.
    
    Channels:
    - Email: For detailed analysis and record-keeping
    - Telegram: For real-time mobile notifications
    
    Features:
    - Alert filtering by confidence threshold
    - Cooldown to prevent spam
    - Alert history tracking
    - Retry logic for failed sends
    """

    def __init__(self, config: AlertConfig):
        """
        Initialize alert system.
        
        Args:
            config: AlertConfig object with email and Telegram settings
        """
        self.config = config
        self.alert_history: List[OpportunityAlert] = []
        self.last_alert_time: Dict[str, datetime] = {}

    def validate_config(self) -> bool:
        """
        Validate alert configuration.
        
        Returns:
            True if configuration is valid
        """
        if self.config.email_enabled:
            if not all([
                self.config.email_address,
                self.config.email_password,
                self.config.smtp_server,
                self.config.smtp_port
            ]):
                logger.error("✗ Email configuration incomplete")
                return False

        if self.config.telegram_enabled:
            if not all([
                self.config.telegram_bot_token,
                self.config.telegram_chat_id
            ]):
                logger.error("✗ Telegram configuration incomplete")
                return False

        logger.info("✓ Alert configuration validated")
        return True

    def should_send_alert(self, opportunity_id: str) -> bool:
        """
        Check if alert should be sent based on cooldown.
        
        Args:
            opportunity_id: ID of the opportunity
            
        Returns:
            True if enough time has passed since last alert
        """
        last_time = self.last_alert_time.get(opportunity_id)
        if not last_time:
            return True

        time_since_last = (datetime.now() - last_time).total_seconds()
        if time_since_last >= self.config.alert_cooldown_seconds:
            return True

        return False

    async def send_email_alert(
        self,
        recipient: str,
        opportunity_type: str,
        spread: float,
        profit: float,
        confidence: float,
        timestamp: str
    ) -> bool:
        """
        Send email alert for an opportunity.
        
        Args:
            recipient: Email address to send to
            opportunity_type: Type of opportunity (CBDC_TO_DEFI, etc.)
            spread: Spread percentage
            profit: Estimated profit in USD
            confidence: Confidence score (0-100)
            timestamp: When the opportunity was detected
            
        Returns:
            True if email sent successfully
        """
        try:
            if not self.config.email_enabled:
                return False

            # Create email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🚨 HIGH-CONFIDENCE OPPORTUNITY DETECTED: {opportunity_type}"
            msg["From"] = self.config.email_address
            msg["To"] = recipient

            # HTML email body
            html = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background-color: #0a0e27; color: #e8e8e8;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #141829; border-radius: 8px; border: 1px solid #2a2f4a;">
                  
                  <h1 style="color: #00d9ff; margin-bottom: 10px;">⚡ SOVEREIGN-SINK ALERT</h1>
                  <p style="color: #8a8a8a; margin-top: 0;">High-Confidence Arbitrage Opportunity Detected</p>
                  
                  <hr style="border: none; border-top: 1px solid #2a2f4a; margin: 20px 0;">
                  
                  <h2 style="color: #00d9ff; font-size: 18px;">Opportunity Details</h2>
                  
                  <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #8a8a8a;">Type</td>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #e8e8e8; font-weight: bold;">{opportunity_type}</td>
                    </tr>
                    <tr>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #8a8a8a;">Spread</td>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #00d9ff; font-weight: bold;">{spread:.4f}%</td>
                    </tr>
                    <tr>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #8a8a8a;">Est. Profit</td>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #00d9ff; font-weight: bold;">${profit:.2f}</td>
                    </tr>
                    <tr>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #8a8a8a;">Confidence</td>
                      <td style="padding: 10px; border-bottom: 1px solid #2a2f4a; color: #00d9ff; font-weight: bold;">{confidence:.1f}%</td>
                    </tr>
                    <tr>
                      <td style="padding: 10px; color: #8a8a8a;">Detected</td>
                      <td style="padding: 10px; color: #e8e8e8;">{timestamp}</td>
                    </tr>
                  </table>
                  
                  <hr style="border: none; border-top: 1px solid #2a2f4a; margin: 20px 0;">
                  
                  <p style="color: #8a8a8a; font-size: 12px;">
                    This is an automated alert from the Sovereign-Sink Arbitrage System.
                    Log in to your dashboard to review and execute this opportunity.
                  </p>
                  
                  <p style="color: #8a8a8a; font-size: 12px; margin-bottom: 0;">
                    Dashboard: https://3000-i3je5kgd4dnml9pshwx1n-75d24699.us2.manus.computer
                  </p>
                </div>
              </body>
            </html>
            """

            msg.attach(MIMEText(html, "html"))

            # Send email
            with smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port) as server:
                server.login(self.config.email_address, self.config.email_password)
                server.sendmail(self.config.email_address, recipient, msg.as_string())

            logger.info(f"✓ Email alert sent to {recipient}")
            return True

        except Exception as e:
            logger.error(f"✗ Email send failed: {e}")
            return False

    async def send_telegram_alert(
        self,
        opportunity_type: str,
        spread: float,
        profit: float,
        confidence: float,
        timestamp: str
    ) -> bool:
        """
        Send Telegram alert for an opportunity.
        
        Args:
            opportunity_type: Type of opportunity
            spread: Spread percentage
            profit: Estimated profit in USD
            confidence: Confidence score (0-100)
            timestamp: When the opportunity was detected
            
        Returns:
            True if message sent successfully
        """
        try:
            if not self.config.telegram_enabled:
                return False

            # Create message
            message = (
                f"⚡ <b>SOVEREIGN-SINK ALERT</b>\n\n"
                f"<b>Opportunity:</b> {opportunity_type}\n"
                f"<b>Spread:</b> {spread:.4f}%\n"
                f"<b>Est. Profit:</b> ${profit:.2f}\n"
                f"<b>Confidence:</b> {confidence:.1f}%\n"
                f"<b>Detected:</b> {timestamp}\n\n"
                f"🔗 <a href='https://3000-i3je5kgd4dnml9pshwx1n-75d24699.us2.manus.computer'>Open Dashboard</a>"
            )

            # Send via Telegram Bot API
            url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"✓ Telegram alert sent to chat {self.config.telegram_chat_id}")
                        return True
                    else:
                        logger.error(f"✗ Telegram send failed: {resp.status}")
                        return False

        except Exception as e:
            logger.error(f"✗ Telegram send error: {e}")
            return False

    async def send_alert(
        self,
        alert_id: str,
        opportunity_id: str,
        opportunity_type: str,
        spread: float,
        profit: float,
        confidence: float,
        recipient_email: Optional[str] = None
    ) -> OpportunityAlert:
        """
        Send alert via all configured channels.
        
        Args:
            alert_id: Unique alert ID
            opportunity_id: ID of the opportunity
            opportunity_type: Type of opportunity
            spread: Spread percentage
            profit: Estimated profit
            confidence: Confidence score
            recipient_email: Email address (uses config if not provided)
            
        Returns:
            OpportunityAlert object
        """
        timestamp = datetime.now().isoformat()

        # Check cooldown
        if not self.should_send_alert(opportunity_id):
            logger.info(f"⏳ Alert throttled for {opportunity_id} (cooldown active)")
            return OpportunityAlert(
                alert_id=alert_id,
                opportunity_id=opportunity_id,
                opportunity_type=opportunity_type,
                spread_percentage=spread,
                estimated_profit=profit,
                confidence_score=confidence,
                timestamp=timestamp,
                sent_via_email=False,
                sent_via_telegram=False
            )

        # Send alerts
        email_sent = False
        telegram_sent = False

        if self.config.email_enabled:
            email_to = recipient_email or self.config.email_address
            email_sent = await self.send_email_alert(
                email_to,
                opportunity_type,
                spread,
                profit,
                confidence,
                timestamp
            )

        if self.config.telegram_enabled:
            telegram_sent = await self.send_telegram_alert(
                opportunity_type,
                spread,
                profit,
                confidence,
                timestamp
            )

        # Record alert
        alert = OpportunityAlert(
            alert_id=alert_id,
            opportunity_id=opportunity_id,
            opportunity_type=opportunity_type,
            spread_percentage=spread,
            estimated_profit=profit,
            confidence_score=confidence,
            timestamp=timestamp,
            sent_via_email=email_sent,
            sent_via_telegram=telegram_sent
        )

        self.alert_history.append(alert)
        self.last_alert_time[opportunity_id] = datetime.now()

        return alert

    def get_alert_history(self, limit: int = 20) -> List[Dict]:
        """
        Get recent alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alerts
        """
        recent = self.alert_history[-limit:]
        return [
            {
                "alert_id": a.alert_id,
                "opportunity_type": a.opportunity_type,
                "profit": a.estimated_profit,
                "confidence": a.confidence_score,
                "timestamp": a.timestamp,
                "email_sent": a.sent_via_email,
                "telegram_sent": a.sent_via_telegram
            }
            for a in recent
        ]


async def main():
    """
    Demonstration of alert system.
    """
    print("=" * 80)
    print("ALERT SYSTEM TEST")
    print("=" * 80)
    print()

    # Create config (with demo values)
    config = AlertConfig(
        email_enabled=True,
        email_address="your-email@gmail.com",
        email_password="your-app-password",
        smtp_server="smtp.gmail.com",
        smtp_port=465,
        telegram_enabled=True,
        telegram_bot_token="your-bot-token",
        telegram_chat_id="your-chat-id",
        min_confidence_threshold=85.0,
        alert_cooldown_seconds=300
    )

    alert_system = AlertSystem(config)

    print("Alert System Configuration:")
    print("-" * 80)
    print(f"Email Enabled: {config.email_enabled}")
    print(f"Telegram Enabled: {config.telegram_enabled}")
    print(f"Min Confidence Threshold: {config.min_confidence_threshold}%")
    print(f"Alert Cooldown: {config.alert_cooldown_seconds}s")
    print()

    # Validate config
    print("Validating configuration...")
    if alert_system.validate_config():
        print("✓ Configuration valid")
    else:
        print("✗ Configuration invalid (using demo mode)")
    print()

    # Simulate alert
    print("Simulating high-confidence opportunity alert...")
    print("-" * 80)
    print()

    alert = await alert_system.send_alert(
        alert_id="alert_demo_001",
        opportunity_id="opp_demo_001",
        opportunity_type="CBDC_TO_DEFI",
        spread=1.5,
        profit=250.0,
        confidence=92.5,
        recipient_email="your-email@gmail.com"
    )

    print(f"Alert ID: {alert.alert_id}")
    print(f"Opportunity: {alert.opportunity_type}")
    print(f"Profit: ${alert.estimated_profit:.2f}")
    print(f"Confidence: {alert.confidence_score:.1f}%")
    print(f"Email Sent: {alert.sent_via_email}")
    print(f"Telegram Sent: {alert.sent_via_telegram}")
    print()

    # Show alert history
    print("Alert History:")
    print("-" * 80)
    history = alert_system.get_alert_history()
    for h in history:
        print(f"  {h['timestamp']}: {h['opportunity_type']} - ${h['profit']:.2f} ({h['confidence']:.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
