"""Summary statistics for a backtest run."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import TradeResult


def compute_metrics(results: list[TradeResult], equity_curve: pd.DataFrame, starting_equity: float) -> dict:
    if not results:
        return {"trades": 0}

    pnls = np.array([r.pnl_dollars for r in results])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    ending_equity = equity_curve["equity"].iloc[-1] if not equity_curve.empty else starting_equity
    running_max = equity_curve["equity"].cummax() if not equity_curve.empty else pd.Series([starting_equity])
    drawdown = (equity_curve["equity"] - running_max) / running_max if not equity_curve.empty else pd.Series([0.0])

    daily_returns = equity_curve["pnl"] / (running_max.shift(1).fillna(starting_equity)) if not equity_curve.empty else pd.Series([0.0])
    sharpe = (
        (daily_returns.mean() / daily_returns.std() * np.sqrt(252))
        if not equity_curve.empty and daily_returns.std() > 0
        else 0.0
    )

    return {
        "trades": len(results),
        "trading_days": len(equity_curve),
        "win_rate": len(wins) / len(pnls),
        "avg_win": wins.mean() if len(wins) else 0.0,
        "avg_loss": losses.mean() if len(losses) else 0.0,
        "profit_factor": (wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf"),
        "total_return_pct": (ending_equity / starting_equity - 1) * 100,
        "ending_equity": ending_equity,
        "max_drawdown_pct": drawdown.min() * 100,
        "avg_daily_pnl": equity_curve["pnl"].mean() if not equity_curve.empty else 0.0,
        "best_day_pnl": equity_curve["pnl"].max() if not equity_curve.empty else 0.0,
        "worst_day_pnl": equity_curve["pnl"].min() if not equity_curve.empty else 0.0,
        "sharpe_annualized": sharpe,
    }


def format_metrics(metrics: dict) -> str:
    if metrics.get("trades", 0) == 0:
        return "No trades were generated."
    lines = [
        f"Trades:              {metrics['trades']} over {metrics['trading_days']} trading days",
        f"Win rate:             {metrics['win_rate']:.1%}",
        f"Avg win / avg loss:   ${metrics['avg_win']:.2f} / ${metrics['avg_loss']:.2f}",
        f"Profit factor:        {metrics['profit_factor']:.2f}",
        f"Total return:         {metrics['total_return_pct']:.2f}%",
        f"Ending equity:        ${metrics['ending_equity']:.2f}",
        f"Max drawdown:         {metrics['max_drawdown_pct']:.2f}%",
        f"Avg daily P&L:        ${metrics['avg_daily_pnl']:.2f}",
        f"Best / worst day:     ${metrics['best_day_pnl']:.2f} / ${metrics['worst_day_pnl']:.2f}",
        f"Sharpe (annualized):  {metrics['sharpe_annualized']:.2f}",
    ]
    return "\n".join(lines)
