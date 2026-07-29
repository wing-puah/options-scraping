"""Clean raw IBKR trade exports into one strategy-labelled options dataset.

Reads every ``portfolio/input/trades_*.csv`` (IBKR flex export), keeps the
option rows, classifies each execution into an option structure, then walks the
executions per ticker to group them into strategies with a lifecycle label.

Output: ``portfolio/output/cleaned_trades.csv``, consumed by ``02_analysis.py``.
"""

from collections import defaultdict
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

# --------------------------------------------------
# Load
# --------------------------------------------------


def load_trades():
    files = sorted(INPUT_DIR.glob("trades_*.csv"))

    if not files:
        raise SystemExit(f"No trades_*.csv files found in {INPUT_DIR}")

    dataframes = []
    for path in files:
        df_year = pd.read_csv(path)
        dataframes.append(df_year)
        print(f"Loaded {path.name} ({len(df_year)} rows)")

    all_trades = pd.concat(dataframes, ignore_index=True)
    print(f"Total combined trades: {len(all_trades)}")

    return all_trades


def prepare_options(all_trades):
    """Keep option rows only and derive the columns the classifier needs."""
    df = all_trades[all_trades["AssetClass"] == "OPT"].copy()
    df = df.rename(columns={"Open/CloseIndicator": "OpenClose"})
    print(f"Rows after filtering for AssetClass == 'OPT': {len(df)}")

    df["Expiry"] = pd.to_datetime(df["Expiry"], format="%Y-%m-%d")
    df["ExcDate"] = pd.to_datetime(
        df["DateTime"].str.split(";").str[0], format="%Y-%m-%d"
    )
    df["DTE"] = (df["Expiry"] - df["ExcDate"]).dt.days

    negative_dte = (df["DTE"] < 0).sum()
    if negative_dte:
        print(f"[WARN] {negative_dte} rows have a negative DTE")

    df["Put/Call"] = df["Put/Call"].str.upper()
    df["Strike"] = pd.to_numeric(df["Strike"], errors="coerce")

    # One execution = every leg filled for the same underlying at the same instant.
    df["ExecutionId"] = df["UnderlyingSymbol"] + "_" + df["DateTime"]

    return df


# -------------------------------------------------------
# SINGLE LEG
# -------------------------------------------------------


def _classify_single_leg(group):
    leg = group.iloc[0]

    if leg['Put/Call'] == 'P':
        return 'Naked Short Put' if leg['Quantity'] < 0 else 'Naked Long Put'
    if leg['Put/Call'] == 'C':
        return 'Naked Short Call' if leg['Quantity'] < 0 else 'Naked Long Call'

    return 'Single Leg'


# --------------------------------------------------
# TWO LEG STRUCTURES
# --------------------------------------------------
def _classify_two_legs(group):
    num_pc = group['Put/Call'].nunique()
    num_strikes = group['Strike'].nunique()
    num_expiry = group['Expiry'].nunique()

    quantities = group['Quantity'].tolist()
    both_long = quantities[0] > 0 and quantities[1] > 0
    both_short = quantities[0] < 0 and quantities[1] < 0

    # ---------------------------
    # STRADDLE
    # ---------------------------
    if num_pc == 2 and num_strikes == 1:
        if both_long:
            return 'Long Straddle'
        if both_short:
            return 'Short Straddle'
        return 'Straddle'

    # ---------------------------
    # STRANGLE
    # ---------------------------
    if num_pc == 2 and num_strikes == 2:
        if both_long:
            return 'Long Strangle'
        if both_short:
            return 'Short Strangle'
        return 'Strangle'

    # ---------------------------
    # VERTICAL SPREAD
    # ---------------------------
    if num_pc == 1 and num_strikes == 2 and num_expiry == 1:
        return _classify_vertical_spread(group)

    # ---------------------------
    # CALENDAR SPREAD
    # ---------------------------
    if num_pc == 1 and num_strikes == 1 and num_expiry == 2:
        return _classify_time_spread(group, "Calendar Spread")

    # ---------------------------
    # DIAGONAL SPREAD
    # ---------------------------
    if num_pc == 1 and num_strikes == 2 and num_expiry == 2:
        return _classify_time_spread(group, "Diagonal Spread")

    return 'Two-Leg Strategy'


# --------------------------------------------------
# CALENDAR / DIAGONAL SPREAD
# --------------------------------------------------
def _classify_time_spread(group, name):
    """Direction comes from the near leg: short near / long far = long the spread."""
    ordered = group.sort_values("Expiry")
    near = ordered.iloc[0]
    far = ordered.iloc[1]

    if near["Quantity"] < 0 and far["Quantity"] > 0:
        return f"Long {name}"

    if near["Quantity"] > 0 and far["Quantity"] < 0:
        return f"Short {name}"

    return name


