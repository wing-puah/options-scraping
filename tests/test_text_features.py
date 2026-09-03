"""Unit tests for `scripts/backtest_study/f1_selection/text_features.py`.

Four things are pinned here, and the first is the one the pre-registration
names by test id: the ARM B labeller's input carries NO outcome and NO
identity. The rest are the arithmetic the verdict block rests on — the
Benjamini-Hochberg step-up, the tercile/binary split, the CANDIDATE
conjunction, and the labeller's response parser.

Nothing here calls `claude`, Drive, or Sheets: the labeller's subprocess is
monkeypatched wholesale.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection import text_features as TF  # noqa: E402


# ── the leakage guard ───────────────────────────────────────────────────────

def _corpus_row(**over):
    """A corpus row shaped like `text_corpus.load_corpus` emits, outcome and all."""
    row = dict(
        date="2025-03-14", ticker="NVDA", structure="bull_call_spread", tier="B",
        source="real", credit=False, post13c=True,
        R=0.83, E=1.20, R_dol=415.0, E_dol=600.0, mfe=1.4, mae=-0.3,
        days_held=12, exit_reason="pt", score_total=31.0, price_vector=0.02,
        text={
            "regime": "risk-on",
            "signal": "[FLOW] NVDA 120C sweeps, $4.68M premium 2025-03-14\n"
                      "counter: NVDA put wall at 110\n[PRICE] NVDA holds 118",
            "play": "[DIRECTIONAL]\nTF | bull call spread 120/130 Mar 21 (7 DTE) | "
                    "NVDA momentum continues into the March 2025 print\n"
                    "Alt: NVDA fades back to 110 if the sweep is a hedge",
            "trigger": "no entry before NVDA clears 118 on a closing basis",
            "invalidation": "NVDA closes below 110, or the March 21 2025 call flow reverses",
            "horizon": "swing", "created_datetime": "2025-03-14T13:05:00", "joined": True,
        },
    )
    row["features"] = TF.TC._features_with_parse(row["text"])
    row.update(over)
    return row


def test_label_input_carries_no_outcome_key():
    """The registration's named guard: the labeller sees the five text fields
    and nothing else — no outcome, no price, no structure result, no date, no
    ticker — and the cache key is a function of that payload alone."""
    row = _corpus_row()
    payload = TF.text_payload(row)

    assert set(payload) == set(TF.TEXT_PAYLOAD_KEYS)
    assert not (set(payload) & TF.FORBIDDEN_PAYLOAD_KEYS)

    blob = json.dumps(payload, sort_keys=True)
    # No outcome number, and no identity, survives into the payload text.
    for leak in ("0.83", "1.2", "415", "NVDA", "2025-03-14", "Mar 21", "2025", "pt"):
        assert leak not in blob, f"{leak!r} leaked into the labeller payload"

    # The cache key is the payload and only the payload: changing an outcome
    # column cannot move it, changing a text field must.
    h0 = TF.payload_hash(payload)
    assert h0 == TF.payload_hash(TF.text_payload(_corpus_row(R=-1.0, tier="A",
                                                             source="tweak")))
    moved = _corpus_row()
    moved["text"]["invalidation"] = "something else entirely"
    moved["features"] = TF.TC._features_with_parse(moved["text"])
    assert TF.payload_hash(TF.text_payload(moved)) != h0


@pytest.mark.parametrize("bad_key", ["R", "E", "date", "ticker", "score_total", "tier"])
def test_payload_carrying_an_outcome_or_identity_key_raises(bad_key):
    payload = {k: "" for k in TF.TEXT_PAYLOAD_KEYS}
    payload[bad_key] = 1.23
    with pytest.raises(ValueError, match="LEAKAGE GUARD"):
        TF.assert_clean_payload(payload)
    with pytest.raises(ValueError, match="LEAKAGE GUARD"):
        TF.payload_hash(payload)


def test_payload_with_an_unexpected_key_raises():
    payload = {k: "" for k in TF.TEXT_PAYLOAD_KEYS}
    payload["notes"] = "hi"
    with pytest.raises(ValueError, match="LEAKAGE GUARD"):
        TF.assert_clean_payload(payload)


def test_scrub_identity_removes_ticker_and_dates():
    out = TF.scrub_identity("AMD breaks 145 by 2026-04-17, or $AMD fades into Apr 17, 2026",
                            "AMD")
    assert "AMD" not in out
    assert "2026" not in out
    assert "Apr 17" not in out
    assert "145" in out                      # a price level is NOT identity


# ── Benjamini-Hochberg ──────────────────────────────────────────────────────

def test_bh_reject_on_a_synthetic_p_vector():
    # m = 5, q = 0.10 -> thresholds .02 .04 .06 .08 .10; the largest k with
    # p_(k) <= q*k/m is k = 2 (p=.030 <= .040), so the two smallest reject.
    p = [0.001, 0.030, 0.070, 0.400, 0.900]
    assert TF.bh_reject(p, 0.10) == [True, True, False, False, False]


def test_bh_step_up_rejects_below_a_later_passing_rank():
    # p_(1)=.05 fails .02, but p_(2)=.03? -- unsorted input must be handled, and
    # a step-up procedure rejects EVERYTHING below the largest passing rank.
    p = [0.039, 0.001, 0.500]
    assert TF.bh_reject(p, 0.10) == [True, True, False]


def test_bh_rejects_nothing_when_no_p_clears():
    assert TF.bh_reject([0.4, 0.6, 0.99], 0.10) == [False, False, False]


def test_bh_ignores_nan_p_values():
    out = TF.bh_reject([float("nan"), 0.001], 0.10)
    assert out == [False, True]


def test_bh_on_an_empty_vector():
    assert TF.bh_reject([], 0.10) == []


# ── tercile / binary split logic ────────────────────────────────────────────

def _feat_row(date="2025-01-02", **feats):
    return {"date": date, "features": dict(feats), "R": 0.0}


def test_tercile_edges_are_cut_on_the_full_book_and_ignore_nan():
    rows = [_feat_row(thesis_len=v) for v in range(1, 10)]        # 1..9
    rows.append(_feat_row(thesis_len=None))
    edges = TF.tercile_edges(rows, "thesis_len")
    assert edges == (4.0, 7.0)                # v[9//3]=v[3]=4, v[2*9//3]=v[6]=7


def test_continuous_level_splits_T1_T2_T3_and_refuses_a_missing_value():
    edges = (4.0, 7.0)
    assert TF.continuous_level(_feat_row(thesis_len=1), "thesis_len", edges) == "T1"
    assert TF.continuous_level(_feat_row(thesis_len=4), "thesis_len", edges) == "T1"
    assert TF.continuous_level(_feat_row(thesis_len=5), "thesis_len", edges) == "T2"
    assert TF.continuous_level(_feat_row(thesis_len=7), "thesis_len", edges) == "T2"
    assert TF.continuous_level(_feat_row(thesis_len=8), "thesis_len", edges) == "T3"
    # NOT EVALUABLE, never imputed.
    assert TF.continuous_level(_feat_row(thesis_len=None), "thesis_len", edges) is None
    assert TF.continuous_level(_feat_row(thesis_len=5), "thesis_len", None) is None


def test_degenerate_terciles_fall_back_to_the_declared_binary_cut():
    rows = [_feat_row(hallucination_rate=0.0) for _ in range(20)]
    rows[0]["features"]["hallucination_rate"] = 0.5
    for r in rows:
        r["hallucination_rate"] = r["features"]["hallucination_rate"]
    edges = TF.tercile_edges(rows, "hallucination_rate")
    assert edges == (0.0, 0.0)                # degenerate: a spike at zero
    row_hi = {"hallucination_rate": 0.5, "features": {}}
    row_lo = {"hallucination_rate": 0.0, "features": {}}
    assert TF.continuous_level(row_hi, "hallucination_rate", edges, True) == "T3"
    assert TF.continuous_level(row_lo, "hallucination_rate", edges, True) == "T1"


def test_binary_feature_split_labels():
    assert TF._f_invalidation_type({"invalidation_type": "price"}) == "price_only"
    for other in ("mixed", "flow", "macro", "none"):
        assert TF._f_invalidation_type({"invalidation_type": other}) == "mixed"
    assert TF._f_invalidation_type({}) is None

    assert TF._f_inside_strikes({"invalidation_inside_strikes": True}) == "inside"
    assert TF._f_inside_strikes({"invalidation_inside_strikes": False}) == "outside"
    assert TF._f_inside_strikes({"invalidation_inside_strikes": None}) is None

    assert TF._f_trigger_conditional({"trigger_conditional": True}) == "conditional"
    assert TF._f_trigger_conditional({"trigger_conditional": False}) == "unconditional"


def test_label_level_refuses_a_level_outside_the_frozen_set():
    row = {"labels": {"evidence_quality": "3", "thesis_type": "wildcard"}}
    assert TF.label_level(row, "evidence_quality") == "3"
    assert TF.label_level(row, "thesis_type") is None
    assert TF.label_level({"labels": None}, "one_sided") is None


# ── the CANDIDATE conjunction ───────────────────────────────────────────────

def _cell_rows(n_dates, per_date, r_value, year="2025", month_a="01", month_b="07"):
    """`n_dates` dates, `per_date` rows each, every R = `r_value`, spread across
    two months in one year and clear of both dominant windows."""
    out = []
    for i in range(n_dates):
        mm = month_a if i % 2 == 0 else month_b
        d = f"{year}-{mm}-{(i % 28) + 1:02d}"
        for j in range(per_date):
            out.append({"date": d, "R": r_value + (0.01 if j else -0.01),
                        "source": "real" if j % 2 == 0 else "tweak"})
    return out


def test_conjunction_passes_on_a_clean_synthetic_cell():
    # Two clearly separated groups, over both calendar years, both pricing
    # tiers, no dominant-window dependence, comfortably over both floors.
    a = _cell_rows(20, 2, 1.0, "2024") + _cell_rows(20, 2, 1.0, "2025")
    b = _cell_rows(20, 2, -1.0, "2024") + _cell_rows(20, 2, -1.0, "2025")
    t = TF.cell_test(a, b)
    t["bh_ok"] = True
    assert t["floor_ok"], t
    assert t["ci_ok"] and t["loo_ok"] and t["cuts_ok"] and t["ex_both_ok"]
    assert t["year_ok"] and t["tier_ok"]
    assert TF.is_candidate(t)
    assert "1 CI=PASS" in TF.criteria_vector(t)


def test_conjunction_fails_when_the_sign_flips_across_years():
    # Same size and the same floors, but 2024 says one thing and 2025 the
    # other: criterion 4 must fail, and the whole conjunction with it.
    a = _cell_rows(20, 2, 1.0, "2024") + _cell_rows(20, 2, -1.0, "2025")
    b = _cell_rows(20, 2, -1.0, "2024") + _cell_rows(20, 2, 1.0, "2025")
    t = TF.cell_test(a, b)
    t["bh_ok"] = True
    assert t["floor_ok"]
    assert not t["year_ok"]
    assert not TF.is_candidate(t)


def test_conjunction_fails_on_bh_alone():
    a = _cell_rows(20, 2, 1.0, "2024") + _cell_rows(20, 2, 1.0, "2025")
    b = _cell_rows(20, 2, -1.0, "2024") + _cell_rows(20, 2, -1.0, "2025")
    t = TF.cell_test(a, b)
    t["bh_ok"] = False
    assert not TF.is_candidate(t), "a raw CI that fails BH is NULL, not CANDIDATE"


def test_underpowered_cell_evaluates_no_criterion():
    a = _cell_rows(5, 2, 1.0)
    b = _cell_rows(5, 2, -1.0)
    t = TF.cell_test(a, b)
    assert not t["floor_ok"]
    assert t["n_rows"] == 20 and t["n_dates"] == 5
    for _, key in TF.CRITERIA_ORDER:
        if key != "floor_ok":
            assert not t[key], f"{key} was evaluated on an UNDERPOWERED cell"
    assert not TF.is_candidate(t)


def test_floor_needs_both_rows_and_dates():
    # 60 rows but only 10 dates -> under the DATE floor.
    t = TF.cell_test(_cell_rows(10, 3, 1.0), _cell_rows(10, 3, -1.0))
    assert t["n_rows"] == 60 and t["n_dates"] == 10 and not t["floor_ok"]
    # 30 dates but only 30 rows -> under the ROW floor.
    t = TF.cell_test(_cell_rows(30, 1, 1.0)[:30], _cell_rows(30, 1, -1.0)[:20])
    assert t["n_rows"] < TF.MIN_ROWS and not t["floor_ok"]


def test_floor_binds_on_each_LEVEL_not_on_the_pair():
    """The registration declares the floor on a cell = feature LEVEL x structure
    x tier, so a 200-vs-1 split is UNDERPOWERED however many rows the pair has."""
    a = _cell_rows(40, 5, 1.0)                 # 200 rows / 40 dates
    b = _cell_rows(1, 1, -1.0)                 # 1 row / 1 date
    t = TF.cell_test(a, b)
    assert t["n_rows"] >= TF.MIN_ROWS and t["n_dates"] >= TF.MIN_AFFECTED_DATES
    assert not t["floor_ok"], "a one-row group must never clear the floor"
    assert not TF.is_candidate(t)


def test_one_empty_group_is_never_powered():
    t = TF.cell_test(_cell_rows(30, 3, 1.0), [])
    assert not t["floor_ok"]


# ── the labeller's response parser ──────────────────────────────────────────

FIXTURE_RESPONSE = """```json
[
  {"i": 1, "thesis_type": "flow-follow", "evidence_quality": "3",
   "confidence_language": "assertive", "one_sided": "substantive",
   "invalidation_concreteness": "3"},
  {"i": 2, "thesis_type": "hedge", "evidence_quality": "1",
   "confidence_language": "hedged", "one_sided": "token",
   "invalidation_concreteness": "2"},
  {"i": 3, "thesis_type": "NOT-A-LEVEL", "evidence_quality": "2",
   "confidence_language": "neutral", "one_sided": "token",
   "invalidation_concreteness": "1"}
]
```"""


def test_parse_label_response_validates_levels_and_drops_the_invalid_row():
    out = TF.parse_label_response(FIXTURE_RESPONSE, 3)
    assert set(out) == {1, 2}, "an out-of-vocabulary level must leave the row UNLABELLED"
    assert out[1]["thesis_type"] == "flow-follow"
    assert out[1]["invalidation_concreteness"] == "3"
    assert out[2]["confidence_language"] == "hedged"


def test_parse_label_response_tolerates_prose_around_the_array():
    raw = 'Here you go:\n[{"i":1,"thesis_type":"vol","evidence_quality":"2",' \
          '"confidence_language":"neutral","one_sided":"token",' \
          '"invalidation_concreteness":"2"}]\nHope that helps.'
    assert TF.parse_label_response(raw, 1)[1]["thesis_type"] == "vol"


def test_parse_label_response_on_garbage_returns_nothing():
    assert TF.parse_label_response("sorry, I cannot help with that", 3) == {}
    assert TF.parse_label_response("[{not json", 3) == {}
    assert TF.parse_label_response(None, 3) == {}


def test_label_rows_caches_batches_and_never_calls_twice(tmp_path, monkeypatch):
    rows = [_corpus_row(), _corpus_row()]
    rows[1]["text"]["invalidation"] = "a different falsifier below 100"
    rows[1]["features"] = TF.TC._features_with_parse(rows[1]["text"])

    seen = []

    def fake_invoke(prompt):
        seen.append(prompt)
        n = prompt.count("### item ")
        return json.dumps([
            {"i": i, "thesis_type": "flow-follow", "evidence_quality": "2",
             "confidence_language": "neutral", "one_sided": "token",
             "invalidation_concreteness": "2"} for i in range(1, n + 1)])

    st = TF.label_rows(rows, cache_dir=tmp_path, mode="run", invoke=fake_invoke,
                       log=lambda *a: None)
    assert st["calls"] == 1 and st["unique"] == 2 and st["labelled"] == 2
    assert all(r["labels"]["thesis_type"] == "flow-follow" for r in rows)
    assert len(list(tmp_path.glob("*.json"))) == 2
    # The prompt the labeller saw carries no ticker and no date.
    assert "NVDA" not in seen[0] and "2025-03-14" not in seen[0]

    # Resumable: a second pass is pure cache, and `cached` mode calls nothing.
    st2 = TF.label_rows(rows, cache_dir=tmp_path, mode="cached",
                        invoke=lambda p: pytest.fail("cached mode must not call"),
                        log=lambda *a: None)
    assert st2["calls"] == 0 and st2["cached"] == 2 and st2["labelled"] == 2


def test_label_rows_retries_once_then_leaves_the_row_unlabelled(tmp_path):
    rows = [_corpus_row()]
    calls = []

    def bad_invoke(prompt):
        calls.append(prompt)
        return "no json here"

    st = TF.label_rows(rows, cache_dir=tmp_path, mode="run", invoke=bad_invoke,
                       log=lambda *a: None)
    assert len(calls) == 2 and st["retries"] == 1
    assert st["failures"] == 1 and st["labelled"] == 0 and st["invalid"] == 1
    assert rows[0]["labels"] is None


def test_label_rows_skip_mode_attaches_nothing(tmp_path):
    rows = [_corpus_row()]
    st = TF.label_rows(rows, cache_dir=tmp_path, mode="skip",
                       invoke=lambda p: pytest.fail("skip mode must not call"))
    assert st["calls"] == 0 and rows[0]["labels"] is None


# ── ARM C mechanics ─────────────────────────────────────────────────────────

def test_gate_replay_veto_and_demotion_move_the_picked_set():
    rows = []
    for i in range(30):
        d = f"2025-0{1 + i % 6}-{(i % 28) + 1:02d}"
        rows.append(dict(_uid=len(rows), date=d, tier="A", source="real", R=-1.0,
                         score_total=40, post13c=True, bad=True))
        for j in range(3):
            rows.append(dict(_uid=len(rows), date=d, tier="B", source="real", R=1.0,
                             score_total=10, post13c=True, bad=False))

    def level(r):
        return "BAD" if r["bad"] else "OK"

    veto = TF.gate_replay(rows, level, "BAD", "veto")
    demote = TF.gate_replay(rows, level, "BAD", "demote")
    # The tier-A loser leads every day's ladder; both gates drop it.
    assert veto["mean_base"] < veto["mean_gate"]
    assert veto["n_affected_dates"] == 30
    # A one-step demotion sends it to tier C, which is never deployed, so on
    # this book the demotion and the veto coincide.
    assert demote["n_gate"] == veto["n_gate"]
    assert TF.DEMOTE_ONE_STEP["A"] == "B" and TF.DEMOTE_ONE_STEP["B"] == "C"


def test_gate_never_fires_on_a_not_evaluable_level():
    rows = [dict(_uid=i, date=f"2025-01-{i + 1:02d}", tier="A", source="real",
                 R=1.0, score_total=1, post13c=True) for i in range(10)]
    g = TF.gate_replay(rows, lambda r: None, "BAD", "veto")
    assert g["n_base"] == g["n_gate"] == 10
    assert g["n_affected_dates"] == 0


def test_designed_refusal_codes_are_a_plain_set_literal():
    """`run.py` finds these by AST parse; a frozenset(...) call is invisible to
    `ast.literal_eval` and the refusal would be misfiled as a failure."""
    src = (ROOT / "scripts" / "backtest_study" / "f1_selection"
           / "text_features.py").read_text()
    import ast
    tree = ast.parse(src)
    found = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "DESIGNED_REFUSAL_EXIT_CODES" for t in node.targets):
            found = ast.literal_eval(node.value)
    assert found == {2, 3}
