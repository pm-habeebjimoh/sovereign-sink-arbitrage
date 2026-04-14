#!/usr/bin/env python3
"""
LIVE EXECUTION ENGINE - Complete Production System
Integrates: Price Feeds + Opportunity Detection + Risk Management + DEX Execution + Performance Tracking
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import asdict
from dotenv import load_dotenv

from price_feed_integration import PriceFeedIntegration
from alert_system import AlertSystem, AlertConfig
from dex_executor import DEXExecutor, DEXType
from risk_manager import RiskManager, RiskConfig, RiskLevel
from performance_tracker import PerformanceTracker

# Load production environment
load_dotenv('.env.production')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', 'live_execution.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LiveExecutionEngine:
    """
    Complete LIVE trading execution engine
    Orchestrates all components for real-time arbitrage trading
    """

    def __init__(self):
        """Initialize the complete execution engine"""
        self.system_mode = "LIVE"  # Force LIVE mode
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        self.private_key = os.getenv('PRIVATE_KEY')
        
        # Initialize price feeds
        self.price_feed = PriceFeedIntegration()
        self.price_feed.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
        self.price_feed.coingecko_api_key = os.getenv('COINGECKO_API_KEY')
        self.price_feed.ethereum_l2_rpc = os.getenv('ETHEREUM_L2_RPC')
        self.price_feed.solana_rpc = os.getenv('SOLANA_RPC')
        
        # Initialize Telegram alerts (no email)
        alert_config = AlertConfig(
            email_enabled=False,
            email_address='',
            email_password='',
            smtp_server='',
            smtp_port=465,
            telegram_enabled=os.getenv('TELEGRAM_ENABLED', 'true').lower() == 'true',
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            min_confidence_threshold=float(os.getenv('MIN_CONFIDENCE_THRESHOLD', 85.0)),
            alert_cooldown_seconds=int(os.getenv('ALERT_COOLDOWN_SECONDS', 300))
        )
        self.alerts = AlertSystem(alert_config)
        
        # Initialize DEX executor
        self.dex_executor = DEXExecutor(
            private_key=self.private_key,
            wallet_address=self.wallet_address,
            rpc_url=os.getenv('ETHEREUM_L2_RPC')
        )
        
        # Initialize risk manager
        risk_config = RiskConfig(
            total_capital=float(os.getenv('MAX_POSITION_SIZE', 5000.0)) * 10,  # Assume 10x position
            risk_level=RiskLevel.MODERATE,
            max_position_size=float(os.getenv('MAX_POSITION_SIZE', 5000.0)),
            max_daily_loss=float(os.getenv('MAX_POSITION_SIZE', 5000.0)) * 0.2,  # 20% of max position
            max_drawdown=15.0,  # 15% max drawdown
            stop_loss_percentage=2.0,
            take_profit_percentage=5.0,
            circuit_breaker_threshold=1000.0
        )
        self.risk_manager = RiskManager(risk_config)
        
        # Initialize performance tracker
        self.performance_tracker = PerformanceTracker('live_performance.json')
        self.performance_tracker.load_trades()
        
        # Metrics
        self.cycle_count = 0
        self.total_opportunities = 0
        self.executed_trades = 0
        self.total_profit = 0.0
        
        logger.info("="*80)
        logger.info("🚀 LIVE EXECUTION ENGINE INITIALIZED - PRODUCTION MODE")
        logger.info("="*80)
        logger.info(f"Wallet: {self.wallet_address}")
        logger.info(f"Mode: {self.system_mode}")
        logger.info(f"Telegram Alerts: Enabled")
        logger.info(f"Risk Level: MODERATE")
        logger.info(f"Max Position: ${risk_config.max_position_size:,.2f}")
        logger.info("="*80)

    async def fetch_live_prices(self) -> Optional[Dict[str, Any]]:
        """Fetch live market prices"""
        try:
            logger.info("📊 Fetching live prices...")
            
            cbdc_rate = await self.price_feed.fetch_chainlink_cbdc_rate()
            if cbdc_rate is None:
                cbdc_rate = 1.0
            
            defi_rates = await self.price_feed.fetch_coingecko_defi_rates()
            defi_rate = defi_rates.get('usdc', 1.0) if defi_rates else 1.0
            
            basefee = await self.price_feed.fetch_ethereum_basefee()
            if basefee is None:
                basefee = 0.0
            
            spread = abs(defi_rate - cbdc_rate) / cbdc_rate * 100 if cbdc_rate > 0 else 0
            
            price_data = {
                "cbdc_rate": cbdc_rate,
                "defi_rate": defi_rate,
                "spread": spread,
                "basefee": basefee,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"   CBDC: ${cbdc_rate:.6f} | DeFi: ${defi_rate:.6f} | Spread: {spread:.4f}%")
            
            return price_data
            
        except Exception as e:
            logger.error(f"❌ Price fetch failed: {str(e)}")
            return None

    def detect_opportunities(self, prices: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect arbitrage opportunities"""
        opportunities = []
        
        try:
            spread = prices.get('spread', 0)
            basefee = prices.get('basefee', 0)
            
            # Opportunity 1: Spread arbitrage
            if spread > 0.5:  # Min 0.5% spread
                confidence = min(99, 60 + (spread * 10) + (basefee / 5))
                estimated_profit = (1000 * spread / 100) - 50  # Position size 1000, minus gas
                
                if estimated_profit > 0:
                    opp = {
                        "type": "SPREAD_ARBITRAGE",
                        "spread": spread,
                        "confidence": confidence,
                        "estimated_profit": estimated_profit,
                        "position_size": 1000,
                        "timestamp": datetime.now().isoformat()
                    }
                    opportunities.append(opp)
                    logger.info(f"   ✓ Spread Arbitrage: {spread:.4f}% | Confidence: {confidence:.1f}% | Profit: ${estimated_profit:.2f}")
            
            # Opportunity 2: Basefee capture
            if basefee > 40:
                confidence = min(98, 70 + (basefee / 2))
                estimated_profit = (basefee / 100) * 100
                
                opp = {
                    "type": "BASEFEE_CAPTURE",
                    "basefee": basefee,
                    "confidence": confidence,
                    "estimated_profit": estimated_profit,
                    "position_size": 500,
                    "timestamp": datetime.now().isoformat()
                }
                opportunities.append(opp)
                logger.info(f"   ✓ Basefee Capture: {basefee:.1f}% | Confidence: {confidence:.1f}% | Profit: ${estimated_profit:.2f}")
            
            self.total_opportunities += len(opportunities)
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Opportunity detection failed: {str(e)}")
            return []

    async def execute_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """Execute a detected opportunity"""
        try:
            logger.info(f"🔄 Executing opportunity: {opportunity['type']}")
            
            # Calculate position size based on risk
            position_size = self.risk_manager.calculate_position_size(opportunity['confidence'])
            
            # Validate trade
            if not self.risk_manager.validate_trade(
                position_size=position_size,
                confidence=opportunity['confidence'],
                estimated_profit=opportunity['estimated_profit']
            ):
                logger.warning(f"❌ Trade validation failed")
                return False
            
            # Execute on DEX
            trade = await self.dex_executor.execute_trade(
                dex=DEXType.ONE_INCH,
                token_in="USDC",
                token_out="USDT",
                amount=position_size,
                min_output=position_size * (1 + opportunity['spread'] / 100) * 0.99
            )
            
            if not trade:
                logger.error(f"❌ Trade execution failed")
                return False
            
            # Record trade result
            self.risk_manager.record_trade_result(trade.profit)
            
            # Track performance
            self.performance_tracker.record_trade({
                "trade_id": trade.trade_id,
                "dex": trade.dex.value,
                "token_in": trade.token_in,
                "token_out": trade.token_out,
                "amount_in": trade.amount_in,
                "amount_out": trade.amount_out,
                "entry_price": 1.0,
                "exit_price": trade.amount_out / trade.amount_in,
                "position_size": position_size,
                "profit_loss": trade.profit,
                "profit_loss_percentage": (trade.profit / position_size) * 100,
                "gas_cost": trade.gas_used,
                "confidence": opportunity['confidence'],
                "status": "executed"
            })
            
            self.executed_trades += 1
            self.total_profit += trade.profit
            
            logger.info(f"✅ Trade executed successfully")
            logger.info(f"   Profit: ${trade.profit:+,.2f}")
            logger.info(f"   Total Profit: ${self.total_profit:+,.2f}")
            
            # Send Telegram alert
            alert_text = (
                f"✅ TRADE EXECUTED\n\n"
                f"Type: {opportunity['type']}\n"
                f"Confidence: {opportunity['confidence']:.1f}%\n"
                f"Profit: ${trade.profit:+,.2f}\n"
                f"Total Profit: ${self.total_profit:+,.2f}"
            )
            await self.alerts.send_telegram_alert(alert_text)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Execution error: {str(e)}")
            return False

    async def execute_live_cycle(self) -> Dict[str, Any]:
        """Execute a single live trading cycle"""
        self.cycle_count += 1
        cycle_start = datetime.now()
        
        logger.info("="*80)
        logger.info(f"CYCLE #{self.cycle_count} - {cycle_start.isoformat()}")
        logger.info("="*80)
        
        cycle_result = {
            "cycle": self.cycle_count,
            "timestamp": cycle_start.isoformat(),
            "opportunities_detected": 0,
            "trades_executed": 0,
            "total_profit": 0,
            "status": "completed"
        }
        
        try:
            # Fetch prices
            prices = await self.fetch_live_prices()
            if not prices:
                cycle_result["status"] = "price_fetch_failed"
                return cycle_result
            
            # Detect opportunities
            opportunities = self.detect_opportunities(prices)
            cycle_result["opportunities_detected"] = len(opportunities)
            logger.info(f"🔍 Opportunities detected: {len(opportunities)}")
            
            # Execute high-confidence opportunities
            for opp in opportunities:
                if opp['confidence'] >= 85:  # Only execute high-confidence trades
                    executed = await self.execute_opportunity(opp)
                    if executed:
                        cycle_result["trades_executed"] += 1
            
            # Get risk report
            risk_report = self.risk_manager.get_risk_report()
            cycle_result["total_profit"] = self.total_profit
            cycle_result["capital"] = risk_report['current_capital']
            cycle_result["drawdown"] = risk_report['drawdown_percentage']
            
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            
            logger.info(f"\n📈 Cycle Summary:")
            logger.info(f"   Duration: {cycle_duration:.2f}s")
            logger.info(f"   Opportunities: {len(opportunities)}")
            logger.info(f"   Trades Executed: {cycle_result['trades_executed']}")
            logger.info(f"   Total Profit: ${self.total_profit:+,.2f}")
            logger.info(f"   Capital: ${risk_report['current_capital']:,.2f}")
            logger.info(f"   Drawdown: {risk_report['drawdown_percentage']:.2f}%")
            
            # Save cycle result
            with open(f"cycle_live_{self.cycle_count:04d}.json", "w") as f:
                json.dump(cycle_result, f, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Cycle error: {str(e)}")
            cycle_result["status"] = "error"
        
        return cycle_result

    async def run_live_continuous(self, interval: int = 5, max_cycles: Optional[int] = None):
        """Run continuous live trading"""
        logger.info(f"\n🚀 STARTING LIVE CONTINUOUS TRADING")
        logger.info(f"   Interval: {interval}s")
        logger.info(f"   Max Cycles: {max_cycles if max_cycles else 'Unlimited'}")
        logger.info(f"   Mode: {self.system_mode}")
        
        try:
            cycle = 0
            while True:
                if max_cycles and cycle >= max_cycles:
                    logger.info(f"Reached maximum cycles ({max_cycles}). Stopping.")
                    break
                
                await self.execute_live_cycle()
                cycle += 1
                
                if max_cycles is None:
                    await asyncio.sleep(interval)
                else:
                    if cycle < max_cycles:
                        await asyncio.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("\n⏹ Live trading stopped by user")
        except Exception as e:
            logger.error(f"❌ Fatal error: {str(e)}")
        finally:
            self.print_final_report()

    def print_final_report(self):
        """Print final trading report"""
        logger.info("\n" + "="*80)
        logger.info("FINAL LIVE TRADING REPORT")
        logger.info("="*80)
        
        summary = self.performance_tracker.get_summary_stats()
        risk_report = self.risk_manager.get_risk_report()
        
        logger.info(f"System Mode: {self.system_mode}")
        logger.info(f"Cycles Completed: {self.cycle_count}")
        logger.info(f"Total Opportunities: {self.total_opportunities}")
        logger.info(f"Trades Executed: {self.executed_trades}")
        logger.info(f"Total Profit/Loss: ${self.total_profit:+,.2f}")
        logger.info(f"\nPerformance Stats:")
        logger.info(f"   Win Rate: {summary['win_rate']:.1f}%")
        logger.info(f"   Profit Factor: {summary['profit_factor']:.2f}")
        logger.info(f"   Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
        logger.info(f"   Max Drawdown: {summary['max_drawdown']:+,.2f}")
        logger.info(f"\nRisk Report:")
        logger.info(f"   Current Capital: ${risk_report['current_capital']:,.2f}")
        logger.info(f"   Daily Loss: ${risk_report['daily_loss']:,.2f}")
        logger.info(f"   Drawdown: {risk_report['drawdown_percentage']:.2f}%")
        logger.info(f"   Circuit Breaker: {'ACTIVE' if risk_report['circuit_breaker_active'] else 'INACTIVE'}")
        logger.info("="*80)
        
        # Print detailed report
        self.performance_tracker.print_report()


async def main():
    """Main entry point"""
    engine = LiveExecutionEngine()
    
    # Run continuous live trading
    # For testing: 10 cycles with 5-second interval
    # For production: remove max_cycles to run indefinitely
    await engine.run_live_continuous(interval=5, max_cycles=10)


if __name__ == "__main__":
    asyncio.run(main())