# --------------------------------------------------
# VERTICAL SPREAD
# --------------------------------------------------
def _classify_vertical_spread(group):
    ordered = group.sort_values("Strike")
    leg_low = ordered.iloc[0]
    leg_high = ordered.iloc[1]

    option_type = leg_low['Put/Call']

    qty_low = leg_low['Quantity']
    qty_high = leg_high['Quantity']

    # ---------------------------
    # CALL SPREADS
    # ---------------------------
    if option_type == 'C':
        if qty_low > 0 and qty_high < 0:
            return 'Bull Call Spread'
        if qty_low < 0 and qty_high > 0:
            return 'Bear Call Spread'

    # ---------------------------
    # PUT SPREADS
    # ---------------------------
    if option_type == 'P':
        if qty_low < 0 and qty_high > 0:
            return 'Bull Put Spread'
        if qty_low > 0 and qty_high < 0:
            return 'Bear Put Spread'

    # shouldn't reach here, but just in case.
    return 'Vertical Spread'


# --------------------------------------------------
# THREE LEG STRUCTURES
# --------------------------------------------------

def _classify_three_legs(group):
    quantities = group['Quantity'].abs()

    # Ratio spread detection
    if quantities.nunique() > 1:
        return 'Ratio Spread'

    return 'Three-Leg Strategy'


# --------------------------------------------------
# FOUR LEG STRUCTURES
# --------------------------------------------------

def _classify_four_legs(group):
    num_pc = group['Put/Call'].nunique()
    num_strikes = group['Strike'].nunique()
    num_expiry = group['Expiry'].nunique()

    # ---------------------------
    # IRON CONDOR
    # ---------------------------
    if num_pc == 2 and num_strikes == 4:
        ordered = group.sort_values("Strike")
        middle = ordered.iloc[1:3]

        if (middle["Quantity"] < 0).all():
            return "Short Iron Condor"

        if (middle["Quantity"] > 0).all():
            return "Long Iron Condor"

        return "Iron Condor"

    # ---------------------------
    # IRON BUTTERFLY
    # ---------------------------
    if num_pc == 2 and num_strikes == 3 and num_expiry == 1:
        middle_strike = group.groupby("Strike").size().idxmax()
        middle = group[group["Strike"] == middle_strike]

        ordered = group.sort_values("Strike")
        s = ordered["Strike"].values

        left = s[1] - s[0]
        right = s[3] - s[2]

        if (middle["Quantity"] < 0).all():
            direction = "Short"
        elif (middle["Quantity"] > 0).all():
            direction = "Long"
        else:
            return "Iron Butterfly"

        if left == right:
            return f"{direction} Iron Butterfly"
        else:
            return f"{direction} Broken Wing Iron Butterfly"

    # ---------------------------
    # BOX SPREAD
    # ---------------------------
    if num_pc == 2 and num_strikes == 2 and num_expiry == 1:
        return 'Box Spread'

    return 'Four-Leg Strategy'


def classify_strategy_group(group):
    num_legs = len(group)
    open_indicators = group['OpenClose'].unique()

    # if there are both 'O' and 'C'
    if 'O' in open_indicators and 'C' in open_indicators:
        return 'Adjustment'

    # Check for closing trades first
    # Another check when tagged with strategyId to determine if
    # it's a partial or a true close
    if 'C' in open_indicators:
        return 'Closing Trade'

    # Classify opening strategies
    if num_legs == 1:
        return _classify_single_leg(group)

    if num_legs == 2:
        return _classify_two_legs(group)

    if num_legs == 3:
        return _classify_three_legs(group)

    if num_legs == 4:
        return _classify_four_legs(group)

    return 'Multi-Leg Strategy'


def classify_executions(df):
    """Label every execution with the structure it opened (or Adjustment/Close)."""
    strategy_mapping = df.groupby('ExecutionId').apply(
        classify_strategy_group, include_groups=False
    )
    strategy_mapping.name = 'OptionStrategy'

    return df.merge(strategy_mapping.reset_index(), on='ExecutionId', how='left')


# --------------------------------------------------
# STRATEGY GROUPING
# --------------------------------------------------


def get_valid_lot(lots, exec_time, ticker, conid):
    if not lots:
        print(f"[WARN] No owner | {ticker} conid:{conid}")
        return None

    # fast path
    if len(lots) == 1:
        return lots[0]

    # multiple lots → resolve by time
    valid_lots = [
        l for l in lots if l["time"] <= exec_time
    ]

    if not valid_lots:
        print(f"[WARN] No valid lot | {ticker} conid:{conid}")
        return None

    # FIFO
    # not the most accurate, but occurence is too small to
    # need to fine tune
    return min(valid_lots, key=lambda x: x["time"])


