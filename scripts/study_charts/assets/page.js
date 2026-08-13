/* account_sim readout — SVG chart layer.
 *
 * Everything is drawn from window.__ACCOUNT_SIM__, which the Python renderer
 * embeds. Series names and category labels come from CSV/report text, so they
 * are inserted with textContent, never innerHTML.
 *
 * The generic layer — helpers, tooltip, panel scaffolding, columnChart,
 * divergingBars — lives in kit.js, which the renderer inlines ahead of this
 * file. Only the charts that know what account_sim means are below.
 */
(function () {
  "use strict";

  var DATA = window.__ACCOUNT_SIM__;
  var state = { population: "primary" };

  var K = window.__STUDY_KIT__;
  var el = K.el, h = K.h, money = K.money, signed = K.signed, pct = K.pct,
      niceTicks = K.niceTicks, hideTip = K.hideTip, hoverable = K.hoverable,
      panel = K.panel, buildTable = K.buildTable, legend = K.legend,
      svgRoot = K.svgRoot, css = K.css, roundedRight = K.roundedRight,
      roundedTop = K.roundedTop, roundedBottom = K.roundedBottom,
      columnChart = K.columnChart, divergingBars = K.divergingBars,
      tile = K.tile, chipList = K.chipList, section = K.section,
      chartHost = K.chartHost, matrix = K.matrix;

  // The account's capital is config-sourced now, not a fixed $25k — every
  // prose site that used to hardcode it reads it back from the payload
  // instead. `acct()` is the full "$25,000" form, `acctK()` the compact
  // "$25k" form used where space is tight (bar labels, table headers).
  function acct() { return money(DATA.capital); }
  function acctK() { return "$" + (DATA.capital / 1000) + "k"; }

  // ---------- charts ----------

  function equityChart(host, tableHost, series, summary) {
    if (!series.length) return;
    var W = 1040, H = 316, DDH = 112;
    var m = { t: 18, r: 88, b: 44, l: 62 };
    var innerW = W - m.l - m.r, innerH = H - m.t - m.b;

    var cums = series.map(function (d) { return d.cum; });
    var lo = Math.min(0, Math.min.apply(null, cums));
    var hi = Math.max.apply(null, cums);
    var ticks = niceTicks(lo, hi, 5);
    var yLo = Math.min(ticks[0], lo), yHi = Math.max(ticks[ticks.length - 1], hi);
    var x = function (i) { return m.l + (series.length === 1 ? innerW / 2 : innerW * i / (series.length - 1)); };
    var y = function (v) { return m.t + innerH * (1 - (v - yLo) / (yHi - yLo || 1)); };

    var svg = svgRoot(W, H + DDH);
    svg.appendChild(el("title", {}, "Realized cumulative profit and loss by exit session"));

    ticks.forEach(function (t) {
      svg.appendChild(el("line", { class: "gridline", x1: m.l, x2: m.l + innerW, y1: y(t), y2: y(t) }));
      svg.appendChild(el("text", { class: "tick", x: m.l - 10, y: y(t) + 3.5, "text-anchor": "end" }, money(t)));
    });
    svg.appendChild(el("line", { class: "baseline", x1: m.l, x2: m.l + innerW, y1: y(0), y2: y(0) }));

    // area wash + line
    var areaPts = series.map(function (d, i) { return x(i) + "," + y(d.cum); });
    svg.appendChild(el("path", {
      d: "M" + x(0) + "," + y(0) + " L" + areaPts.join(" L") + " L" + x(series.length - 1) + "," + y(0) + " Z",
      fill: css("--s1"), opacity: 0.10
    }));
    svg.appendChild(el("path", {
      d: "M" + areaPts.join(" L"), fill: "none", stroke: css("--s1"),
      "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round"
    }));

    // trough marker — the maxDD low point
    var peak = 0, troughIdx = 0, worst = 0;
    series.forEach(function (d, i) {
      peak = Math.max(peak, d.cum);
      if (d.cum - peak < worst) { worst = d.cum - peak; troughIdx = i; }
    });
    svg.appendChild(el("circle", {
      cx: x(troughIdx), cy: y(series[troughIdx].cum), r: 4.5,
      fill: css("--s1"), stroke: css("--panel"), "stroke-width": 2
    }));
    // Label above the trough when it sits low in the plot, so it clears the x axis.
    var troughY = y(series[troughIdx].cum);
    var troughLow = troughY > m.t + innerH * 0.6;
    svg.appendChild(el("text", {
      class: "dlabel-2", x: x(troughIdx), y: troughY + (troughLow ? -14 : 22),
      "text-anchor": troughIdx === 0 ? "start" : "middle"
    }, "max DD " + money(worst)));

    // endpoint direct label
    var last = series[series.length - 1];
    svg.appendChild(el("circle", {
      cx: x(series.length - 1), cy: y(last.cum), r: 4.5,
      fill: css("--s1"), stroke: css("--panel"), "stroke-width": 2
    }));
    svg.appendChild(el("text", {
      class: "dlabel", x: x(series.length - 1) + 10, y: y(last.cum) + 4
    }, money(last.cum)));

    // x ticks — first, last, and a few between
    var xTickIdx = [0];
    var step = Math.max(1, Math.round((series.length - 1) / 5));
    for (var i = step; i < series.length - 1; i += step) xTickIdx.push(i);
    xTickIdx.push(series.length - 1);
    xTickIdx.forEach(function (i) {
      svg.appendChild(el("text", {
        class: "tick", x: x(i), y: m.t + innerH + 16, "text-anchor": i === 0 ? "start" : (i === series.length - 1 ? "end" : "middle")
      }, series[i].sess.slice(2)));
    });

    // underwater panel
    var ddTop = H + 14, ddInner = DDH - 40;
    var ddMin = Math.min.apply(null, series.map(function (d) { return d.drawdown; }));
    var yd = function (v) { return ddTop + ddInner * (v / (ddMin || -1)); };
    svg.appendChild(el("text", { class: "axis-title", x: m.l, y: ddTop - 2 }, "UNDERWATER"));
    var ddPts = series.map(function (d, i) { return x(i) + "," + yd(d.drawdown); });
    svg.appendChild(el("path", {
      d: "M" + x(0) + "," + yd(0) + " L" + ddPts.join(" L") + " L" + x(series.length - 1) + "," + yd(0) + " Z",
      fill: css("--s8"), opacity: 0.14
    }));
    svg.appendChild(el("path", { d: "M" + ddPts.join(" L"), fill: "none", stroke: css("--s8"), "stroke-width": 2 }));
    svg.appendChild(el("line", { class: "baseline", x1: m.l, x2: m.l + innerW, y1: yd(0), y2: yd(0) }));
    svg.appendChild(el("text", { class: "tick", x: m.l - 10, y: yd(ddMin) + 3.5, "text-anchor": "end" }, money(ddMin)));

    // crosshair + hit layer
    var cross = el("line", { class: "refline", y1: m.t, y2: H + DDH - 26, opacity: 0 });
    svg.appendChild(cross);
    var hit = el("rect", { x: m.l, y: m.t, width: innerW, height: H + DDH - m.t - 26, fill: "transparent" });
    svg.appendChild(hit);
    hit.addEventListener("pointermove", function (evt) {
      var box = svg.getBoundingClientRect();
      var px = (evt.clientX - box.left) * (W / box.width);
      var i = Math.round((px - m.l) / (innerW / Math.max(1, series.length - 1)));
      i = Math.max(0, Math.min(series.length - 1, i));
      var d = series[i];
      cross.setAttribute("x1", x(i));
      cross.setAttribute("x2", x(i));
      cross.setAttribute("opacity", 1);
      showTip(evt, d.sess, [
        { color: css("--s1"), value: money(d.cum), name: "cumulative" },
        { color: css("--s1"), value: money(d.pnl), name: "this session" },
        { color: css("--s8"), value: money(d.drawdown), name: "drawdown" },
        { value: String(d.closed), name: d.closed === 1 ? "position closed" : "positions closed" }
      ]);
    });
    hit.addEventListener("pointerleave", function () { cross.setAttribute("opacity", 0); hideTip(); });

    host.appendChild(svg);
    host.parentNode.appendChild(legend([
      { color: css("--s1"), label: "Realized cumulative P&L", line: true },
      { color: css("--s8"), label: "Drawdown from peak", line: true }
    ]));

    buildTable(tableHost, ["Exit session", "Session P&L", "Cumulative", "Drawdown", "Closed"],
      series.map(function (d) {
        return [d.sess, money(d.pnl), money(d.cum), money(d.drawdown), d.closed];
      }).concat([["TOTAL", money(summary.dollars), money(summary.dollars), money(summary.maxDD), summary.n]]));
  }

  function attritionChart(host, tableHost, baselines, summary, ratio) {
    var bars = [
      { label: "B1 stored contracts", sub: "the $50k book's own sizing", v: baselines.B1.dollars, n: baselines.B1.n, emph: false },
      { label: "B2 " + acctK() + " sizing", sub: "unconstrained, max-loss sized", v: baselines.B2.dollars, n: baselines.B2.n, emph: false },
      { label: "Constrained walk", sub: "caps and 3-a-day applied", v: summary.dollars, n: summary.n, emph: true }
    ];
    var W = 1040, rowH = 62, m = { t: 8, r: 132, b: 30, l: 168 };
    var H = m.t + bars.length * rowH + m.b;
    var innerW = W - m.l - m.r;
    var hi = Math.max.apply(null, bars.map(function (b) { return b.v; }));
    var ticks = niceTicks(0, hi, 5);
    var xMax = Math.max(ticks[ticks.length - 1], hi);
    var x = function (v) { return m.l + innerW * v / (xMax || 1); };

    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, "Where the paper book's dollars go: sizing first, then the caps"));
    ticks.forEach(function (t) {
      svg.appendChild(el("line", { class: "gridline", x1: x(t), x2: x(t), y1: m.t, y2: m.t + bars.length * rowH }));
      svg.appendChild(el("text", { class: "tick", x: x(t), y: H - 12, "text-anchor": "middle" }, money(t)));
    });

    bars.forEach(function (b, i) {
      var yTop = m.t + i * rowH + (rowH - 24) / 2;
      var w = Math.max(2, x(b.v) - m.l);
      var color = b.emph ? css("--s1") : css("--rule-strong");
      var r = el("path", { d: roundedRight(m.l, yTop, w, 24, 4), fill: color });
      hoverable(r, b.label, [
        { color: color, value: money(b.v), name: "realized" },
        { value: String(b.n), name: "positions" }
      ]);
      svg.appendChild(r);
      svg.appendChild(el("text", { class: "dlabel", x: m.l + w + 10, y: yTop + 16 }, money(b.v)));
      svg.appendChild(el("text", { class: "dlabel", x: m.l - 12, y: yTop + 10, "text-anchor": "end" }, b.label));
      svg.appendChild(el("text", { class: "tick", x: m.l - 12, y: yTop + 23, "text-anchor": "end" }, b.n + " positions"));
    });
    svg.appendChild(el("line", { class: "baseline", x1: m.l, x2: m.l, y1: m.t, y2: m.t + bars.length * rowH }));
    host.appendChild(svg);

    buildTable(tableHost, ["Stage", "Positions", "Dates", "Realized $", "Mean R"], [
      ["B1 stored contracts", baselines.B1.n, baselines.B1.dates, money(baselines.B1.dollars), signed(baselines.B1.meanR)],
      ["B2 " + acctK() + " sizing", baselines.B2.n, baselines.B2.dates, money(baselines.B2.dollars), signed(baselines.B2.meanR)],
      ["Constrained walk", summary.n, summary.dates, money(summary.dollars), signed(summary.meanR)],
      ["B2 / B1 ratio", "", "", ratio.toFixed(2) + "x", ""]
    ]);
  }


  var CENSUS_LABELS = {
    taken: "Taken", taken_downsized: "Taken, downsized", cash: "Cash short",
    per_pos_delta: "Per-position delta cap", net_delta: "Net delta cap",
    min1_refusal: "Refused at 1 contract", day3_cap: "3-a-day cap", unsizable: "No usable max loss"
  };

  function censusChart(host, tableHost, census, mostBinding) {
    var slots = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s7"];
    var total = census.reduce(function (a, c) { return a + c.n; }, 0);
    var W = 1040, H = 124, m = { l: 0, r: 0, t: 44 }, barH = 34;
    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, "Every candidate the walk considered, split by what happened to it"));

    var cursor = 0;
    census.forEach(function (c, i) {
      var color = css(slots[i % slots.length]);
      var w = W * c.n / total;
      var drawW = Math.max(1, w - 2); // 2px surface gap does the separating
      var rect = el("rect", { x: cursor, y: m.t, width: drawW, height: barH, fill: color, rx: 2 });
      hoverable(rect, CENSUS_LABELS[c.bucket] || c.bucket, [
        { color: color, value: String(c.n), name: "candidates" },
        { value: pct(c.n / total, 1), name: "of all considered" }
      ]);
      svg.appendChild(rect);
      // Only label inside the segment when the text actually fits.
      var label = String(c.n);
      if (drawW > 34) {
        svg.appendChild(el("text", {
          x: cursor + drawW / 2, y: m.t + 22, "text-anchor": "middle",
          "font-size": 12, "font-weight": 600, fill: "#ffffff", "font-family": "var(--mono)"
        }, label));
      }
      if (drawW > 74) {
        svg.appendChild(el("text", {
          class: "tick", x: cursor + drawW / 2, y: m.t - 8, "text-anchor": "middle"
        }, pct(c.n / total, 0)));
      }
      cursor += w;
    });

    svg.appendChild(el("text", { class: "axis-title", x: 0, y: 12 }, "ALL " + total + " CANDIDATES CONSIDERED"));
    svg.appendChild(el("text", {
      class: "tick", x: 0, y: m.t + barH + 18
    }, "most binding: " + (CENSUS_LABELS[mostBinding] || mostBinding).toLowerCase()));
    host.appendChild(svg);

    host.parentNode.appendChild(legend(census.map(function (c, i) {
      return { color: css(slots[i % slots.length]), label: (CENSUS_LABELS[c.bucket] || c.bucket) + " · " + c.n };
    })));

    buildTable(tableHost, ["Outcome", "Candidates", "Share"],
      census.map(function (c) { return [CENSUS_LABELS[c.bucket] || c.bucket, c.n, pct(c.n / total, 1)]; })
        .concat([["TOTAL", total, "100%"]]));
  }

  function adverseChart(host, tableHost, adverse) {
    var W = 1040, rowH = 66, m = { t: 14, r: 118, b: 34, l: 254 };
    var H = m.t + adverse.length * rowH + m.b;
    var innerW = W - m.l - m.r;
    var vals = [];
    adverse.forEach(function (a) {
      vals.push(a.meanR);
      if (a.ci) { vals.push(a.ci[0]); vals.push(a.ci[1]); }
    });
    var lo = Math.min(0, Math.min.apply(null, vals));
    var hi = Math.max(0, Math.max.apply(null, vals));
    var ticks = niceTicks(lo, hi, 6);
    var xLo = Math.min(ticks[0], lo), xHi = Math.max(ticks[ticks.length - 1], hi);
    var x = function (v) { return m.l + innerW * (v - xLo) / (xHi - xLo || 1); };

    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, "Mean R of the picks the caps took versus the picks they skipped"));
    ticks.forEach(function (t) {
      svg.appendChild(el("line", { class: "gridline", x1: x(t), x2: x(t), y1: m.t, y2: m.t + adverse.length * rowH }));
      svg.appendChild(el("text", { class: "tick", x: x(t), y: H - 16, "text-anchor": "middle" }, signed(t, 2)));
    });
    svg.appendChild(el("text", { class: "axis-title", x: m.l + innerW / 2, y: H - 2, "text-anchor": "middle" }, "MEAN R"));

    adverse.forEach(function (a, i) {
      var yTop = m.t + i * rowH + (rowH - 22) / 2;
      var isTaken = a.bucket === "taken";
      var color = a.meanR >= 0 ? css("--s1") : css("--s8");
      var x0 = x(0), x1 = x(a.meanR);
      var rect = el("path", {
        d: a.meanR >= 0 ? roundedRight(x0, yTop, Math.max(2, x1 - x0), 22, 4)
          : roundedRight(x1, yTop, Math.max(2, x0 - x1), 22, 4),
        fill: color, opacity: isTaken ? 1 : 0.55
      });
      var rows = [{ color: color, value: signed(a.meanR), name: "mean R" }, { value: String(a.n), name: "positions" }];
      if (a.ci) rows.push({ value: "[" + signed(a.ci[0], 2) + ", " + signed(a.ci[1], 2) + "]", name: "95% CI" });
      hoverable(rect, isTaken ? "Taken" : "Skipped · " + (CENSUS_LABELS[a.bucket] || a.bucket), rows);
      svg.appendChild(rect);

      if (a.ci) {
        var cy = yTop + 11;
        svg.appendChild(el("line", { x1: x(a.ci[0]), x2: x(a.ci[1]), y1: cy, y2: cy, stroke: css("--ink-2"), "stroke-width": 1.5 }));
        [a.ci[0], a.ci[1]].forEach(function (v) {
          svg.appendChild(el("line", { x1: x(v), x2: x(v), y1: cy - 6, y2: cy + 6, stroke: css("--ink-2"), "stroke-width": 1.5 }));
        });
      }
      // Clear the CI whisker, not just the bar end, or the two overprint.
      var labelX = Math.max(x0, x1, a.ci ? x(a.ci[1]) : x1) + 12;
      svg.appendChild(el("text", { class: "dlabel", x: labelX, y: yTop + 15 }, signed(a.meanR)));
      svg.appendChild(el("text", {
        class: "dlabel", x: m.l - 14, y: yTop + 9, "text-anchor": "end"
      }, isTaken ? "Taken" : "Skipped · " + (CENSUS_LABELS[a.bucket] || a.bucket).toLowerCase()));
      svg.appendChild(el("text", { class: "tick", x: m.l - 14, y: yTop + 22, "text-anchor": "end" }, "n = " + a.n));
    });
    svg.appendChild(el("line", { class: "baseline", x1: x(0), x2: x(0), y1: m.t, y2: m.t + adverse.length * rowH }));
    host.appendChild(svg);

    buildTable(tableHost, ["Bucket", "n", "Mean R", "95% CI (date-clustered)"],
      adverse.map(function (a) {
        return [a.bucket === "taken" ? "Taken" : "Skipped · " + (CENSUS_LABELS[a.bucket] || a.bucket),
          a.n, signed(a.meanR), a.ci ? "[" + signed(a.ci[0]) + ", " + signed(a.ci[1]) + "]" : "—"];
      }));
  }


  function capGrid(host, tableHost, grid) {
    var netCaps = grid.net_caps, rows = grid.rows;
    var all = [];
    rows.forEach(function (r) { r.cells.forEach(function (c) { all.push(c.dollars); }); });
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    var cellW = 150, cellH = 62, m = { t: 34, l: 92 };
    var W = m.l + netCaps.length * cellW + 8, H = m.t + rows.length * cellH + 34;
    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, "Realized dollars across the per-position and net delta-notional cap grid"));

    netCaps.forEach(function (n, j) {
      svg.appendChild(el("text", {
        class: "tick", x: m.l + j * cellW + cellW / 2, y: m.t - 12, "text-anchor": "middle"
      }, "net " + n + (n === "inf" ? "" : "x")));
    });
    svg.appendChild(el("text", { class: "axis-title", x: 0, y: m.t - 12 }, "PER-POS"));

    rows.forEach(function (r, i) {
      svg.appendChild(el("text", {
        class: "tick", x: m.l - 14, y: m.t + i * cellH + cellH / 2 + 4, "text-anchor": "end"
      }, r.per_pos + (r.per_pos === "inf" ? "" : "x")));
      r.cells.forEach(function (c, j) {
        var step = K.rampStep(c.dollars, lo, hi);
        var fill = K.rampFill(step);
        var isHeadline = r.per_pos === grid.headline.per_pos && netCaps[j] === grid.headline.net;
        var x = m.l + j * cellW + 1, y = m.t + i * cellH + 1;
        var rect = el("rect", { x: x, y: y, width: cellW - 3, height: cellH - 3, fill: fill, rx: 2 });
        hoverable(rect, "per-pos " + r.per_pos + "x  ×  net " + netCaps[j] + "x", [
          { color: fill, value: money(c.dollars), name: "realized" },
          { value: String(c.n), name: "positions taken" }
        ].concat(isHeadline ? [{ value: "configured cell", name: "" }] : []));
        svg.appendChild(rect);
        var ink = K.rampInk(step);
        svg.appendChild(el("text", {
          x: x + (cellW - 3) / 2, y: y + 26, "text-anchor": "middle",
          "font-size": 13, "font-weight": 600, fill: ink, "font-family": "var(--mono)"
        }, money(c.dollars)));
        svg.appendChild(el("text", {
          x: x + (cellW - 3) / 2, y: y + 43, "text-anchor": "middle",
          "font-size": 11, fill: ink, opacity: 0.8, "font-family": "var(--mono)"
        }, c.n + " taken"));
        if (isHeadline) {
          svg.appendChild(el("rect", {
            x: x - 1, y: y - 1, width: cellW - 1, height: cellH - 1, fill: "none",
            stroke: css("--s2"), "stroke-width": 2.5, rx: 3
          }));
        }
      });
    });
    svg.appendChild(el("text", {
      class: "tick", x: m.l, y: H - 10
    }, "orange ring = the configured cell (per-pos " + grid.headline.per_pos + "x × net " + grid.headline.net + "x)"));
    host.appendChild(svg);

    buildTable(tableHost, ["Per-position cap"].concat(netCaps.map(function (n) { return "net " + n; })),
      rows.map(function (r) {
        return [r.per_pos].concat(r.cells.map(function (c) { return money(c.dollars) + " / " + c.n; }));
      }));
  }

  function armsChart(host, tableHost, arms) {
    var metrics = [
      { key: "dollars", label: "REALIZED $", fmt: function (v) { return money(v); } },
      { key: "meanR", label: "MEAN R", fmt: function (v) { return signed(v); } },
      { key: "maxDD", label: "MAX DRAWDOWN", fmt: function (v) { return money(v); } }
    ];
    var wrap = h("div", "grid-3");
    metrics.forEach(function (metric) {
      var W = 320, H = 200, m = { t: 26, r: 10, b: 40, l: 58 };
      var innerW = W - m.l - m.r, innerH = H - m.t - m.b;
      var vals = arms.map(function (a) { return a[metric.key]; });
      var lo = Math.min(0, Math.min.apply(null, vals)), hi = Math.max(0, Math.max.apply(null, vals));
      var ticks = niceTicks(lo, hi, 3);
      var yLo = Math.min(ticks[0], lo), yHi = Math.max(ticks[ticks.length - 1], hi);
      var y = function (v) { return m.t + innerH * (1 - (v - yLo) / (yHi - yLo || 1)); };
      var band = innerW / arms.length, barW = Math.min(24, band - 12);

      var svg = svgRoot(W, H);
      svg.appendChild(el("title", {}, metric.label + " by arm"));
      svg.appendChild(el("text", { class: "axis-title", x: 0, y: 12 }, metric.label));
      ticks.forEach(function (t) {
        svg.appendChild(el("line", { class: "gridline", x1: m.l, x2: m.l + innerW, y1: y(t), y2: y(t) }));
        svg.appendChild(el("text", { class: "tick", x: m.l - 8, y: y(t) + 3.5, "text-anchor": "end" },
          metric.key === "meanR" ? t.toFixed(2) : money(t)));
      });
      arms.forEach(function (a, i) {
        var cx = m.l + band * i + band / 2;
        var v = a[metric.key];
        var color = a.headline ? css("--s2") : css("--s1");
        // The rounded end is the DATA end — bottom for a bar hanging below zero.
        var top = Math.min(y(v), y(0)), hgt = Math.max(1, Math.abs(y(v) - y(0)));
        var shape = v >= 0 ? roundedTop : roundedBottom;
        var bar = el("path", { d: shape(cx - barW / 2, top, barW, hgt, 4), fill: color, opacity: a.headline ? 1 : 0.6 });
        hoverable(bar, a.arm + (a.headline ? " — headline" : ""), [
          { color: color, value: metric.fmt(v), name: metric.label.toLowerCase() },
          { value: String(a.n), name: "positions" }
        ]);
        svg.appendChild(bar);
        svg.appendChild(el("text", {
          class: "tick", x: cx, y: m.t + innerH + 16, "text-anchor": "middle"
        }, a.arm.replace(/[() ]/g, "")));
      });
      svg.appendChild(el("line", { class: "baseline", x1: m.l, x2: m.l + innerW, y1: y(0), y2: y(0) }));
      var cell = h("div", "chart");
      cell.appendChild(svg);
      wrap.appendChild(cell);
    });
    host.appendChild(wrap);
    host.parentNode.appendChild(legend([
      { color: css("--s2"), label: "(R, F1) — the headline arm, what production does" },
      { color: css("--s1"), label: "Reported, not adopted" }
    ]));
    buildTable(tableHost, ["Arm", "n", "Dates", "Realized $", "Mean R", "Win", "Max DD"],
      arms.map(function (a) {
        return [a.arm + (a.headline ? " HEADLINE" : ""), a.n, a.dates, money(a.dollars), signed(a.meanR), pct(a.win), money(a.maxDD)];
      }));
  }

  function dumbbell(host, tableHost, accounts) {
    var big = accounts[0], small = accounts[1];
    // The intended risk budget as a %, read back from this run's own
    // capital/budget rather than assumed to be 2 — the reference line below
    // has to sit at whatever the config actually set.
    var riskPct = small.capital ? 100 * small.budget / small.capital : 2;
    var rows = [
      { label: "Median position", a: big.risk_median, b: small.risk_median },
      { label: "90th percentile", a: big.risk_p90, b: small.risk_p90 },
      { label: "Largest position", a: big.risk_max, b: small.risk_max }
    ];
    var W = 1040, rowH = 52, m = { t: 26, r: 74, b: 44, l: 168 };
    var H = m.t + rows.length * rowH + m.b;
    var innerW = W - m.l - m.r;
    var hi = Math.max.apply(null, rows.map(function (r) { return Math.max(r.a, r.b); }));
    var ticks = niceTicks(0, hi, 5);
    var xMax = Math.max(ticks[ticks.length - 1], hi);
    var x = function (v) { return m.l + innerW * v / (xMax || 1); };

    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, "Realized risk per position as a share of capital, $50k book versus " + acctK() + " book"));
    ticks.forEach(function (t) {
      svg.appendChild(el("line", { class: "gridline", x1: x(t), x2: x(t), y1: m.t, y2: m.t + rows.length * rowH }));
      svg.appendChild(el("text", { class: "tick", x: x(t), y: H - 22, "text-anchor": "middle" }, t + "%"));
    });
    svg.appendChild(el("text", { class: "axis-title", x: m.l + innerW / 2, y: H - 6, "text-anchor": "middle" },
      "REALIZED RISK PER POSITION, % OF CAPITAL"));

    // the intended risk budget
    svg.appendChild(el("line", { class: "refline", x1: x(riskPct), x2: x(riskPct), y1: m.t, y2: m.t + rows.length * rowH }));
    svg.appendChild(el("text", { class: "tick", x: x(riskPct), y: m.t - 8, "text-anchor": "middle" }, riskPct.toFixed(riskPct % 1 ? 1 : 0) + "% intended budget"));

    rows.forEach(function (r, i) {
      var cy = m.t + i * rowH + rowH / 2;
      svg.appendChild(el("line", { x1: x(r.a), x2: x(r.b), y1: cy, y2: cy, stroke: css("--rule-strong"), "stroke-width": 3, "stroke-linecap": "round" }));
      [{ v: r.a, color: css("--seq-3"), name: "$50,000 account" }, { v: r.b, color: css("--s1"), name: acct() + " account" }].forEach(function (pt) {
        var dot = el("circle", { cx: x(pt.v), cy: cy, r: 6, fill: pt.color, stroke: css("--panel"), "stroke-width": 2 });
        hoverable(dot, r.label, [{ color: pt.color, value: pt.v.toFixed(1) + "%", name: pt.name }]);
        svg.appendChild(dot);
      });
      svg.appendChild(el("text", { class: "dlabel", x: m.l - 14, y: cy + 4, "text-anchor": "end" }, r.label));
      // Both ends direct-labelled: the light $50k step sits under 3:1 on the light surface.
      svg.appendChild(el("text", { class: "dlabel-2", x: x(r.a) - 12, y: cy + 4, "text-anchor": "end" }, r.a.toFixed(1) + "%"));
      svg.appendChild(el("text", { class: "dlabel", x: x(r.b) + 12, y: cy + 4 }, r.b.toFixed(1) + "%"));
    });
    svg.appendChild(el("line", { class: "baseline", x1: m.l, x2: m.l, y1: m.t, y2: m.t + rows.length * rowH }));
    host.appendChild(svg);
    host.parentNode.appendChild(legend([
      { color: css("--seq-3"), label: "$50,000 account · $1,000 budget" },
      { color: css("--s1"), label: acct() + " account · " + money(small.budget) + " budget" }
    ]));

    buildTable(tableHost, ["Measure", "$50k account", acctK() + " account"],
      rows.map(function (r) { return [r.label, r.a.toFixed(1) + "%", r.b.toFixed(1) + "%"]; }).concat([
        ["1-contract floor share", big.floor_pct + "%", small.floor_pct + "%"],
        ["Mean contracts", big.mean_contracts.toFixed(2), small.mean_contracts.toFixed(2)]
      ]));
  }

  // ---------- render ----------


  function render() {
    var host = document.getElementById("panels");
    host.textContent = "";
    var pop = DATA.populations[state.population];
    var rep = DATA.report.populations[state.population];
    var s = pop.summary;
    var isPrimary = state.population === "primary";

    // --- headline tiles
    var sec = section("headline", isPrimary ? "The dense-episode book" : "The full sparse book",
      isPrimary
        ? "The primary population: runs of signal dates with no internal gap over 5 sessions."
        : "An availability upper bound and a concurrency lower bound. The pre-registration says it may not carry a conclusion alone.");
    var tiles = h("div", "tiles");
    tiles.appendChild(tile("Positions taken", String(s.n), s.dates + " signal dates"));
    tiles.appendChild(tile("Realized", money(s.dollars), "on " + acct() + " of capital"));
    tiles.appendChild(tile("Mean R", signed(s.meanR), s.ci ? "95% CI " + signed(s.ci[0], 2) + " to " + signed(s.ci[1], 2) : ""));
    tiles.appendChild(tile("Win rate", pct(s.win), s.n + " closed positions"));
    tiles.appendChild(tile("Max drawdown", money(s.maxDD), pct(Math.abs(s.maxDD) / DATA.capital, 1) + " of capital"));
    tiles.appendChild(tile("Worst session", money(s.worst), "median hold " + s.median_days + "d"));
    sec.appendChild(tiles);
    host.appendChild(sec);

    // --- equity
    sec = section("equity", "Equity and drawdown",
      "P&L booked on the session a position exits — open positions are never marked to market, so this understates intra-position drawdown.");
    var p = panel("Realized cumulative P&L", "Each step is one exit session, not one calendar day; gaps between episodes are closed up. The underwater panel below shares the same x positions.", { table: true });
    equityChart(chartHost(p), p.table, pop.equity, s);
    sec.appendChild(p.figure);
    var ddNote = h("p", "note");
    ddNote.appendChild(document.createTextNode("Max drawdown reached " + money(s.maxDD) + ", or "));
    ddNote.appendChild(h("strong", null, pct(Math.abs(s.maxDD) / DATA.capital, 1) + " of starting capital"));
    ddNote.appendChild(document.createTextNode(" against the A3 limit of " + rep.equity.dd_limit_pct + "%."));
    sec.appendChild(ddNote);
    host.appendChild(sec);

    // --- attrition
    sec = section("attrition", "Where the paper book's dollars go",
      "B1 to B2 isolates granularity — contract counts. B2 to constrained isolates the caps.");
    p = panel("Three stages, same picks", "B1 is the stored book at its own contract counts, which are a $50k account's. B2 re-sizes those same picks for " + acct() + " with no caps. The constrained walk then applies the delta-notional caps and the 3-a-day limit.", { table: true });
    attritionChart(chartHost(p), p.table, rep.baselines, s, rep.baselines.ratio);
    sec.appendChild(p.figure);
    var note = h("p", "note");
    note.appendChild(document.createTextNode("The book shrinks by "));
    note.appendChild(h("strong", null, "size before any constraint applies"));
    note.appendChild(document.createTextNode(" — B2 is " + rep.baselines.ratio.toFixed(2) + "x of B1. On the " + rep.criteria[1].detail + "."));
    sec.appendChild(note);
    host.appendChild(sec);

    // --- constraints
    sec = section("constraints", "What the caps did",
      "Every candidate the walk considered is accounted for exactly once (criterion A4).");
    var stack = h("div", "stack");
    p = panel("Binding-constraint census", "One segment per outcome. The exclusion buckets are what the account could not fit, not what the ladder declined to pick.", { table: true });
    censusChart(chartHost(p), p.table, pop.census, rep.census.most_binding);
    stack.appendChild(p.figure);

    p = panel("Adverse-ordering check", "If the caps systematically skipped the better picks, the account is not merely smaller than the paper book — it is adversely selected. Skipped picks are replayed at the size they would have been given. Whiskers are the study's own date-clustered bootstrap 95% CI.", { table: true });
    adverseChart(chartHost(p), p.table, pop.adverse);
    stack.appendChild(p.figure);
    sec.appendChild(stack);

    // The study prints a delta-vs-taken per rejected bucket but draws no verdict
    // from it (report.parse_adverse). Quote those deltas as-is, for every bucket,
    // rather than picking a "worst" one and asserting what it means.
    var rejected = rep.adverse.rejected;
    if (rejected.length) {
      note = h("p", "note is-warning");
      note.appendChild(document.createTextNode("The study's delta vs taken, per skipped bucket: "));
      rejected.forEach(function (r, i) {
        if (i > 0) note.appendChild(document.createTextNode(", "));
        note.appendChild(h("strong", null, (CENSUS_LABELS[r.bucket] || r.bucket).toLowerCase()));
        note.appendChild(document.createTextNode(" " + signed(r.delta) + " R (n=" + r.n + ")"));
      });
      note.appendChild(document.createTextNode("."));
      sec.appendChild(note);
    }
    host.appendChild(sec);

    // --- sizing
    var small = rep.granularity.accounts[1];
    var riskShare = small.capital ? small.budget / small.capital : null;
    var riskPctLabel = riskShare === null ? "the risk budget" : pct(riskShare);
    sec = section("sizing", "What " + riskPctLabel + " of " + acct() + " actually buys",
      "The intended risk budget is " + money(small.budget) + " per position. Most spreads cost more than that at one contract.");
    stack = h("div", "stack");
    p = panel("Realized risk per position", "Each rung compares the same book sized for a $50,000 account against a " + acctK() + " one. Anything right of the reference line breached the " + riskPctLabel + " budget the moment it was opened.", { table: true });
    dumbbell(chartHost(p), p.table, rep.granularity.accounts);
    stack.appendChild(p.figure);

    p = panel("Contracts held per position", "At " + acct() + " the position size collapses toward the one-contract floor, and a floor position is a position whose risk the budget never actually controlled.", { table: true });
    columnChart(chartHost(p), p.table, {
      rows: pop.contracts.map(function (c) {
        return { label: c.contracts + "c", value: c.n, sub: pct(c.n / s.n, 0) + " of taken" };
      }),
      valueFmt: function (v) { return String(v); },
      valueName: "positions",
      subName: "share",
      axisTitle: "POSITIONS",
      title: "Contract counts held per position"
    });
    stack.appendChild(p.figure);
    sec.appendChild(stack);

    note = h("p", "note is-warning");
    note.appendChild(h("strong", null, small.floor_pct + "% of sized candidates"));
    note.appendChild(document.createTextNode(" breached the " + money(small.budget) + " budget at a single contract (" + small.floor_n + " of " + small.floor_of + "), against " +
      rep.granularity.accounts[0].floor_pct + "% for the same picks in a $50,000 account. The headline arm takes those positions anyway — that is what the F1 in (R, F1) means."));
    sec.appendChild(note);
    host.appendChild(sec);

    // --- exits
    sec = section("exits", "How the positions ended",
      "Exit reasons come from the frozen replay harness, not from this simulation.");
    stack = h("div", "stack");
    p = panel("Realized dollars by exit reason", "Bars right of zero made money, left of zero lost it. The count of positions behind each bar is in the tooltip and the table.", { table: true });
    divergingBars(chartHost(p), p.table, {
      rows: pop.exits.map(function (e) {
        return { label: e.reason.replace(/_/g, " "), value: e.dollars, sub: e.n + " positions" };
      }),
      valueFmt: function (v) { return money(v); },
      valueName: "realized",
      subName: "count",
      axisTitle: "REALIZED $",
      title: "Realized dollars by exit reason",
      tableCols: ["Exit reason", "Positions", "Realized $", "Average per position"],
      tableRows: pop.exits.map(function (e) {
        return [e.reason.replace(/_/g, " "), e.n, money(e.dollars), money(e.dollars / e.n)];
      })
    });
    stack.appendChild(p.figure);
    sec.appendChild(stack);
    host.appendChild(sec);

    // --- utilisation
    sec = section("utilisation", "How full the account ran",
      "Net delta-notional as a multiple of equity, averaged over the sessions in each month.");
    // The net cap is config-driven (config/account-sim.yml); it also reads "inf"
    // when the config sets caps.net: null, which is uncapped, not a number.
    var netCapStr = rep.cap_grid.headline.net;
    var netCapNum = netCapStr === "inf" ? null : parseFloat(netCapStr);
    var utilPanelText = netCapNum === null
      ? "The net delta-notional was uncapped for this run. Months that ran high did so on the account's own budget, not against a cap."
      : "The cap is " + netCapNum.toFixed(2) + "x equity. Months that sit against it are months where the account, not the ladder, decided how many positions it held.";
    p = panel("Monthly net delta-notional", utilPanelText, { table: true });
    columnChart(chartHost(p), p.table, {
      rows: rep.utilisation.map(function (u) {
        return { label: u.month, value: u.net_avg, sub: "peak " + u.net_max.toFixed(2) + "x · " + u.open_avg.toFixed(1) + " open avg" };
      }),
      valueFmt: function (v) { return v.toFixed(2) + "x"; },
      tickFmt: function (v) { return v.toFixed(2) + "x"; },
      valueName: "net avg",
      subName: "",
      axisTitle: "NET DELTA-NOTIONAL, MULTIPLE OF EQUITY",
      refLine: netCapNum === null ? null : { v: netCapNum, label: netCapNum.toFixed(2) + "x net cap" },
      rotateLabels: true,
      labelEvery: 2,
      title: "Monthly average net delta-notional",
      tableCols: ["Month", "Sessions", "Reserved avg", "Reserved max", "Net avg", "Net max", "Open avg", "Open max"],
      tableRows: rep.utilisation.map(function (u) {
        return [u.month, u.sessions, u.res_avg.toFixed(2) + "x", u.res_max.toFixed(2) + "x",
          u.net_avg.toFixed(2) + "x", u.net_max.toFixed(2) + "x", u.open_avg.toFixed(1), u.open_max];
      })
    });
    sec.appendChild(p.figure);
    host.appendChild(sec);

    // --- arms
    sec = section("arms", "The four arms",
      "F1 takes the one-contract floor when the budget is breached; F2 refuses it. R rejects on breach; D downsizes.");
    p = panel("Same selection, four sizing policies", "(R, F1) is what production does and is the only arm the study adopts. The other three are reported, not adopted.", { table: true });
    armsChart(chartHost(p), p.table, rep.arms);
    sec.appendChild(p.figure);
    host.appendChild(sec);

    // --- cap grid
    sec = section("capgrid", "The cap grid", "Read monotonicity, and nothing else.");
    p = panel("Realized dollars across the cap surface", "Each cell is a full re-walk at that pair of caps. Rows monotone in the net cap: " +
      rep.cap_grid.monotone_rows[0] + "/" + rep.cap_grid.monotone_rows[1] + ". Columns monotone in the per-position cap: " +
      rep.cap_grid.monotone_cols[0] + "/" + rep.cap_grid.monotone_cols[1] + ".", { table: true });
    capGrid(chartHost(p), p.table, rep.cap_grid);
    sec.appendChild(p.figure);
    note = h("p", "note is-warning");
    note.appendChild(h("strong", null, "Anti-tuning rule: "));
    note.appendChild(document.createTextNode("no cap value may be adopted, recommended, or carried into a conclusion on the basis of its P&L here. The only admissible reading is qualitative monotonicity. The walk is stateful, so a cap that rejects a large early position leaves headroom a looser cap has already spent — the non-monotone columns are path dependence, and G3 and G4 both pass."));
    sec.appendChild(note);
    host.appendChild(sec);

    // --- criteria
    sec = section("criteria", "Criteria A1–A6", "Pre-registered before the run. The checklist is the result.");
    sec.appendChild(chipList(rep.criteria.map(function (c) {
      return { id: c.id, title: c.name, detail: c.detail, status: c.status };
    })));
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
