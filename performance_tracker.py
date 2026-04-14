#!/usr/bin/env python3
"""
Performance Tracking Module
Tracks and analyzes trading performance metrics
"""

import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Individual trade record"""
    trade_id: str
    timestamp: str
    dex: str
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float
    entry_price: float
    exit_price: float
    position_size: float
    profit_loss: float
    profit_loss_percentage: float
    gas_cost: float
    confidence: float
    status: str  # "executed", "stopped_out", "taken_profit"


class PerformanceTracker:
    """
    Tracks and analyzes trading performance
    """

    def __init__(self, output_file: str = "performance_log.json"):
        """Initialize performance tracker"""
        self.trades: List[TradeRecord] = []
        self.output_file = output_file
        self.start_time = datetime.now()
        
        logger.info(f"📊 Performance Tracker initialized")
        logger.info(f"   Output file: {output_file}")

    def record_trade(self, trade_data: Dict[str, Any]) -> TradeRecord:
        """Record a completed trade"""
        trade = TradeRecord(
            trade_id=trade_data.get("trade_id"),
            timestamp=datetime.now().isoformat(),
            dex=trade_data.get("dex"),
            token_in=trade_data.get("token_in"),
            token_out=trade_data.get("token_out"),
            amount_in=trade_data.get("amount_in", 0),
            amount_out=trade_data.get("amount_out", 0),
            entry_price=trade_data.get("entry_price", 1.0),
            exit_price=trade_data.get("exit_price", 1.0),
            position_size=trade_data.get("position_size", 0),
            profit_loss=trade_data.get("profit_loss", 0),
            profit_loss_percentage=trade_data.get("profit_loss_percentage", 0),
            gas_cost=trade_data.get("gas_cost", 0),
            confidence=trade_data.get("confidence", 0),
            status=trade_data.get("status", "executed")
        )
        
        self.trades.append(trade)
        
        logger.info(f"✓ Trade recorded: {trade.trade_id}")
        logger.info(f"   P&L: ${trade.profit_loss:+,.2f} ({trade.profit_loss_percentage:+.2f}%)")
        
        # Save to file
        self.save_trades()
        
        return trade

    def save_trades(self) -> None:
        """Save trades to JSON file"""
        try:
            with open(self.output_file, 'w') as f:
                json.dump([asdict(t) for t in self.trades], f, indent=2)
            logger.debug(f"✓ Trades saved to {self.output_file}")
        except Exception as e:
            logger.error(f"✗ Failed to save trades: {str(e)}")

    def load_trades(self) -> None:
        """Load trades from JSON file"""
        try:
            with open(self.output_file, 'r') as f:
                trades_data = json.load(f)
                self.trades = [TradeRecord(**t) for t in trades_data]
            logger.info(f"✓ Loaded {len(self.trades)} trades from {self.output_file}")
        except FileNotFoundError:
            logger.info(f"No existing trades file found")
        except Exception as e:
            logger.error(f"✗ Failed to load trades: {str(e)}")

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics"""
        if not self.trades:
            return {
                "total_trades": 0,
                "total_profit_loss": 0,
                "win_rate": 0,
                "avg_profit_per_trade": 0,
                "largest_win": 0,
                "largest_loss": 0,
                "profit_factor": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0
            }
        
        total_pl = sum(t.profit_loss for t in self.trades)
        winning_trades = [t for t in self.trades if t.profit_loss > 0]
        losing_trades = [t for t in self.trades if t.profit_loss < 0]
        
        win_rate = (len(winning_trades) / len(self.trades)) * 100 if self.trades else 0
        
        total_wins = sum(t.profit_loss for t in winning_trades)
        total_losses = abs(sum(t.profit_loss for t in losing_trades))
        
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        largest_win = max((t.profit_loss for t in self.trades), default=0)
        largest_loss = min((t.profit_loss for t in self.trades), default=0)
        
        avg_profit = total_pl / len(self.trades) if self.trades else 0
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.profit_loss_percentage for t in self.trades]
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            sharpe_ratio = (mean_return / std_dev) if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown()
        
        return {
            "total_trades": len(self.trades),
            "total_profit_loss": total_pl,
            "win_rate": win_rate,
            "avg_profit_per_trade": avg_profit,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades)
        }

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self.trades:
            return 0
        
        cumulative_pl = 0
        peak = 0
        max_dd = 0
        
        for trade in self.trades:
            cumulative_pl += trade.profit_loss
            if cumulative_pl > peak:
                peak = cumulative_pl
            
            drawdown = peak - cumulative_pl
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd

    def get_daily_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics grouped by day"""
        daily_stats = defaultdict(lambda: {
            "trades": 0,
            "profit_loss": 0,
            "win_rate": 0,
            "avg_profit": 0
        })
        
        for trade in self.trades:
            date = trade.timestamp.split('T')[0]
            daily_stats[date]["trades"] += 1
            daily_stats[date]["profit_loss"] += trade.profit_loss
            if trade.profit_loss > 0:
                daily_stats[date]["wins"] = daily_stats[date].get("wins", 0) + 1
        
        # Calculate win rates and averages
        for date in daily_stats:
            stats = daily_stats[date]
            stats["win_rate"] = (stats.get("wins", 0) / stats["trades"] * 100) if stats["trades"] > 0 else 0
            stats["avg_profit"] = stats["profit_loss"] / stats["trades"] if stats["trades"] > 0 else 0
        
        return dict(daily_stats)

    def get_dex_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics grouped by DEX"""
        dex_stats = defaultdict(lambda: {
            "trades": 0,
            "profit_loss": 0,
            "win_rate": 0,
            "avg_profit": 0
        })
        
        for trade in self.trades:
            dex = trade.dex
            dex_stats[dex]["trades"] += 1
            dex_stats[dex]["profit_loss"] += trade.profit_loss
            if trade.profit_loss > 0:
                dex_stats[dex]["wins"] = dex_stats[dex].get("wins", 0) + 1
        
        # Calculate win rates and averages
        for dex in dex_stats:
            stats = dex_stats[dex]
            stats["win_rate"] = (stats.get("wins", 0) / stats["trades"] * 100) if stats["trades"] > 0 else 0
            stats["avg_profit"] = stats["profit_loss"] / stats["trades"] if stats["trades"] > 0 else 0
        
        return dict(dex_stats)

    def get_confidence_analysis(self) -> Dict[str, Any]:
        """Analyze performance by confidence levels"""
        confidence_buckets = {
            "75-80": [],
            "80-85": [],
            "85-90": [],
            "90-95": [],
            "95-100": []
        }
        
        for trade in self.trades:
            conf = trade.confidence
            if 75 <= conf < 80:
                confidence_buckets["75-80"].append(trade)
            elif 80 <= conf < 85:
                confidence_buckets["80-85"].append(trade)
            elif 85 <= conf < 90:
                confidence_buckets["85-90"].append(trade)
            elif 90 <= conf < 95:
                confidence_buckets["90-95"].append(trade)
            elif 95 <= conf <= 100:
                confidence_buckets["95-100"].append(trade)
        
        analysis = {}
        for bucket, trades in confidence_buckets.items():
            if trades:
                total_pl = sum(t.profit_loss for t in trades)
                win_rate = (sum(1 for t in trades if t.profit_loss > 0) / len(trades)) * 100
                analysis[bucket] = {
                    "trades": len(trades),
                    "total_profit_loss": total_pl,
                    "win_rate": win_rate,
                    "avg_profit": total_pl / len(trades)
                }
        
        return analysis

    def generate_report(self) -> str:
        """Generate comprehensive performance report"""
        summary = self.get_summary_stats()
        daily = self.get_daily_stats()
        dex = self.get_dex_stats()
        confidence = self.get_confidence_analysis()
        
        report = f"""
{'='*80}
SOVEREIGN-SINK ARBITRAGE PERFORMANCE REPORT
{'='*80}

SUMMARY STATISTICS
{'-'*80}
Total Trades: {summary['total_trades']}
Total Profit/Loss: ${summary['total_profit_loss']:+,.2f}
Win Rate: {summary['win_rate']:.1f}%
Average Profit per Trade: ${summary['avg_profit_per_trade']:+,.2f}
Largest Win: ${summary['largest_win']:+,.2f}
Largest Loss: ${summary['largest_loss']:+,.2f}
Profit Factor: {summary['profit_factor']:.2f}
Sharpe Ratio: {summary['sharpe_ratio']:.2f}
Max Drawdown: ${summary['max_drawdown']:+,.2f}

DAILY PERFORMANCE
{'-'*80}
"""
        
        for date, stats in sorted(daily.items()):
            report += f"{date}: {stats['trades']} trades, ${stats['profit_loss']:+,.2f} P&L, {stats['win_rate']:.1f}% win rate\n"
        
        report += f"\nDEX PERFORMANCE\n{'-'*80}\n"
        for dex_name, stats in dex.items():
            report += f"{dex_name}: {stats['trades']} trades, ${stats['profit_loss']:+,.2f} P&L, {stats['win_rate']:.1f}% win rate\n"
        
        report += f"\nCONFIDENCE ANALYSIS\n{'-'*80}\n"
        for bucket, stats in confidence.items():
            report += f"{bucket}%: {stats['trades']} trades, ${stats['total_profit_loss']:+,.2f} P&L, {stats['win_rate']:.1f}% win rate\n"
        
        report += f"\n{'='*80}\n"
        
        return report

    def print_report(self) -> None:
        """Print performance report"""
        report = self.generate_report()
        print(report)
        logger.info(report)


def test_performance_tracker():
    """Test performance tracker"""
    tracker = PerformanceTracker()
    
    # Record some test trades
    tracker.record_trade({
        "trade_id": "trade_1",
        "dex": "uniswap_v3",
        "token_in": "USDC",
        "token_out": "USDT",
        "amount_in": 1000,
        "amount_out": 1005,
        "entry_price": 1.0,
        "exit_price": 1.005,
        "position_size": 1000,
        "profit_loss": 5,
        "profit_loss_percentage": 0.5,
        "gas_cost": 50,
        "confidence": 92,
        "status": "executed"
    })
    
    tracker.record_trade({
        "trade_id": "trade_2",
        "dex": "1inch",
        "token_in": "USDT",
        "token_out": "USDC",
        "amount_in": 1000,
        "amount_out": 995,
        "entry_price": 1.0,
        "exit_price": 0.995,
        "position_size": 1000,
        "profit_loss": -5,
        "profit_loss_percentage": -0.5,
        "gas_cost": 50,
        "confidence": 78,
        "status": "stopped_out"
    })
    
    # Print report
    tracker.print_report()


if __name__ == "__main__":
    test_performance_tracker()