def assign_single_ticker_strategy_id(df):
    # Ensure chronological processing
    df["close_priority"] = df["OpenClose"].map({"C": 0, "O": 1})
    df = df.sort_values(
        ["UnderlyingSymbol", "ExecutionId", "close_priority"]
    ).copy()
    ticker = df["UnderlyingSymbol"].iloc[0]

    # --------------------------------------------------
    # Execution group signals
    # --------------------------------------------------
    exec_stats = (
        df.groupby("ExecutionId")["OpenClose"]
        .agg(
            has_open_exec=lambda s: (s == "O").any(),
            open_only_exec=lambda s: (s == "O").all()
        )
    )

    df = df.join(exec_stats, on="ExecutionId")

    # --------------------------------------------------
    #  State containers
    # --------------------------------------------------
    strategy_idx = 0
    strategy_ids = []
    lifecycle = []

    exec_strategy = {}       # ExecutionId → strategyId
    contract_lots = defaultdict(list)  # conid → { sid, qty, time }[]

    # --------------------------------------------------
    # Main state machine
    # --------------------------------------------------
    for row in df.itertuples():
        conid = row.Conid
        qty = row.Quantity
        exec_id = row.ExecutionId
        exec_time = row.exec_time

        indicator = row.OpenClose
        open_only = row.open_only_exec
        has_open_exec = row.has_open_exec

        strategy_id = None

        # -------------------------
        # OPEN ONLY → NEW STRATEGY
        # -------------------------
        if open_only:
            if exec_id in exec_strategy:
                strategy_id = exec_strategy[exec_id]
            else:
                strategy_idx += 1
                strategy_id = strategy_idx
                exec_strategy[exec_id] = strategy_id

            lifecycle_event = "OPEN"

        # -----------------------------
        # ROLL EXECUTION
        # -----------------------------
        elif has_open_exec:
            if indicator != "O":
                lots = contract_lots.get(conid, [])
                lot = get_valid_lot(lots, exec_time, ticker, conid)

                if lot is None:
                    strategy_ids.append(f"{ticker}_None")
                    lifecycle.append("ERROR")
                    continue

                strategy_id = lot["strategy"]
                exec_strategy[exec_id] = strategy_id
                lifecycle_event = "ROLL_CLOSE"

            else:
                strategy_id = exec_strategy.get(exec_id)
                if strategy_id is None:
                    print(f"[WARN] Roll open without anchor | {ticker} exec:{exec_id}")
                    strategy_ids.append(f"{ticker}_None")
                    lifecycle.append("ERROR")
                    continue

                lifecycle_event = "ROLL_OPEN"

        # -----------------------------
        # PURE CLOSE
        # -----------------------------
        else:
            lots = contract_lots.get(conid, [])
            lot = get_valid_lot(lots, exec_time, ticker, conid)

            if lot is None:
                strategy_ids.append(f"{ticker}_None")
                lifecycle.append("ERROR")
                continue

            strategy_id = lot["strategy"]
            if lot["qty"] + qty == 0:
                lifecycle_event = "TRUE_CLOSE"
            else:
                lifecycle_event = "PARTIAL_CLOSE"

        # ----------------------------------
        # Update lot tracking
        # ----------------------------------
        if indicator == "O":
            contract_lots[conid].append(
                {
                    "strategy": strategy_id,
                    "qty": qty,
                    "time": exec_time,
                }
            )
        else:
            lot["qty"] += qty
            if lot["qty"] == 0:
                contract_lots[conid].remove(lot)

        strategy_ids.append(f"{ticker}_{strategy_id}")
        lifecycle.append(lifecycle_event)

    df["strategyId"] = strategy_ids
    df["lifecycle"] = lifecycle

    return df.drop(columns=["open_only_exec", "has_open_exec", "close_priority", "exec_time"])


def assign_strategy_id(df):
    df["exec_time"] = pd.to_datetime(
        df["ExecutionId"].str.split("_").str[1],
        format="%Y-%m-%d;%H%M%S"
    )
    results = []

    for _ticker, group in df.groupby("UnderlyingSymbol", sort=False):
        results.append(assign_single_ticker_strategy_id(group))

    return pd.concat(results).sort_index()


def assign_strategy_label(df):
    """Resolve one structure label per strategy from its earliest OPEN execution.

    ``OptionStrategy`` is per-execution, so a strategy's rows also carry
    'Closing Trade' / 'Adjustment' labels. Taking the opening execution's
    structure keeps the downstream analysis independent of row order.
    """
    opens = df[df["lifecycle"] == "OPEN"].sort_values("DateTime")
    labels = opens.groupby("strategyId")["OptionStrategy"].first()

    df["StrategyLabel"] = df["strategyId"].map(labels)

    missing = df["StrategyLabel"].isna().sum()
    if missing:
        print(f"[WARN] {missing} rows belong to a strategy with no OPEN execution")
        df["StrategyLabel"] = df["StrategyLabel"].fillna(df["OptionStrategy"])

    return df


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_trades_df = load_trades()
    all_trades_df = prepare_options(all_trades_df)
    all_trades_df = classify_executions(all_trades_df)

    all_trades_df = assign_strategy_id(all_trades_df)
    all_trades_df = assign_strategy_label(all_trades_df)

    unresolved = all_trades_df["strategyId"].str.endswith("_None").sum()
    if unresolved:
        print(f"[WARN] {unresolved} rows could not be matched to a strategy")

    print(f"\nStrategies identified: {all_trades_df['strategyId'].nunique()}")
    print("Lifecycle breakdown:")
    print(all_trades_df["lifecycle"].value_counts().to_string())

    output_path = OUTPUT_DIR / "cleaned_trades.csv"
    all_trades_df.sort_values(["strategyId", "ExecutionId"]).to_csv(
        output_path, index=False
    )

    print(f"\nCleaned data saved to: {output_path}")


if __name__ == "__main__":
    main()
