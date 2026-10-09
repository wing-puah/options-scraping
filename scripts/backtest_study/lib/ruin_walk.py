"""The vectorised account walk behind `ruin_bound` — many resampled paths at once.

Registration: `research/pre-registrations/f4_deployment/ruin_bound.md`
(2026-10-09). Pure NumPy, no file I/O, no printing; the study module
(`f4_deployment/ruin_bound.py`) builds the tables and reads the results.

--- What it is ----------------------------------------------------------------
A second, INDEPENDENT copy of `account_sim.simulate()`'s ARM R loop, walked on
every path of one configuration in lock-step, one session at a time. It exists
because `simulate()` walks one book in Python, and the registered design is
millions of walks. The two are kept equal by the study's gate R2, which runs
this walk on the identity path (the series itself, in order) and compares the
positions, dollars and both drawdowns against `simulate()` on the real book.
`simulate()` is never called from here and never changed for this.

Per session `t`, in this order (the order `simulate()` uses, plus the
registered guardrails and overlays):

  1. entries, in ladder order, up to `max_per_day`: an unsizable pick burns a
     slot; F2 refuses a pick whose one contract exceeds the budget; admission
     is cash, then the per-position cap, then the net cap (static capital
     basis, `compound=False`); G-M then refuses a pick that would lift
     reserved capital past `m` x the marked equity at the close of t - 1;
  2. the overlay shock, on the session the caller names (O1, O2);
  3. the close: marked equity, ruin, the running peak, the drawdowns, and the
     G-K / G-C state the NEXT session's entries read;
  4. exits booked on their exit session (released before the next session's
     entries, as `simulate()`'s `release_before` does).

A position's exit offset and marks travel with it: it is entered at path index
`t` and exits at `t + k`, whatever block the path has moved on to.

--- What it reads -------------------------------------------------------------
Entry decisions read only static per-candidate fields (reserved, delta-notional,
the cap and floor flags) and the marks of positions already held through the
previous close. `ruin_bound`'s R4 truncation check scrambles every outcome
after a cut session and requires every decision up to it to be unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

EPS = 1e-9            # account_sim.EPS — admission's tolerant boundary
GUARDS = ("none", "M", "K", "C")
OVERLAYS = ("O0", "O1", "O2")


# ════════════════════════════════════════════════════════════════════════════
# Inputs
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Table:
    """Every candidate of one population at one budget, on one session series.

    `cand[i]` lists, in ladder order, the candidate ids whose entry session is
    series index `i` (-1 pads). Candidate arrays are indexed by id; `marks` has
    one extra all-zero row (id `C`) that empty slots read.

    `marks[c, o]` is the cumulative marked dollars `o` sessions after entry,
    for `o` in `[0, k[c]]`; `dollars[c]` is what the position books at exit.
    """
    n: int
    cand: np.ndarray            # [n, K] int64
    reserved: np.ndarray        # [C] float
    dn: np.ndarray              # [C] signed delta-notional at the sized count
    dollars: np.ndarray         # [C] booked at exit
    k: np.ndarray               # [C] exit offset, sessions after entry
    entry: np.ndarray           # [C] series index of the entry session
    unsizable: np.ndarray       # [C] bool
    over_budget: np.ndarray     # [C] bool — one contract's max loss > budget
    pp_bad: np.ndarray          # [C] bool — |dn| over the per-position cap
    marks: np.ndarray           # [C + 1, W] float
    capital: float
    max_per_day: int

    @property
    def n_cand(self) -> int:
        return len(self.reserved)

    def signal_sessions(self) -> np.ndarray:
        """Series indices carrying at least one candidate (O3's sources)."""
        return np.nonzero(self.cand[:, 0] >= 0)[0]


@dataclass(frozen=True)
class WalkCfg:
    """One configuration: a cap cell and a guardrail."""
    label: str
    net_cap: float              # x capital
    take_floor: bool            # F1 True, F2 False
    guard: str = "none"
    m: float = 0.50
    k: float = 0.25
    c: float = 0.05
    b: int = 5
    ruin_frac: float = 0.50

    def __post_init__(self):
        if self.guard not in GUARDS:
            raise ValueError(f"guard must be one of {GUARDS}, got {self.guard!r}")


# ════════════════════════════════════════════════════════════════════════════
# The sampler
# ════════════════════════════════════════════════════════════════════════════

def stationary_indices(n_src: int, H: int, L: float, n_paths: int,
                       rng: np.random.Generator) -> np.ndarray:
    """`[n_paths, H]` source indices of a stationary block bootstrap.

    Politis and Romano (1994): each step starts a new block with probability
    `1 / L`, at a uniform source index, and otherwise continues to the next
    index, wrapping from the end back to 0. Block lengths are geometric with
    mean `L`.

    `L >= n_src` is the identity: every path is `0, 1, ..., H - 1` (mod
    `n_src`), with no draw. That is the walk gate R2 compares.
    """
    if n_src <= 0 or H <= 0:
        raise ValueError("stationary_indices needs a non-empty series and horizon")
    t = np.arange(H)
    if L >= n_src:
        return np.tile(t % n_src, (n_paths, 1))
    starts = rng.integers(0, n_src, size=(n_paths, H))
    new = rng.random((n_paths, H)) < 1.0 / L
    new[:, 0] = True
    last = np.maximum.accumulate(np.where(new, t, 0), axis=1)
    rows = np.arange(n_paths)[:, None]
    return (starts[rows, last] + (t - last)) % n_src


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score 95% interval for a binomial share."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


# ════════════════════════════════════════════════════════════════════════════
# The walk
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Result:
    """Per-path outcomes of one walk. Fractions are of starting capital except
    `o2_loss`, which is of marked equity just before the shock."""
    ruined: np.ndarray
    maxdd: np.ndarray           # marked basis
    rmaxdd: np.ndarray          # realized-on-close basis
    dollars: np.ndarray         # realized by the end of H
    taken: np.ndarray
    fired: np.ndarray           # the guardrail acted at least once
    o2_loss: np.ndarray         # NaN where no shock landed
    ruin_t: np.ndarray          # first ruined session, -1 if never
    eq_shock: np.ndarray        # marked equity at the shock session (O0: at peak reserve)
    peak_resv_t: np.ndarray     # first session of maximum reserved capital
    resv_over_mtm: np.ndarray   # sessions where reserved > marked equity
    ledger_err: float           # max |cash + reserved - capital - realized|
    neg_cash: int               # sessions with cash < 0 (the margin-call proxy)
    decisions: list = field(default_factory=list)   # (path, t, cand) if recorded
    equity: np.ndarray | None = None                # [H] marked, path 0, if recorded
    reserved: np.ndarray | None = None              # [H] after entries, path 0, if recorded


def walk(tab: Table, paths: np.ndarray, cfg: WalkCfg, overlay: str = "O0",
         g: float = 0.10, shock_t: np.ndarray | None = None,
         record: bool = False) -> Result:
    """Walk every row of `paths` (series indices, `[P, H]`) through the ledger.

    Opening a position SCHEDULES its whole future on the path: its marks into
    the open-book contribution of every session it is held, and its release
    (reserve back, dollars booked, delta-notional off) on its exit session.
    Every later session then reads one column, so a session costs O(P).

    The overlays fit the same scheme because the shock session of each path is
    fixed in advance (`shock_t`, from the same paths' O0 walk): whether a
    position is open at its path's shock, and what the shock does to its marks
    and its booking, is known the moment it is opened.
    """
    if overlay not in OVERLAYS:
        raise ValueError(f"overlay must be one of {OVERLAYS}, got {overlay!r}")
    if overlay != "O0" and shock_t is None:
        raise ValueError(f"{overlay} needs shock_t from the same paths' O0 walk")
    P, H = paths.shape
    cap = float(tab.capital)
    net_abs = cfg.net_cap * cap
    ruin_line = (1.0 - cfg.ruin_frac) * cap
    W = tab.marks.shape[1]
    offs = np.arange(W)
    res_c = np.append(tab.reserved, 0.0)
    dn_c = np.append(tab.dn, 0.0)
    dol_c = np.append(tab.dollars, 0.0)
    k_c = np.append(tab.k, 0)
    uns_c = np.append(tab.unsizable, False)
    over_c = np.append(tab.over_budget, False)
    ppbad_c = np.append(tab.pp_bad, True)
    # Marks with nothing past the exit: a position adds to the open book on
    # [entry, exit] only; after that its dollars sit in `realized`.
    live = np.where(offs[None, :] <= k_c[:, None], tab.marks, 0.0)
    K = tab.cand.shape[1]
    T = H + W + 1

    f_open = np.zeros((P, T))       # scheduled marks of open positions
    f_flat = f_open.reshape(-1)     # a view, for the scatter
    x_resv = np.zeros((P, T))       # scheduled releases of reserve (negative)
    x_real = np.zeros((P, T))       # scheduled bookings
    x_net = np.zeros((P, T))        # scheduled delta-notional off
    shock_loss = np.zeros(P)        # what the shock takes, at the shock session

    cash = np.full(P, cap)
    resv = np.zeros(P)
    realized = np.zeros(P)
    net_open = np.zeros(P)
    e_prev = np.full(P, cap)
    peak = np.full(P, cap)
    rpeak = np.full(P, cap)
    maxdd = np.zeros(P)
    rmaxdd = np.zeros(P)
    ruined = np.zeros(P, dtype=bool)
    killed = np.zeros(P, dtype=bool)
    pause_until = np.zeros(P, dtype=np.int64)    # entries allowed when t >= this
    fired = np.zeros(P, dtype=bool)
    taken = np.zeros(P, dtype=np.int64)
    max_resv = np.full(P, -1.0)
    peak_resv_t = np.full(P, -1, dtype=np.int64)
    o2_loss = np.full(P, np.nan)
    ruin_t = np.full(P, -1, dtype=np.int64)
    eq_shock = np.full(P, np.nan)
    over = np.zeros(P, dtype=np.int64)
    ledger_err = 0.0
    neg_cash = 0
    decisions: list = []
    eq_rec = np.zeros(H) if record else None
    resv_rec = np.zeros(H) if record else None

    for t in range(H):
        src = paths[:, t]
        allowed = np.ones(P, dtype=bool)
        if cfg.guard == "K":
            allowed &= ~killed
        elif cfg.guard == "C":
            allowed &= t >= pause_until
        n_today = np.zeros(P, dtype=np.int64)

        # 1. entries — only the paths whose source session lists a j-th pick
        cand_t = tab.cand[src]
        for j in range(K):
            rows = np.nonzero(cand_t[:, j] >= 0)[0]
            if rows.size == 0:
                break
            cc = cand_t[rows, j]
            act = allowed[rows] & (n_today[rows] < tab.max_per_day)
            uns = act & uns_c[cc]
            n_today[rows] += uns
            act &= ~uns
            if not cfg.take_floor:
                act &= ~over_c[cc]
            r = res_c[cc]
            d = dn_c[cc]
            ok = (act & (r <= cash[rows] + EPS) & ~ppbad_c[cc]
                  & (np.abs(net_open[rows] + d) <= net_abs + EPS))
            if cfg.guard == "M":
                fits = (resv[rows] + r) <= cfg.m * e_prev[rows] + EPS
                fired[rows] |= ok & ~fits
                ok &= fits
            if not ok.any():
                continue
            sel = np.nonzero(ok)[0]
            rows, cr, rr, dr = rows[sel], cc[sel], r[sel], d[sel]
            kr = k_c[cr]
            wb = int(kr.max()) + 1
            m = live[cr, :wb]
            book = dol_c[cr]
            if overlay != "O0":
                m, book = _shock(m, book, rr, dr, kr, shock_t[rows] - t, offs[:wb],
                                 overlay, g, shock_loss, rows, live[cr, :wb])
            flat = (rows * T + t)[:, None] + offs[None, :wb]
            f_flat[flat] += m
            ex = t + kr
            x_resv[rows, ex] -= rr
            x_real[rows, ex] += book
            x_net[rows, ex] -= dr
            cash[rows] -= rr
            resv[rows] += rr
            net_open[rows] += dr
            n_today[rows] += 1
            taken[rows] += 1
            if record:
                decisions.extend((int(p), t, int(c)) for p, c in zip(rows, cr))

        if record:
            resv_rec[t] = resv[0]
        upd = resv > max_resv + EPS
        max_resv = np.where(upd, resv, max_resv)
        peak_resv_t = np.where(upd, t, peak_resv_t)

        # 2-3. the close
        eq = cap + realized + f_open[:, t]
        if overlay != "O0":
            hit = shock_t == t
            if hit.any():
                eq_shock[hit] = eq[hit]
                with np.errstate(divide="ignore", invalid="ignore"):
                    o2_loss[hit] = shock_loss[hit] / (eq[hit] + shock_loss[hit])
        else:
            eq_shock = np.where(upd, eq, eq_shock)
        if record:
            eq_rec[t] = eq[0]
        now = eq <= ruin_line + EPS
        ruin_t = np.where(now & ~ruined, t, ruin_t)
        ruined |= now
        peak = np.maximum(peak, eq)
        maxdd = np.maximum(maxdd, (peak - eq) / cap)
        over += resv > eq + EPS
        if cfg.guard == "K":
            trip = ~killed & (eq <= peak * (1.0 - cfg.k) + EPS)
            killed |= trip
            fired |= trip
        elif cfg.guard == "C":
            trip = (e_prev - eq) >= cfg.c * e_prev - EPS
            pause_until = np.where(trip, t + 1 + cfg.b, pause_until)
            fired |= trip

        # 4. exits booked at this close
        rel = x_resv[:, t]
        bk = x_real[:, t]
        cash += bk - rel
        resv += rel
        realized += bk
        net_open += x_net[:, t]

        er = cap + realized
        rpeak = np.maximum(rpeak, er)
        rmaxdd = np.maximum(rmaxdd, (rpeak - er) / cap)
        ledger_err = max(ledger_err, float(np.max(np.abs(cash + resv - cap - realized))))
        neg_cash += int(np.sum(cash < -EPS))
        e_prev = eq

    return Result(ruined=ruined, maxdd=maxdd, rmaxdd=rmaxdd, dollars=realized,
                  taken=taken, fired=fired, o2_loss=o2_loss, ruin_t=ruin_t,
                  eq_shock=eq_shock,
                  peak_resv_t=np.where(max_resv > 0, peak_resv_t, -1),
                  resv_over_mtm=over, ledger_err=ledger_err, neg_cash=neg_cash,
                  decisions=decisions, equity=eq_rec, reserved=resv_rec)


def _shock(m, book, res, dn, k, o_s, offs, overlay, g, shock_loss, rows, raw):
    """Apply a path's shock to positions opened now, if they are open at it.

    `o_s` is each position's offset to its path's shock session (negative when
    the shock came before, or there is none). A position is hit when
    `0 <= o_s <= k`. From that offset on, O1 lowers every mark by the smaller
    of the max loss and `dn x g` (long delta only), floored at minus the max
    loss; O2 marks it at minus the max loss. The booking at exit moves the
    same way. `shock_loss` gathers, per path, what the shock takes on its own
    session.
    """
    hit = (o_s >= 0) & (o_s <= k)
    if not hit.any():
        return m, book
    if overlay == "O1":
        shk = np.where(dn > 0, np.minimum(res, dn * g), 0.0)
        hit &= shk > 0
        if not hit.any():
            return m, book
    after = hit[:, None] & (offs[None, :] >= o_s[:, None]) & (offs[None, :] <= k[:, None])
    if overlay == "O1":
        adj = np.maximum(m - shk[:, None], -res[:, None])
        new_book = np.where(hit, np.maximum(book - shk, -res), book)
    else:
        adj = np.broadcast_to(-res[:, None], m.shape)
        new_book = np.where(hit, -res, book)
    m2 = np.where(after, adj, m)
    idx = np.nonzero(hit)[0]
    o = o_s[idx]
    shock_loss[rows[idx]] += raw[idx, o] - m2[idx, o]
    return m2, new_book


# ════════════════════════════════════════════════════════════════════════════
# One configuration's resample, as a worker task
# ════════════════════════════════════════════════════════════════════════════

def _pct(vals: np.ndarray, q: float) -> float:
    """Linear-interpolated percentile of the finite values — the same rule as
    `forward_drawdown.pctile` — NaN if none."""
    v = vals[np.isfinite(vals)]
    return float(np.percentile(v, q)) if v.size else float("nan")


def summarize(res: Result, guard: str) -> dict:
    """The registered per-cell metrics of one walk. Counts and percentiles only."""
    n = len(res.ruined)
    k = int(res.ruined.sum())
    lo, hi = wilson(k, n)
    return dict(
        n=n, n_ruin=k, p_ruin=k / n if n else float("nan"), ci=(lo, hi),
        dd50=_pct(res.maxdd, 50), dd95=_pct(res.maxdd, 95), dd99=_pct(res.maxdd, 99),
        rdd95=_pct(res.rmaxdd, 95),
        dol50=_pct(res.dollars, 50), dol5=_pct(res.dollars, 5),
        taken50=_pct(res.taken.astype(float), 50),
        fired=float(res.fired.mean()) if n else float("nan"),
        ruin_unfired=int((res.ruined & ~res.fired).sum()) if guard == "K" else None,
        o2_99=_pct(res.o2_loss, 99),
        n_shocked=int(np.isfinite(res.o2_loss).sum()),
        over_share=float((res.resv_over_mtm > 0).mean()) if n else float("nan"),
        ledger_err=res.ledger_err, neg_cash=res.neg_cash)


def resample_paths(tab: Table, L: float, n_paths: int, seed: int, key: tuple,
                   live_density: bool = False) -> np.ndarray:
    """The registered index stream for one (budget, population, L).

    One stream per key, shared by every configuration (common random numbers)
    and by O0, O1 and O2. O3 (`live_density`) draws its own stream over the
    sessions that carry a candidate list; the path is still `tab.n` long.
    """
    rng = np.random.default_rng([seed, *key, 3 if live_density else 0])
    if not live_density:
        return stationary_indices(tab.n, tab.n, L, n_paths, rng)
    src = tab.signal_sessions()
    return src[stationary_indices(len(src), tab.n, L, n_paths, rng)]


def run_task(tab: Table, cfg: WalkCfg, L: float, n_paths: int, seed: int,
             key: tuple, g: float) -> dict:
    """O0, O1, O2 and O3 for one configuration at one block length."""
    paths = resample_paths(tab, L, n_paths, seed, key)
    r0 = walk(tab, paths, cfg)
    shock_t = r0.peak_resv_t
    r1 = walk(tab, paths, cfg, overlay="O1", g=g, shock_t=shock_t)
    r2 = walk(tab, paths, cfg, overlay="O2", shock_t=shock_t)
    r3 = walk(tab, resample_paths(tab, L, n_paths, seed, key, live_density=True), cfg)
    out = {o: summarize(r, cfg.guard) for o, r in
           (("O0", r0), ("O1", r1), ("O2", r2), ("O3", r3))}
    out["R5"] = overlay_order(r0, r1, r2, shock_t)
    return out


def overlay_order(r0: Result, r1: Result, r2: Result, shock_t: np.ndarray) -> dict:
    """Gate R5 path by path, on what must hold by construction.

    The three walks are identical up to the shock session and the shock only
    lowers equity, so on every shocked path: marked equity at the shock is
    O2 <= O1 <= O0, and ruin at or before the shock under O0 implies it under
    O1, which implies it under O2. After the shock the walks differ (less cash,
    and a guardrail reacting), so the order of the full-H shares is not a
    property of a correct walk and is only printed.
    """
    shocked = shock_t >= 0

    def by(r):
        return (r.ruin_t >= 0) & (r.ruin_t <= shock_t) & shocked
    b0, b1, b2 = by(r0), by(r1), by(r2)
    tol = 1e-6
    eq_bad = shocked & ((r2.eq_shock > r1.eq_shock + tol) | (r1.eq_shock > r0.eq_shock + tol))
    return dict(paths=int(shocked.sum()), ruin_bad=int(((b0 & ~b1) | (b1 & ~b2)).sum()),
                eq_bad=int(eq_bad.sum()))
