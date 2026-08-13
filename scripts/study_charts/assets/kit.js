/* Study-chart kit — the layout and drawing primitives every study_charts page
 * shares, with no knowledge of any particular study.
 *
 * Split out of page.js when a second page (the regime readout) needed the same
 * scaffolding. Nothing in here reads a global data payload: every function
 * takes what it draws as an argument, which is what made the split possible at
 * all. Labels come from CSV/report text, so they are inserted with textContent,
 * never innerHTML.
 */
(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  // ---------- small helpers ----------

  function el(tag, attrs, text) {
    var node = document.createElementNS(SVGNS, tag);
    for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) node.setAttribute(k, attrs[k]);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function h(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function money(v, digits) {
    var sign = v < 0 ? "-" : "";
    return sign + "$" + Math.abs(v).toLocaleString("en-US", {
      minimumFractionDigits: digits || 0, maximumFractionDigits: digits || 0
    });
  }

  function signed(v, digits) {
    return (v >= 0 ? "+" : "") + v.toFixed(digits === undefined ? 3 : digits);
  }

  function pct(v, digits) { return (v * 100).toFixed(digits === undefined ? 0 : digits) + "%"; }

  function niceTicks(lo, hi, count) {
    var span = hi - lo;
    if (span <= 0) return [lo];
    var raw = span / (count || 5);
    var mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var norm = raw / mag;
    var step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
    var out = [];
    for (var t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) out.push(Math.round(t / step) * step);
    return out;
  }

  // ---------- tooltip ----------

  var tip = h("div", "tip");
  tip.setAttribute("role", "status");
  document.body.appendChild(tip);

  function showTip(evt, head, rows) {
    tip.textContent = "";
    var headEl = h("div", "tip-head", head);
    tip.appendChild(headEl);
    rows.forEach(function (r) {
      var row = h("div", "tip-row");
      if (r.color) {
        var key = h("span", "tip-key");
        key.style.background = r.color;
        row.appendChild(key);
      }
      row.appendChild(h("span", "tip-val", r.value));
      if (r.name) row.appendChild(h("span", "tip-name", r.name));
      tip.appendChild(row);
    });
    tip.setAttribute("data-show", "true");
    moveTip(evt);
  }

  function moveTip(evt) {
    var pad = 14;
    var box = tip.getBoundingClientRect();
    var x = evt.clientX + pad;
    var y = evt.clientY + pad;
    if (x + box.width > window.innerWidth - 8) x = evt.clientX - box.width - pad;
    if (y + box.height > window.innerHeight - 8) y = evt.clientY - box.height - pad;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  }

  function hideTip() { tip.setAttribute("data-show", "false"); }

  function hoverable(node, head, rows) {
    node.style.cursor = "default";
    node.addEventListener("pointerenter", function (e) { showTip(e, head, rows); });
    node.addEventListener("pointermove", moveTip);
    node.addEventListener("pointerleave", hideTip);
    node.setAttribute("tabindex", "0");
    node.addEventListener("focus", function () {
      var b = node.getBoundingClientRect();
      showTip({ clientX: b.left + b.width / 2, clientY: b.top }, head, rows);
    });
    node.addEventListener("blur", hideTip);
  }

  // ---------- panel scaffolding ----------

  function panel(title, how, opts) {
    var fig = h("figure", "panel");
    var head = h("div", "panel-head");
    var titles = h("div");
    titles.appendChild(h("h3", null, title));
    head.appendChild(titles);
    var body = h("div");
    var table = h("div", "table-view");
    table.hidden = true;
    if (opts && opts.table) {
      var btn = h("button", "table-toggle", "Table");
      btn.type = "button";
      btn.setAttribute("aria-expanded", "false");
      btn.addEventListener("click", function () {
        table.hidden = !table.hidden;
        btn.setAttribute("aria-expanded", String(!table.hidden));
        btn.textContent = table.hidden ? "Table" : "Hide table";
      });
      head.appendChild(btn);
    }
    fig.appendChild(head);
    if (how) fig.appendChild(h("p", "how", how));
    fig.appendChild(body);
    fig.appendChild(table);
    return { figure: fig, body: body, table: table };
  }

  function buildTable(container, columns, rows) {
    container.textContent = "";
    var t = h("table");
    var thead = h("thead");
    var tr = h("tr");
    columns.forEach(function (c) { tr.appendChild(h("th", null, c)); });
    thead.appendChild(tr);
    t.appendChild(thead);
    var tbody = h("tbody");
    rows.forEach(function (r) {
      var row = h("tr");
      r.forEach(function (cell) { row.appendChild(h("td", null, String(cell))); });
      tbody.appendChild(row);
    });
    t.appendChild(tbody);
    container.appendChild(t);
  }

  function legend(items) {
    var ul = h("ul", "legend");
    items.forEach(function (it) {
      var li = h("li");
      var key = h("span", "key" + (it.line ? " line" : ""));
      key.style.background = it.color;
      li.appendChild(key);
      li.appendChild(h("span", null, it.label));
      ul.appendChild(li);
    });
    return ul;
  }

  function svgRoot(width, height) {
    var svg = el("svg", {
      viewBox: "0 0 " + width + " " + height,
      width: width, height: height, role: "img"
    });
    return svg;
  }

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function roundedRight(x, y, w, hgt, r) {
    r = Math.min(r, w);
    return "M" + x + "," + y +
      " H" + (x + w - r) + " Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + r) +
      " V" + (y + hgt - r) + " Q" + (x + w) + "," + (y + hgt) + " " + (x + w - r) + "," + (y + hgt) +
      " H" + x + " Z";
  }

  function roundedTop(x, y, w, hgt, r) {
    r = Math.min(r, hgt, w / 2);
    return "M" + x + "," + (y + hgt) +
      " V" + (y + r) + " Q" + x + "," + y + " " + (x + r) + "," + y +
      " H" + (x + w - r) + " Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + r) +
      " V" + (y + hgt) + " Z";
  }

  function roundedBottom(x, y, w, hgt, r) {
    r = Math.min(r, hgt, w / 2);
    return "M" + x + "," + y +
      " V" + (y + hgt - r) + " Q" + x + "," + (y + hgt) + " " + (x + r) + "," + (y + hgt) +
      " H" + (x + w - r) + " Q" + (x + w) + "," + (y + hgt) + " " + (x + w) + "," + (y + hgt - r) +
      " V" + y + " Z";
  }
  function columnChart(host, tableHost, opts) {
    // opts: {rows:[{label,value,sub}], valueFmt, axisTitle, refLine:{v,label}, emphIndex, tableCols, tableRows}
    var rows = opts.rows;
    // t clears the axis title above the tallest bar's own data label.
    var m = { t: 36, r: 16, b: opts.rotateLabels ? 74 : 52, l: 62 };
    // Keep bands near 90px so a three-category chart is not stretched over 1040px.
    var innerW = Math.min(1040 - m.l - m.r, Math.max(240, rows.length * 90));
    var W = innerW + m.l + m.r, H = 236 + (opts.rotateLabels ? 22 : 0);
    var innerH = H - m.t - m.b;
    var maxV = Math.max.apply(null, rows.map(function (r) { return r.value; }).concat(opts.refLine ? [opts.refLine.v] : []));
    var ticks = niceTicks(0, maxV, 4);
    var yMax = Math.max(ticks[ticks.length - 1], maxV);
    var y = function (v) { return m.t + innerH * (1 - v / (yMax || 1)); };
    var band = innerW / rows.length;
    var barW = Math.min(24, band - 8);

    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, opts.title || ""));
    ticks.forEach(function (t) {
      svg.appendChild(el("line", { class: "gridline", x1: m.l, x2: m.l + innerW, y1: y(t), y2: y(t) }));
      svg.appendChild(el("text", { class: "tick", x: m.l - 10, y: y(t) + 3.5, "text-anchor": "end" }, opts.tickFmt ? opts.tickFmt(t) : String(t)));
    });

    rows.forEach(function (r, i) {
      var cx = m.l + band * i + band / 2;
      var hgt = Math.max(1, y(0) - y(r.value));
      var emph = opts.emphIndex === i;
      var color = emph ? css("--s2") : css("--s1");
      var bar = el("path", { d: roundedTop(cx - barW / 2, y(r.value), barW, hgt, 4), fill: color });
      hoverable(bar, r.label, [{ color: color, value: opts.valueFmt(r.value), name: opts.valueName || "value" }]
        .concat(r.sub ? [{ value: r.sub, name: opts.subName || "" }] : []));
      svg.appendChild(bar);
      if (opts.labelEvery === undefined || i % opts.labelEvery === 0 || emph) {
        svg.appendChild(el("text", { class: "dlabel", x: cx, y: y(r.value) - 7, "text-anchor": "middle" }, opts.valueFmt(r.value)));
      }
      var t = el("text", { class: "tick", x: cx, y: m.t + innerH + 16, "text-anchor": "middle" }, r.label);
      if (opts.rotateLabels) t.setAttribute("transform", "rotate(-38 " + cx + " " + (m.t + innerH + 16) + ")");
      if (opts.rotateLabels) t.setAttribute("text-anchor", "end");
      svg.appendChild(t);
    });

    if (opts.refLine) {
      svg.appendChild(el("line", { class: "refline", x1: m.l, x2: m.l + innerW, y1: y(opts.refLine.v), y2: y(opts.refLine.v) }));
      svg.appendChild(el("text", { class: "tick", x: m.l + innerW, y: y(opts.refLine.v) - 6, "text-anchor": "end" }, opts.refLine.label));
    }
    svg.appendChild(el("line", { class: "baseline", x1: m.l, x2: m.l + innerW, y1: y(0), y2: y(0) }));
    if (opts.axisTitle) svg.appendChild(el("text", { class: "axis-title", x: m.l, y: 12 }, opts.axisTitle));
    host.appendChild(svg);
    if (opts.tableCols) buildTable(tableHost, opts.tableCols, opts.tableRows);
  }

  function divergingBars(host, tableHost, opts) {
    var rows = opts.rows;
    var W = 1040, rowH = 34, m = { t: 22, r: 110, b: 30, l: 176 };
    var H = m.t + rows.length * rowH + m.b;
    var innerW = W - m.l - m.r;
    var vals = rows.map(function (r) { return r.value; });
    var lo = Math.min(0, Math.min.apply(null, vals)), hi = Math.max(0, Math.max.apply(null, vals));
    var ticks = niceTicks(lo, hi, 6);
    var xLo = Math.min(ticks[0], lo), xHi = Math.max(ticks[ticks.length - 1], hi);
    var x = function (v) { return m.l + innerW * (v - xLo) / (xHi - xLo || 1); };

    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, opts.title || ""));
    ticks.forEach(function (t) {
      svg.appendChild(el("line", { class: "gridline", x1: x(t), x2: x(t), y1: m.t, y2: m.t + rows.length * rowH }));
      svg.appendChild(el("text", { class: "tick", x: x(t), y: H - 12, "text-anchor": "middle" }, opts.valueFmt(t)));
    });

    rows.forEach(function (r, i) {
      var yTop = m.t + i * rowH + 6;
      var barH = rowH - 12;
      var color = r.value >= 0 ? css("--s1") : css("--s8");
      var x0 = x(0), x1 = x(r.value);
      var bar = el("path", {
        d: r.value >= 0 ? roundedRight(x0, yTop, Math.max(2, x1 - x0), barH, 4)
          : roundedRight(x1, yTop, Math.max(2, x0 - x1), barH, 4),
        fill: color
      });
      hoverable(bar, r.label, [{ color: color, value: opts.valueFmt(r.value), name: opts.valueName }]
        .concat(r.sub ? [{ value: r.sub, name: opts.subName }] : []));
      svg.appendChild(bar);
      // A long negative bar would push its outside label into the category gutter;
      // when that happens the label moves inside the bar end instead of overprinting.
      var text = opts.valueFmt(r.value);
      var outsideX = r.value >= 0 ? x1 + 10 : x1 - 10;
      var inside = r.value < 0 && outsideX - text.length * 7 < m.l + 6;
      svg.appendChild(el("text", {
        class: inside ? null : "dlabel",
        x: inside ? x1 + 10 : outsideX,
        y: yTop + barH - 5,
        "text-anchor": inside || r.value >= 0 ? "start" : "end",
        "font-size": inside ? 11 : null,
        "font-weight": inside ? 600 : null,
        "font-family": inside ? "var(--mono)" : null,
        fill: inside ? "#ffffff" : null
      }, text));
      svg.appendChild(el("text", { class: "dlabel", x: m.l - 14, y: yTop + barH - 5, "text-anchor": "end" }, r.label));
    });
    svg.appendChild(el("line", { class: "baseline", x1: x(0), x2: x(0), y1: m.t, y2: m.t + rows.length * rowH }));
    if (opts.axisTitle) svg.appendChild(el("text", { class: "axis-title", x: m.l, y: 12 }, opts.axisTitle));
    host.appendChild(svg);
    if (opts.tableCols) buildTable(tableHost, opts.tableCols, opts.tableRows);
  }
  function tile(label, value, sub) {
    var t = h("div", "tile");
    t.appendChild(h("span", "label", label));
    t.appendChild(h("span", "value", value));
    if (sub) t.appendChild(h("span", "sub", sub));
    return t;
  }

  function chipList(items) {
    var wrap = h("div", "chips");
    items.forEach(function (it) {
      var good = it.status === "PASS" || it.status === "MET";
      var row = h("div", "chip " + (good ? "is-good" : "is-bad"));
      row.appendChild(h("span", "id", it.id));
      row.appendChild(h("span", "mark", good ? "✓" : "✗"));
      var mid = h("div");
      mid.appendChild(h("div", "title", it.title));
      if (it.detail) mid.appendChild(h("div", "detail", it.detail));
      row.appendChild(mid);
      row.appendChild(h("span", "state", it.status));
      wrap.appendChild(row);
    });
    return wrap;
  }

  function section(id, title, blurb) {
    var s = h("section");
    s.id = id;
    var head = h("div", "section-head");
    head.appendChild(h("h2", null, title));
    if (blurb) head.appendChild(h("p", null, blurb));
    s.appendChild(head);
    return s;
  }

  function chartHost(fig) {
    var box = h("div", "chart");
    fig.body.appendChild(box);
    return box;
  }

  // ---------- heatmap ----------

  var RAMP = ["--seq-0", "--seq-1", "--seq-2", "--seq-3",
              "--seq-4", "--seq-5", "--seq-6", "--seq-7"];

  function rampStep(v, lo, hi) {
    var t = (v - lo) / (hi - lo || 1);
    return Math.max(0, Math.min(RAMP.length - 1, Math.floor(t * RAMP.length)));
  }

  function rampFill(step) { return css(RAMP[step]); }

  /* Ink chosen by fill luminance so a label always clears its own cell. */
  function rampInk(step) { return step >= 4 ? "#ffffff" : css("--ink"); }

  /* A labelled matrix of cells on the sequential ramp.
   *
   * The ramp is sequential, so `value` must be a magnitude that means more
   * the higher it is — a count, a share. A signed quantity read on a
   * sequential ramp says "big negative" and "big positive" are opposite ends
   * of one scale, which they are not; those belong in divergingBars.
   *
   * spec: {title, rowTitle, cols, rows:[{label, cells:[{value,n,note}|null]}],
   *        fmt, sub, highlight(i,j), footnote, tableCols, tableRows}
   */
  function matrix(host, tableHost, spec) {
    var all = [];
    spec.rows.forEach(function (r) {
      r.cells.forEach(function (c) { if (c) all.push(c.value); });
    });
    var lo = all.length ? Math.min.apply(null, all) : 0;
    var hi = all.length ? Math.max.apply(null, all) : 0;
    var fmt = spec.fmt || String;

    var cellW = Math.max(104, Math.min(180, Math.floor(880 / spec.cols.length)));
    var cellH = spec.sub ? 62 : 48;
    var m = { t: 34, l: 150 };
    var W = m.l + spec.cols.length * cellW + 8;
    var H = m.t + spec.rows.length * cellH + (spec.footnote ? 34 : 10);
    var svg = svgRoot(W, H);
    svg.appendChild(el("title", {}, spec.title));

    spec.cols.forEach(function (label, j) {
      svg.appendChild(el("text", {
        class: "tick", x: m.l + j * cellW + cellW / 2, y: m.t - 12, "text-anchor": "middle"
      }, label));
    });
    if (spec.rowTitle) {
      svg.appendChild(el("text", { class: "axis-title", x: 0, y: m.t - 12 }, spec.rowTitle));
    }

    spec.rows.forEach(function (r, i) {
      svg.appendChild(el("text", {
        class: "tick", x: m.l - 14, y: m.t + i * cellH + cellH / 2 + 4, "text-anchor": "end"
      }, r.label));
      r.cells.forEach(function (c, j) {
        var x = m.l + j * cellW + 1, y = m.t + i * cellH + 1;
        var w = cellW - 3, hgt = cellH - 3;
        if (!c) {
          // An absent cell is drawn as empty, never as a zero: "the book never
          // deployed here" and "it deployed here and made nothing" are
          // different facts and must not share a colour.
          svg.appendChild(el("rect", {
            x: x, y: y, width: w, height: hgt, fill: css("--panel-sunk"), rx: 2
          }));
          return;
        }
        var step = rampStep(c.value, lo, hi);
        var fill = rampFill(step), ink = rampInk(step);
        var rect = el("rect", { x: x, y: y, width: w, height: hgt, fill: fill, rx: 2 });
        hoverable(rect, r.label + "  ×  " + spec.cols[j],
          [{ color: fill, value: fmt(c.value), name: spec.valueName || "value" }]
            .concat(c.n !== undefined ? [{ value: String(c.n), name: "positions" }] : [])
            .concat(c.note ? [{ value: c.note, name: "" }] : []));
        svg.appendChild(rect);
        svg.appendChild(el("text", {
          x: x + w / 2, y: y + (spec.sub ? 26 : 30), "text-anchor": "middle",
          "font-size": 13, "font-weight": 600, fill: ink, "font-family": "var(--mono)"
        }, fmt(c.value)));
        if (spec.sub) {
          svg.appendChild(el("text", {
            x: x + w / 2, y: y + 43, "text-anchor": "middle",
            "font-size": 11, fill: ink, opacity: 0.8, "font-family": "var(--mono)"
          }, spec.sub(c)));
        }
        if (spec.highlight && spec.highlight(i, j)) {
          svg.appendChild(el("rect", {
            x: x - 1, y: y - 1, width: w + 2, height: hgt + 2, fill: "none",
            stroke: css("--s2"), "stroke-width": 2.5, rx: 3
          }));
        }
      });
    });
    if (spec.footnote) {
      svg.appendChild(el("text", { class: "tick", x: m.l, y: H - 10 }, spec.footnote));
    }
    host.appendChild(svg);
    if (spec.tableCols) buildTable(tableHost, spec.tableCols, spec.tableRows);
  }

  window.__STUDY_KIT__ = {
    matrix: matrix,
    rampStep: rampStep,
    rampFill: rampFill,
    rampInk: rampInk,
    el: el,
    h: h,
    money: money,
    signed: signed,
    pct: pct,
    niceTicks: niceTicks,
    showTip: showTip,
    moveTip: moveTip,
    hideTip: hideTip,
    hoverable: hoverable,
    panel: panel,
    buildTable: buildTable,
    legend: legend,
    svgRoot: svgRoot,
    css: css,
    roundedRight: roundedRight,
    roundedTop: roundedTop,
    roundedBottom: roundedBottom,
    columnChart: columnChart,
    divergingBars: divergingBars,
    tile: tile,
    chipList: chipList,
    section: section,
    chartHost: chartHost,
  };
})();
