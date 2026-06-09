TODO — Backtest engine fixes (/options)
Source of issues: analysis\_-_BacktestResults.csv review (39 trades, 13 entry days).
P0 — Exit engine does not implement the documented invalidation rules
The backtest exits on fixed horizons + a fixed profit-target %, and otherwise holds to
expiry. It does NOT evaluate the invalidation conditions in AnalysisClaude
(e.g. "AAPL close < 290", "SMH reclaims 570", "BTC drops >10%").

Parse each trade's invalidation rule and evaluate it against daily underlying closes, exiting on the first day the condition is met (at that day's spread mark).
Stop relabeling expiry as stop_loss. 7 of 8 current stop_loss rows occur at a horizon past the option's expiration (NVDA 235/265, MSTR 180/210, GLD, SMH 555/520, NVDA 215/195, TSLA, IBIT). These are expired-worthless, not stops.
At expiration, mark to intrinsic value, not a blanket -100% / $0.
Add a distinct terminal status set: invalidation_exit, expired_intrinsic, profit_target, time_stop — drop the misused stop_loss.

P1 — Entry faithfulness (executed trade ≠ documented play)
Strikes/expiries drift between the play and the traded row.

ARM: play = 220/250 Aug-21, traded = 170/250 (0.80-delta long leg — different instrument).
SOXX: play = 525/600, traded = 515/600.
AAPL: play = "300/325 Dec-18", analysis says Jan-27, traded = Jan-2028 expiry.
Add a reconciliation check that fails loudly when executed strike/expiry ≠ play.
