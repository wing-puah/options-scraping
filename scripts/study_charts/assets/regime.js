/* account_sim regime readout — SVG chart layer.
 *
 * Draws window.__ACCOUNT_SIM_REGIME__, which the Python renderer embeds. Every
 * number in it was recomputed from the study's positions export and reconciled
 * against the study's own DEPLOYED BOOK BY REGIME section before this page was
 * written, so nothing here is this file's arithmetic.
 *
 * What this page must never do is turn a description into a claim. account_sim
 * pre-registers no cut by regime; the cells are small and were chosen after
 * seeing the book. So every cell carries its n, thin cells say so, and the
 * banner says it once more in words.
 */
(function () {
  "use strict";

  var DATA = window.__ACCOUNT_SIM_REGIME__;
  var state = { population: "primary" };

  var K = window.__STUDY_KIT__;
  var el = K.el, h = K.h, money = K.money, signed = K.signed, pct = K.pct,
      hideTip = K.hideTip, panel = K.panel, buildTable = K.buildTable,
      columnChart = K.columnChart, divergingBars = K.divergingBars,
      tile = K.tile, section = K.section, chartHost = K.chartHost,
      matrix = K.matrix;

  var THIN_N = 10;

  // ---------- shaping ----------

  function label(cell) { return cell.thin ? cell.cell + " †" : cell.cell; }

  function uniq(values) {
    var seen = {}, out = [];
    values.forEach(function (v) { if (!seen[v]) { seen[v] = 1; out.push(v); } });
    return out;
  }

  /* Cells ordered by how much of the book they hold, biggest first — the order
   * a reader asking "where did it deploy" wants, and stable across arms. */
  function cellsBySize(rows) {
    var total = {};
    rows.forEach(function (r) { total[r.cell] = (total[r.cell] || 0) + r.n; });
    return Object.keys(total).sort(function (a, b) {
      return total[b] - total[a] || (a < b ? -1 : 1);
    });
  }

  function rollup(rows, cell) {
    var mine = rows.filter(function (r) { return r.cell === cell; });
    var n = mine.reduce(function (a, r) { return a + r.n; }, 0);
    return {
      cell: cell,
      n: n,
      thin: n < THIN_N,
      dollars: mine.reduce(function (a, r) { return a + r.dollars; }, 0),
      // Weighted by n: the per-structure means are means of different-sized
      // groups, so a mean of the means would quietly re-weight the book.
      meanR: n ? mine.reduce(function (a, r) { return a + r.meanR * r.n; }, 0) / n : 0,
      win: n ? mine.reduce(function (a, r) { return a + r.win * r.n; }, 0) / n : 0
    };
  }

  function find(rows, cell, structure) {
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].cell === cell && rows[i].structure === structure) return rows[i];
    }
    return null;
  }

  // ---------- panels ----------

  function deploymentMatrix(sec, rows, what) {
    var cells = cellsBySize(rows);
    var structures = uniq(rows.map(function (r) { return r.structure; })).sort();
    var p = panel("Where the book deployed — positions by " + what + " and structure",
      "Colour is the position count, nothing else. An empty tile is a pairing the "
      + "book never took, which is a different fact from one it took and lost money on.",
      { table: true });
    matrix(chartHost(p), p.table, {
      title: "Positions deployed by " + what + " and structure",
      rowTitle: what.toUpperCase(),
      valueName: "positions",
      cols: structures,
      rows: cells.map(function (cell) {
        return {
          label: cell,
          cells: structures.map(function (s) {
            var r = find(rows, cell, s);
            return r ? {
              value: r.n,
              sub: money(r.dollars) + (r.thin ? "  †" : ""),
              note: "mean R " + signed(r.meanR) + ", win " + pct(r.win)
                + (r.thin ? " — thin" : "")
            } : null;
          })
        };
      }),
      fmt: String,
      sub: function (c) { return c.sub; },
      footnote: "† marks a cell holding fewer than " + THIN_N + " positions.",
      tableCols: [what, "Structure", "Positions", "Realized", "Mean R", "Win"],
      tableRows: rows.map(function (r) {
        return [label(r), r.structure, r.n, money(r.dollars), signed(r.meanR), pct(r.win)];
      })
    });
    sec.appendChild(p.figure);
  }

  function outcomePanels(sec, rows, what) {
    var rolled = cellsBySize(rows).map(function (c) { return rollup(rows, c); });
    var stack = h("div", "stack");

    var p = panel("Mean R by " + what,
      "Structures pooled inside each cell, weighted by position count. Post-hoc: "
      + "the study tested no regime split, and these cells are small.", { table: true });
    divergingBars(chartHost(p), p.table, {
      rows: rolled.map(function (r) {
        return { label: label(r), value: r.meanR, sub: "n=" + r.n + " · win " + pct(r.win) };
      }),
      valueFmt: function (v) { return signed(v); },
      axisTitle: "MEAN R",
      tableCols: [what, "Positions", "Mean R", "Win rate", "Realized"],
      tableRows: rolled.map(function (r) {
        return [label(r), r.n, signed(r.meanR), pct(r.win), money(r.dollars)];
      })
    });
    stack.appendChild(p.figure);

    p = panel("Realized dollars by " + what,
      "The same cells by money rather than by rate. A cell can lead on mean R and "
      + "trail here, because position size is set by the risk budget, not by the regime.",
      { table: true });
    divergingBars(chartHost(p), p.table, {
      rows: rolled.map(function (r) {
        return { label: label(r), value: r.dollars, sub: "n=" + r.n };
      }),
      valueFmt: function (v) { return money(v); },
      axisTitle: "REALIZED $"
    });
    stack.appendChild(p.figure);
    sec.appendChild(stack);
  }

  function censusPanel(sec, census) {
    var p = panel("Capital reserved per position, by mechanical cell",
      "What one position in each cell cost the account against the intended risk budget. "
      + "Position count, tier mix and delta-notional are on the bar and in the table.",
      { table: true });
    columnChart(chartHost(p), p.table, {
      rows: census.map(function (c) {
        return {
          label: c.cell, value: c.reserved,
          sub: c.n + " positions · tier A " + c.tierA + " · B " + c.tierB
               + " · avg delta-notional " + money(c.dn)
        };
      }),
      valueFmt: function (v) { return money(v); },
      valueName: "avg reserved",
      axisTitle: "AVG CAPITAL RESERVED PER POSITION",
      tableCols: ["Mechanical cell", "Positions", "Tier A", "Tier B",
                  "Avg reserved", "Avg delta-notional"],
      tableRows: census.map(function (c) {
        return [c.cell, c.n, c.tierA, c.tierB, money(c.reserved), money(c.dn)];
      })
    });
    sec.appendChild(p.figure);
  }

  function skipsPanel(sec, skips, considered) {
    var cells = uniq(skips.map(function (s) { return s.cell; })).sort();
    var buckets = uniq(skips.map(function (s) { return s.bucket; })).sort();
    var by = {};
    skips.forEach(function (s) { by[s.cell + "|" + s.bucket] = s.n; });
    var p = panel("Every candidate, by mechanical cell and outcome",
      "The account considered " + considered + " candidates in this population. "
      + "`taken` is the deployed book; the rest are what the caps could not fit — "
      + "not what the ladder declined to pick.", { table: true });
    matrix(chartHost(p), p.table, {
      title: "Candidates by mechanical cell and admission outcome",
      rowTitle: "MECH CELL",
      valueName: "candidates",
      cols: buckets,
      rows: cells.map(function (cell) {
        return {
          label: cell,
          cells: buckets.map(function (b) {
            var n = by[cell + "|" + b];
            return n === undefined ? null : { value: n };
          })
        };
      }),
      fmt: String,
      tableCols: ["Mechanical cell", "Outcome", "Candidates"],
      tableRows: skips.map(function (s) { return [s.cell, s.bucket, s.n]; })
    });
    sec.appendChild(p.figure);
  }

  function agreementPanel(sec, regime) {
    var models = uniq(regime.agreement.map(function (a) { return a.model; })).sort();
    var mechs = uniq(regime.agreement.map(function (a) { return a.mech; })).sort();
    var by = {};
    regime.agreement.forEach(function (a) { by[a.model + "|" + a.mech] = a.n; });
    var share = regime.agree_total ? regime.agree / regime.agree_total : 0;
    var p = panel("The model's direction against the mechanical one",
      "Rows are the direction parsed out of the analysis row's free-text market "
      + "regime — the one the deployment ladder keys the tier off. Columns are the "
      + "mechanical direction from SPY and VIX, which selects the exit profile. "
      + "The ringed diagonal is where they agree.", { table: true });
    matrix(chartHost(p), p.table, {
      title: "Model direction against mechanical direction, deployed positions",
      rowTitle: "MODEL",
      valueName: "positions",
      cols: mechs,
      rows: models.map(function (m) {
        return {
          label: m,
          cells: mechs.map(function (k) {
            var n = by[m + "|" + k];
            return n === undefined ? null : { value: n };
          })
        };
      }),
      fmt: String,
      highlight: function (i, j) { return models[i] === mechs[j]; },
      footnote: "They agree on " + regime.agree + " of " + regime.agree_total
        + " deployed positions (" + pct(share) + ").",
      tableCols: ["Model direction", "Mechanical direction", "Positions"],
      tableRows: regime.agreement.map(function (a) { return [a.model, a.mech, a.n]; })
    });
    sec.appendChild(p.figure);
    var note = h("p", "note");
    note.appendChild(document.createTextNode(
      "The two readings are taken off different things, so this is a description "
      + "of that gap and not an error rate: neither column is the truth the other "
      + "one missed."));
    sec.appendChild(note);
  }

  // ---------- render ----------

  function render() {
    var host = document.getElementById("panels");
    host.textContent = "";
    var pop = DATA.populations[state.population];
    var regime = pop.regime, s = pop.summary;
    var isPrimary = state.population === "primary";

    var sec = section("headline",
      isPrimary ? "The dense-episode book, by regime" : "The full sparse book, by regime",
      isPrimary
        ? "The primary population: runs of signal dates with no internal gap over 5 sessions."
        : "An availability upper bound and a concurrency lower bound. The pre-registration says it may not carry a conclusion alone.");
    var tiles = h("div", "tiles");
    var thin = regime.mech.filter(function (r) { return r.thin; }).length;
    tiles.appendChild(tile("Positions deployed", String(s.n), s.dates + " signal dates"));
    tiles.appendChild(tile("Mechanical cells", String(cellsBySize(regime.mech).length),
      "of the book's " + regime.considered + " candidates"));
    tiles.appendChild(tile("Structures used",
      String(uniq(regime.mech.map(function (r) { return r.structure; })).length),
      "the ladder emits no others"));
    tiles.appendChild(tile("Model ≠ mechanical",
      String(regime.agree_total - regime.agree),
      "of " + regime.agree_total + " positions disagree on direction"));
    tiles.appendChild(tile("Thin cells", String(thin) + " of " + regime.mech.length,
      "hold fewer than " + THIN_N + " positions"));
    sec.appendChild(tiles);
    host.appendChild(sec);

    sec = section("mech", "The mechanical read",
      "SPY and VIX as of the signal date (lib/mech_regime.py). Deterministic, and "
      + "what selects the exit profile a position is held under.");
    deploymentMatrix(sec, regime.mech, "mechanical cell");
    outcomePanels(sec, regime.mech, "mechanical cell");
    host.appendChild(sec);

    sec = section("model", "The model read",
      "Parsed out of the analysis row's free-text market regime. This is the label "
      + "the deployment ladder keys the tier off, so it is the one that decided "
      + "whether a play was eligible at all.");
    deploymentMatrix(sec, regime.model, "model cell");
    outcomePanels(sec, regime.model, "model cell");
    host.appendChild(sec);

    sec = section("census", "What deploying there cost",
      "Every candidate the account considered is accounted for exactly once.");
    censusPanel(sec, regime.census);
    skipsPanel(sec, regime.skips, regime.considered);
    host.appendChild(sec);

    sec = section("agreement", "Two regime readings, side by side",
      "The book carries both, and they disagree on most of it.");
    agreementPanel(sec, regime);
    host.appendChild(sec);

    document.querySelectorAll("[data-pop-label]").forEach(function (n) {
      n.textContent = isPrimary ? "dense episodes" : "full book";
    });
  }

  // ---------- boot ----------

  document.querySelectorAll("[data-population]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.population = btn.getAttribute("data-population");
      document.querySelectorAll("[data-population]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      render();
    });
  });

  render();
  window.addEventListener("resize", function () { hideTip(); });
})();
