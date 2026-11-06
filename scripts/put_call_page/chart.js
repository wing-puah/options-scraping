/* ETF put/call page. Each ETF gets one figure with two panels on one date axis:
 * price with the put/call ratio overlaid, then call and put premium as mirrored
 * bars. The price and ratio share a plot because the operator asked for the
 * overlay, so each axis carries a title with its own line key.
 * A null is a gap, never a zero.
 */
(function () {
  "use strict";
  var D = window.__PUT_CALL__;
  var K = window.__STUDY_KIT__;
  var RANGES = [["3M", 63], ["6M", 126], ["1Y", 252], ["All", 0]];
  var LOG_TICKS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var range = 126;
  var figures = [];

  function compact(v) {
    if (v === null || v === undefined) return "no data";
    var a = Math.abs(v);
    if (a >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
    if (a >= 1e6) return "$" + (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
    if (a >= 1e3) return "$" + (v / 1e3).toFixed(0) + "K";
    return "$" + v.toFixed(0);
  }

  function finite(list) {
    return list.filter(function (v) { return v !== null && v !== undefined; });
  }

  // A line that breaks at every null, with a dot for a value with no neighbour.
  function gapLine(svg, values, x, y, color, width, i0) {
    var d = "";
    values.forEach(function (v, n) {
      if (v === null || v === undefined) return;
      var prev = n > 0 ? values[n - 1] : null;
      var next = n < values.length - 1 ? values[n + 1] : null;
      var hasPrev = prev !== null && prev !== undefined;
      var hasNext = next !== null && next !== undefined;
      if (!hasPrev && !hasNext) {
        svg.appendChild(K.el("circle", { cx: x(n + i0), cy: y(v), r: 2.5, fill: color }));
        return;
      }
      d += (hasPrev ? "L" : "M") + x(n + i0).toFixed(1) + "," + y(v).toFixed(1);
    });
    if (d) svg.appendChild(K.el("path", {
      d: d, fill: "none", stroke: color, "stroke-width": width,
      "stroke-linejoin": "round", "stroke-linecap": "round"
    }));
  }

  function label(svg, x, y, text, anchor, color) {
    svg.appendChild(K.el("text", {
      x: x, y: y, "text-anchor": anchor || "start", "font-size": 11,
      fill: color || "var(--ink-3)", "font-family": "var(--mono)"
    }, text));
  }

  function drawDateAxis(svg, i0, i1, x, top, bottom, minGap) {
    var last = -1e9, lastMonth = "";
    for (var i = i0; i <= i1; i++) {
      var ym = D.dates[i].slice(0, 7);
      if (ym === lastMonth) continue;
      lastMonth = ym;
      var px = x(i);
      if (px - last < minGap) continue;
      last = px;
      var m = parseInt(ym.slice(5), 10) - 1;
      svg.appendChild(K.el("line", { x1: px, x2: px, y1: top, y2: bottom, stroke: "var(--grid)" }));
      label(svg, px, bottom + 15, MONTHS[m] + (m === 0 || i === i0 ? " " + ym.slice(2, 4) : ""), "middle");
    }
  }

  function axisKey(svg, x, y, text, anchor, color) {
    var w = 16, dir = anchor === "end" ? -1 : 1;
    svg.appendChild(K.el("line", {
      x1: x, x2: x + dir * w, y1: y - 4, y2: y - 4, stroke: color, "stroke-width": 2
    }));
    label(svg, x + dir * (w + 5), y, text, anchor, "var(--ink-2)");
  }

  function draw(fig) {
    var etf = fig.etf, host = fig.host;
    var W = Math.max(300, host.clientWidth || 900);
    var narrow = W < 520;
    var L = narrow ? 44 : 56, R = narrow ? 42 : 52;
    var keyH = 18, topH = narrow ? 190 : 230, gap = 14, lowH = narrow ? 120 : 140, axisH = 22;
    var topY = keyH + 6, lowY = topY + topH + gap;
    var H = lowY + lowH + axisH;
    var n = D.dates.length;
    var i0 = range ? Math.max(0, n - range) : 0, i1 = n - 1;
    var step = (W - L - R) / (i1 - i0 + 1);
    var x = function (i) { return L + (i - i0 + 0.5) * step; };

    var closes = etf.close.slice(i0, i1 + 1), ratios = etf.ratio.slice(i0, i1 + 1);
    var calls = etf.call.slice(i0, i1 + 1), puts = etf.put.slice(i0, i1 + 1);
    var px = finite(closes), rs = finite(ratios);

    var svg = K.svgRoot(W, H);
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-label", etf.sym + " price, put/call ratio and premium by date. Arrow keys step through dates.");

    drawDateAxis(svg, i0, i1, x, topY, lowY + lowH, narrow ? 44 : 52);

    // Price scale, left axis.
    var yPrice = null;
    if (px.length) {
      var pLo = Math.min.apply(null, px), pHi = Math.max.apply(null, px);
      var pad = (pHi - pLo) * 0.06 || pHi * 0.02;
      pLo -= pad; pHi += pad;
      yPrice = function (v) { return topY + topH - (v - pLo) / (pHi - pLo) * topH; };
      K.niceTicks(pLo, pHi, 5).forEach(function (t) {
        if (t < pLo || t > pHi) return;
        svg.appendChild(K.el("line", { x1: L, x2: W - R, y1: yPrice(t), y2: yPrice(t), stroke: "var(--grid)" }));
        label(svg, L - 6, yPrice(t) + 4, "$" + t, "end");
      });
    } else {
      label(svg, L + 8, topY + 16, "No price in this range. The last price is " + (etf.last_price || "not cached") + ".");
    }

    // Ratio scale, right axis, log.
    var rLo = (rs.length ? Math.min.apply(null, rs.concat([1])) : 0.5) / 1.15;
    var rHi = (rs.length ? Math.max.apply(null, rs.concat([1])) : 2) * 1.15;
    var yRatio = function (v) {
      return topY + topH - (Math.log(v) - Math.log(rLo)) / (Math.log(rHi) - Math.log(rLo)) * topH;
    };
    var ticks = LOG_TICKS.filter(function (t) { return t >= rLo && t <= rHi; });
    while (ticks.length > 7) ticks = ticks.filter(function (t, k) { return k % 2 === 0 || t === 1; });
    ticks.forEach(function (t) { label(svg, W - R + 6, yRatio(t) + 4, String(t), "start"); });
    svg.appendChild(K.el("line", {
      x1: L, x2: W - R, y1: yRatio(1), y2: yRatio(1), stroke: "var(--rule-strong)", "stroke-dasharray": "4 4"
    }));

    axisKey(svg, L, keyH - 4, "Close, $", "start", "var(--ink)");
    axisKey(svg, W - R, keyH - 4, "Put/call, log", "end", "var(--s3)");

    gapLine(svg, ratios, x, yRatio, "var(--s3)", 1.5, i0);
    if (yPrice) gapLine(svg, closes, x, yPrice, "var(--ink)", 2, i0);

    if (etf.last_price && D.dates[i1] > etf.last_price && yPrice) {
      var li = D.dates.indexOf(etf.last_price);
      if (li >= i0) {
        var endX = x(li), far = endX > W - R - 130;
        label(svg, endX + (far ? -6 : 6), yPrice(etf.close[li]) - 8,
          "Price ends " + etf.last_price, far ? "end" : "start", "var(--ink-2)");
      }
    }

    // Premium bars: calls up, puts down, on one scale. A single outlier would flatten
    // every other day, so the scale caps at the 98th percentile when the top value is
    // over three times it. A cut bar carries a notch, and the tooltip keeps its value.
    var prem = finite(calls).concat(finite(puts)).filter(function (v) { return v > 0; })
      .sort(function (a, b) { return a - b; });
    var top = prem.length ? prem[prem.length - 1] : 1;
    var p98 = prem.length ? prem[Math.floor((prem.length - 1) * 0.98)] : 1;
    var cut = top > p98 * 3;
    var maxP = cut ? p98 * 1.1 : top;
    var mid = lowY + lowH / 2, half = lowH / 2 - 2;
    var yBar = function (v) { return Math.min(v, maxP) / maxP * half; };
    K.niceTicks(0, maxP, 2).forEach(function (t) {
      if (t <= 0 || t > maxP) return;
      [mid - yBar(t), mid + yBar(t)].forEach(function (yy) {
        svg.appendChild(K.el("line", { x1: L, x2: W - R, y1: yy, y2: yy, stroke: "var(--grid)" }));
        label(svg, L - 6, yy + 4, compact(t), "end");
      });
    });
    if (cut) label(svg, W - R, lowY - 2, "Notched bars are cut at " + compact(maxP) + ". Hover for the value.", "end", "var(--ink-2)");
    var bw = step > 4 ? step - 2 : Math.max(1, step * 0.8);
    var r = bw >= 6 ? 3 : 0;
    function notch(cx, yy) {
      svg.appendChild(K.el("line", {
        x1: cx - bw / 2 - 1, x2: cx + bw / 2 + 1, y1: yy, y2: yy, stroke: "var(--panel)", "stroke-width": 2
      }));
    }
    calls.forEach(function (v, k) {
      if (!v) return;
      var h = Math.max(1, yBar(v)), cx = x(k + i0);
      svg.appendChild(K.el("path", { d: K.roundedTop(cx - bw / 2, mid - 1 - h, bw, h, r), fill: "var(--s1)" }));
      if (v > maxP) notch(cx, mid - 1 - h + 6);
    });
    puts.forEach(function (v, k) {
      if (!v) return;
      var h = Math.max(1, yBar(v)), cx = x(k + i0);
      svg.appendChild(K.el("path", { d: K.roundedBottom(cx - bw / 2, mid + 1, bw, h, r), fill: "var(--s2)" }));
      if (v > maxP) notch(cx, mid + 1 + h - 6);
    });
    svg.appendChild(K.el("line", { x1: L, x2: W - R, y1: mid, y2: mid, stroke: "var(--rule-strong)" }));

    // Crosshair and tooltip.
    var guide = K.el("line", {
      y1: topY, y2: lowY + lowH, stroke: "var(--ink-3)", visibility: "hidden", "pointer-events": "none"
    });
    svg.appendChild(guide);
    var hit = K.el("rect", { x: L, y: topY, width: W - L - R, height: lowY + lowH - topY, fill: "transparent" });
    svg.appendChild(hit);

    var cur = null;
    function show(i, evt) {
      cur = i;
      guide.setAttribute("x1", x(i));
      guide.setAttribute("x2", x(i));
      guide.setAttribute("visibility", "visible");
      K.showTip(evt, etf.sym + " " + D.dates[i], [
        { color: "var(--ink)", value: etf.close[i] === null ? "no data" : "$" + etf.close[i].toFixed(2), name: "close" },
        { color: "var(--s3)", value: etf.ratio[i] === null ? "blank" : etf.ratio[i].toFixed(2), name: "put/call" },
        { color: "var(--s1)", value: compact(etf.call[i]), name: "call premium" },
        { color: "var(--s2)", value: compact(etf.put[i]), name: "put premium" }
      ]);
    }
    function hide() { guide.setAttribute("visibility", "hidden"); K.hideTip(); }
    hit.addEventListener("pointermove", function (e) {
      var box = svg.getBoundingClientRect();
      var sx = (e.clientX - box.left) * W / box.width;
      show(Math.min(i1, Math.max(i0, i0 + Math.floor((sx - L) / step))), e);
    });
    hit.addEventListener("pointerleave", hide);
    svg.addEventListener("blur", hide);
    svg.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      var i = cur === null ? i1 : cur + (e.key === "ArrowLeft" ? -1 : 1);
      i = Math.min(i1, Math.max(i0, i));
      var box = svg.getBoundingClientRect();
      show(i, { clientX: box.left + x(i) * box.width / W, clientY: box.top + topY * box.height / H });
    });

    host.textContent = "";
    host.appendChild(svg);

    // The same dates as a table, newest first.
    var rows = [];
    for (var i = i1; i >= i0; i--) {
      rows.push([D.dates[i],
        etf.close[i] === null ? "" : etf.close[i].toFixed(2),
        etf.ratio[i] === null ? "" : etf.ratio[i].toFixed(2),
        etf.call[i] === null ? "" : compact(etf.call[i]),
        etf.put[i] === null ? "" : compact(etf.put[i])]);
    }
    K.buildTable(fig.table, ["Date", "Close", "Put/call", "Call premium", "Put premium"], rows);
  }

  function drawAll() { K.hideTip(); figures.forEach(draw); }

  function controls() {
    var host = document.getElementById("pc-controls");
    var sw = K.h("div", "switch");
    sw.setAttribute("role", "group");
    sw.setAttribute("aria-label", "Date range");
    RANGES.forEach(function (r) {
      var b = K.h("button", null, r[0]);
      b.type = "button";
      b.setAttribute("aria-pressed", r[1] === range ? "true" : "false");
      b.addEventListener("click", function () {
        range = r[1];
        sw.querySelectorAll("button").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
        drawAll();
      });
      sw.appendChild(b);
    });
    host.appendChild(sw);
    host.appendChild(K.legend([
      { color: "var(--ink)", label: "Close", line: true },
      { color: "var(--s3)", label: "Put/call ratio", line: true },
      { color: "var(--s1)", label: "Call premium" },
      { color: "var(--s2)", label: "Put premium" }
    ]));
  }

  function figure(etf) {
    var box = K.h("figure", "panel pc-etf");
    box.style.margin = "0 0 18px";
    var title = K.h("h3", null, etf.sym);
    title.appendChild(K.h("span", null, etf.name));
    box.appendChild(title);
    box.appendChild(K.h("div", "pc-meta",
      "Last price " + (etf.last_price || "none") + " · " + etf.n_blank + " sessions with no flow row · " +
      etf.n_no_ratio + " sessions with a zero side, ratio blank"));
    var host = K.h("div", "pc-host");
    box.appendChild(host);
    var det = K.h("details");
    det.appendChild(K.h("summary", null, "Show these dates as a table"));
    var table = K.h("div", "pc-table");
    det.appendChild(table);
    box.appendChild(det);
    document.getElementById("pc-etfs").appendChild(box);
    figures.push({ etf: etf, host: host, table: table });
  }

  controls();
  D.etfs.forEach(figure);
  drawAll();

  var lastW = 0, pending = null;
  window.addEventListener("resize", function () {
    if (window.innerWidth === lastW) return;
    lastW = window.innerWidth;
    clearTimeout(pending);
    pending = setTimeout(drawAll, 120);
  });
})();
