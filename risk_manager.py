#!/usr/bin/env python3
"""
Risk Management Module
Implements position sizing, stop-losses, and circuit breakers
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for position sizing"""
    CONSERVATIVE = "conservative"  # 1-2% of capital per trade
    MODERATE = "moderate"          # 2-5% of capital per trade
    AGGRESSIVE = "aggressive"      # 5-10% of capital per trade


@dataclass
class RiskConfig:
    """Risk management configuration"""
    total_capital: float
    risk_level: RiskLevel
    max_position_size: float
    max_daily_loss: float
    max_drawdown: float
    stop_loss_percentage: float
    take_profit_percentage: float
    circuit_breaker_threshold: float


class RiskManager:
    """
    Manages trading risk through position sizing, stops, and circuit breakers
    """

    def __init__(self, config: RiskConfig):
        """Initialize risk manager"""
        self.config = config
        self.current_capital = config.total_capital
        self.daily_loss = 0
        self.peak_capital = config.total_capital
        self.circuit_breaker_active = False
        self.trades_today = []
        self.last_reset = datetime.now()
        
        logger.info(f"🛡️ Risk Manager initialized")
        logger.info(f"   Total Capital: ${config.total_capital:,.2f}")
        logger.info(f"   Risk Level: {config.risk_level.value}")
        logger.info(f"   Max Position: ${config.max_position_size:,.2f}")
        logger.info(f"   Max Daily Loss: ${config.max_daily_loss:,.2f}")
        logger.info(f"   Max Drawdown: {config.max_drawdown:.1f}%")

    def calculate_position_size(self, confidence: float) -> float:
        """Calculate position size based on risk level and confidence"""
        # Base position size from risk level
        if self.config.risk_level == RiskLevel.CONSERVATIVE:
            base_size = self.config.total_capital * 0.015  # 1.5%
        elif self.config.risk_level == RiskLevel.MODERATE:
            base_size = self.config.total_capital * 0.035  # 3.5%
        else:  # AGGRESSIVE
            base_size = self.config.total_capital * 0.075  # 7.5%
        
        # Adjust based on confidence
        confidence_multiplier = min(1.5, confidence / 100)  # Max 1.5x for 100% confidence
        position_size = base_size * confidence_multiplier
        
        # Cap at max position size
        position_size = min(position_size, self.config.max_position_size)
        
        # Cap at available capital
        position_size = min(position_size, self.current_capital * 0.5)
        
        logger.info(f"📊 Position Size Calculated")
        logger.info(f"   Confidence: {confidence:.1f}%")
        logger.info(f"   Base Size: ${base_size:,.2f}")
        logger.info(f"   Final Size: ${position_size:,.2f}")
        
        return position_size

    def check_position_limits(self, position_size: float) -> bool:
        """Check if position respects risk limits"""
        # Check against max position size
        if position_size > self.config.max_position_size:
            logger.warning(f"⚠ Position ${position_size:,.2f} exceeds max ${self.config.max_position_size:,.2f}")
            return False
        
        # Check against available capital
        if position_size > self.current_capital * 0.5:
            logger.warning(f"⚠ Position would use more than 50% of capital")
            return False
        
        # Check circuit breaker
        if self.circuit_breaker_active:
            logger.warning(f"⚠ Circuit breaker is active - no new positions allowed")
            return False
        
        return True

    def apply_stop_loss(self, entry_price: float, position_size: float) -> float:
        """Calculate stop loss price"""
        stop_loss_price = entry_price * (1 - self.config.stop_loss_percentage / 100)
        max_loss = position_size * (self.config.stop_loss_percentage / 100)
        
        logger.info(f"🛑 Stop Loss Set")
        logger.info(f"   Entry: ${entry_price:.6f}")
        logger.info(f"   Stop: ${stop_loss_price:.6f}")
        logger.info(f"   Max Loss: ${max_loss:,.2f}")
        
        return stop_loss_price

    def apply_take_profit(self, entry_price: float, position_size: float) -> float:
        """Calculate take profit price"""
        take_profit_price = entry_price * (1 + self.config.take_profit_percentage / 100)
        max_gain = position_size * (self.config.take_profit_percentage / 100)
        
        logger.info(f"🎯 Take Profit Set")
        logger.info(f"   Entry: ${entry_price:.6f}")
        logger.info(f"   Target: ${take_profit_price:.6f}")
        logger.info(f"   Max Gain: ${max_gain:,.2f}")
        
        return take_profit_price

    def record_trade_result(self, profit_loss: float) -> None:
        """Record trade result and update risk metrics"""
        self.current_capital += profit_loss
        self.trades_today.append({
            "timestamp": datetime.now(),
            "profit_loss": profit_loss
        })
        
        # Update daily loss
        if profit_loss < 0:
            self.daily_loss += abs(profit_loss)
        
        # Update peak capital for drawdown calculation
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        # Check if daily loss limit exceeded
        if self.daily_loss > self.config.max_daily_loss:
            logger.error(f"❌ Daily loss limit exceeded: ${self.daily_loss:,.2f} > ${self.config.max_daily_loss:,.2f}")
            self.activate_circuit_breaker()
        
        # Check drawdown
        drawdown = ((self.peak_capital - self.current_capital) / self.peak_capital) * 100
        if drawdown > self.config.max_drawdown:
            logger.error(f"❌ Max drawdown exceeded: {drawdown:.1f}% > {self.config.max_drawdown:.1f}%")
            self.activate_circuit_breaker()
        
        logger.info(f"📈 Trade Result: ${profit_loss:+,.2f}")
        logger.info(f"   Capital: ${self.current_capital:,.2f}")
        logger.info(f"   Daily Loss: ${self.daily_loss:,.2f}")
        logger.info(f"   Drawdown: {drawdown:.1f}%")

    def activate_circuit_breaker(self) -> None:
        """Activate circuit breaker to stop trading"""
        self.circuit_breaker_active = True
        logger.error(f"🚨 CIRCUIT BREAKER ACTIVATED - Trading halted")

    def deactivate_circuit_breaker(self) -> None:
        """Deactivate circuit breaker (manual reset)"""
        self.circuit_breaker_active = False
        logger.info(f"✓ Circuit breaker deactivated")

    def reset_daily_metrics(self) -> None:
        """Reset daily metrics (call at market open)"""
        if datetime.now() - self.last_reset > timedelta(hours=24):
            self.daily_loss = 0
            self.trades_today = []
            self.last_reset = datetime.now()
            logger.info(f"✓ Daily metrics reset")

    def get_risk_report(self) -> Dict[str, Any]:
        """Get current risk report"""
        drawdown = ((self.peak_capital - self.current_capital) / self.peak_capital) * 100 if self.peak_capital > 0 else 0
        
        return {
            "current_capital": self.current_capital,
            "peak_capital": self.peak_capital,
            "daily_loss": self.daily_loss,
            "drawdown_percentage": drawdown,
            "daily_loss_limit": self.config.max_daily_loss,
            "max_drawdown_limit": self.config.max_drawdown,
            "circuit_breaker_active": self.circuit_breaker_active,
            "trades_today": len(self.trades_today),
            "capital_at_risk": self.config.total_capital - self.current_capital
        }

    def validate_trade(self, position_size: float, confidence: float, estimated_profit: float) -> bool:
        """Validate if trade should be executed based on risk parameters"""
        logger.info(f"🔍 Validating trade")
        logger.info(f"   Position: ${position_size:,.2f}")
        logger.info(f"   Confidence: {confidence:.1f}%")
        logger.info(f"   Est. Profit: ${estimated_profit:,.2f}")
        
        # Check position limits
        if not self.check_position_limits(position_size):
            logger.warning(f"❌ Trade rejected - position limits exceeded")
            return False
        
        # Check minimum profit threshold
        if estimated_profit < 50:  # Minimum $50 profit
            logger.warning(f"❌ Trade rejected - profit too low: ${estimated_profit:,.2f}")
            return False
        
        # Check confidence threshold
        if confidence < 75:
            logger.warning(f"❌ Trade rejected - confidence too low: {confidence:.1f}%")
            return False
        
        logger.info(f"✅ Trade validation passed")
        return True


def test_risk_manager():
    """Test risk manager"""
    config = RiskConfig(
        total_capital=10000,
        risk_level=RiskLevel.MODERATE,
        max_position_size=1000,
        max_daily_loss=500,
        max_drawdown=10,
        stop_loss_percentage=2,
        take_profit_percentage=5,
        circuit_breaker_threshold=500
    )
    
    manager = RiskManager(config)
    
    # Test position sizing
    position = manager.calculate_position_size(confidence=90)
    print(f"Position size: ${position:,.2f}")
    
    # Test stop loss
    stop = manager.apply_stop_loss(entry_price=1.0, position_size=position)
    print(f"Stop loss: ${stop:.6f}")
    
    # Test take profit
    tp = manager.apply_take_profit(entry_price=1.0, position_size=position)
    print(f"Take profit: ${tp:.6f}")
    
    # Test trade recording
    manager.record_trade_result(profit_loss=100)
    manager.record_trade_result(profit_loss=-50)
    
    # Get report
    report = manager.get_risk_report()
    print(f"Risk report: {report}")


if __name__ == "__main__":
    test_risk_manager()
