"""Chart renderers for backtest-study reports — RESEARCH tier, never scheduled.

A study under `scripts/backtest_study/` prints a long fixed-width report that is
read once and argued about. Some of what it prints is genuinely tabular — an
equity curve, a 4x4 cap grid, a monthly utilisation table — and those are slow
to read as text and easy to misread. This package turns one study's output into
a single self-contained HTML page so the shape of the result is visible at a
glance.

    python -m scripts.study_charts.account_sim

It renders, it never computes a new conclusion. Every number on the page is
either read straight out of the study's own report text or recomputed from the
positions CSV the study exported — and the recomputed ones are reconciled
against the report at build time (`series.reconcile`), so a chart can never
quietly disagree with the report it claims to draw.

Nothing here may add a statistic the study itself refused to print. account_sim
forbids an annualised figure, a Sharpe ratio, and a time-to-recover by
construction; the renderer does not reintroduce them.
"""
