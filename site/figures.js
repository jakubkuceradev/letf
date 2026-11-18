// Static method figures for the article body. Each function returns an element built with
// Observable Plot; the caller supplies plain data from method.json or chart.json and tokens.

/* global Plot */

import { logTicks } from "./charts.js";

const mult = (v) => (v >= 100 ? `${v.toFixed(0)}×` : v >= 10 ? `${v.toFixed(1)}×` : `${v.toFixed(2)}×`);
const pctPts = (v) => `${v.toFixed(1)}%`;
const halo = (t) => ({ stroke: t.surface, strokeWidth: 4, paintOrder: "stroke" });
const frame = (width, height, t, extra = {}) => ({
  width,
  height,
  marginLeft: 56,
  marginRight: 24,
  marginBottom: 40,
  style: { background: "transparent", color: t.textSecondary, fontSize: "12px", overflow: "visible" },
  ...extra,
});
const tip = (t) => ({ fill: t.surface, stroke: t.grid });
const toDate = (s) => new Date(`${s}T00:00:00Z`);

// Figure: monthly cost drag against the financing rate, one panel per fund, with the fitted line.
export function costFit(fund, width, t) {
  const pts = fund.month.map((m, i) => ({ date: m, rate: fund.rate[i], drag: fund.drag[i] }));
  const xs = pts.map((p) => p.rate);
  const line = [Math.min(...xs), Math.max(...xs)].map((x) => ({ rate: x, drag: -fund.fit_k * x - fund.fit_s }));
  const lo = Math.min(...pts.map((p) => p.drag));
  const hi = Math.max(...pts.map((p) => p.drag));
  return Plot.plot({
    ...frame(width, 260, t),
    x: { label: "Federal funds rate (% a year) →", tickFormat: (v) => `${v}%` },
    y: {
      label: "↑ Cost beyond fees (% a year)",
      tickFormat: (v) => `${v}%`,
      domain: [Math.max(lo, -25), Math.min(hi, 10)],
      clamp: true,
    },
    marks: [
      Plot.gridY({ stroke: t.grid, strokeOpacity: 1 }),
      Plot.ruleY([0], { stroke: t.axis }),
      Plot.dot(pts, { x: "rate", y: "drag", r: 2.5, fill: t.series1, fillOpacity: 0.45 }),
      Plot.line(line, { x: "rate", y: "drag", stroke: t.textPrimary, strokeWidth: 2 }),
      Plot.text([`fit: −${fund.fit_k.toFixed(2)} × rate − ${fund.fit_s.toFixed(2)}%`], {
        frameAnchor: "top-right",
        dy: 4,
        dx: -4,
        fill: t.textPrimary,
        ...halo(t),
      }),
      Plot.tip(
        pts,
        Plot.pointer({
          x: "rate",
          y: "drag",
          title: (d) => `${d.drag.toFixed(1)}% cost\n${d.rate.toFixed(2)}% rate, ${d.date.slice(0, 7)}`,
          ...tip(t),
        }),
      ),
    ],
  });
}

// Figure: growth of 1 in the real fund against the model, log scale.
export function actualVsRebuilt(fund, width, t) {
  const rows = fund.month.map((m, i) => ({ date: toDate(m), actual: fund.actual[i], rebuilt: fund.rebuilt[i] }));
  const long = rows.flatMap((r) => [
    { date: r.date, value: r.actual, series: `${fund.ticker} (actual)` },
    { date: r.date, value: r.rebuilt, series: "Model" },
  ]);
  const ticks = logTicks(long.map((d) => d.value));
  return Plot.plot({
    ...frame(width, 260, t),
    x: { label: null },
    y: { label: "↑ Growth of 1 (log scale)", type: "log", ticks, tickFormat: mult },
    color: { domain: [`${fund.ticker} (actual)`, "Model"], range: [t.series1, t.series2] },
    marks: [
      Plot.gridY(ticks, { stroke: t.grid, strokeOpacity: 1 }),
      Plot.line(long, { x: "date", y: "value", stroke: "series", strokeWidth: 2 }),
      Plot.ruleX(rows, Plot.pointerX({ x: "date", stroke: t.axis })),
      Plot.tip(
        rows,
        Plot.pointerX({
          x: "date",
          y: "actual",
          title: (d) =>
            `${d.date.toISOString().slice(0, 7)}\n${mult(d.actual)}  ${fund.ticker} (actual)\n${mult(d.rebuilt)}  Model`,
          ...tip(t),
        }),
      ),
    ],
  });
}

// Figure: real growth of 1 since 1957 for the index and the rebuilt 2x and 3x funds.
export function history(h, width, t) {
  const names = { sp500: "S&P 500", letf2: "Rebuilt 2x", letf3: "Rebuilt 3x" };
  const colors = { sp500: t.series2, letf2: t.series3, letf3: t.series1 };
  const rows = h.month.map((m, i) => ({ date: toDate(m), sp500: h.sp500[i], letf2: h.letf2[i], letf3: h.letf3[i] }));
  const long = rows.flatMap((r) => Object.keys(names).map((k) => ({ date: r.date, value: r[k], series: names[k] })));
  const ends = Object.keys(names).map((k) => ({ date: rows.at(-1).date, value: rows.at(-1)[k], series: names[k] }));
  const ticks = logTicks(long.map((d) => d.value));
  return Plot.plot({
    ...frame(width, 340, t, { marginRight: width < 500 ? 24 : 80 }),
    x: { label: null },
    y: { label: "↑ Real growth of 1 (log scale)", type: "log", ticks, tickFormat: mult },
    color: { domain: Object.values(names), range: Object.keys(names).map((k) => colors[k]) },
    marks: [
      Plot.gridY(ticks, { stroke: t.grid, strokeOpacity: 1 }),
      Plot.ruleY([1], { stroke: t.axis }),
      Plot.line(long, { x: "date", y: "value", stroke: "series", strokeWidth: 1.5 }),
      width < 500
        ? null
        : Plot.text(ends, { x: "date", y: "value", text: "series", textAnchor: "start", dx: 6, fill: t.textPrimary, ...halo(t) }),
      Plot.ruleX(rows, Plot.pointerX({ x: "date", stroke: t.axis })),
      Plot.tip(
        rows,
        Plot.pointerX({
          x: "date",
          y: "letf3",
          title: (d) =>
            `${d.date.toISOString().slice(0, 7)}\n${mult(d.letf3)}  Rebuilt 3x\n${mult(d.letf2)}  Rebuilt 2x\n${mult(d.sp500)}  S&P 500`,
          ...tip(t),
        }),
      ),
    ],
  });
}

// Figure: the federal funds rate over the same period.
export function fedFunds(h, width, t) {
  const rows = h.month.map((m, i) => ({ date: toDate(m), rate: h.fed_funds[i] }));
  return Plot.plot({
    ...frame(width, 140, t, { marginBottom: 28 }),
    x: { label: null },
    y: { label: "↑ Fed funds rate", tickFormat: (v) => `${v}%`, ticks: 3 },
    marks: [
      Plot.gridY({ ticks: 3, stroke: t.grid, strokeOpacity: 1 }),
      Plot.areaY(rows, { x: "date", y: "rate", fill: t.textMuted, fillOpacity: 0.2 }),
      Plot.line(rows, { x: "date", y: "rate", stroke: t.textSecondary, strokeWidth: 1.5 }),
      Plot.ruleX(rows, Plot.pointerX({ x: "date", stroke: t.axis })),
      Plot.tip(
        rows,
        Plot.pointerX({ x: "date", y: "rate", title: (d) => `${d.rate.toFixed(2)}%\n${d.date.toISOString().slice(0, 7)}`, ...tip(t) }),
      ),
    ],
  });
}

// Figure: what borrowing for stock exposure costs, per borrowed dollar, today.
export function borrowing(b, width, t) {
  const rows = b.rows.map((r) => ({ ...r, mid: (r.low + r.high) / 2 }));
  const narrow = width < 560;
  return Plot.plot({
    ...frame(width, 44 + rows.length * 34, t, { marginLeft: narrow ? 8 : 230, marginBottom: 36 }),
    x: { label: "Cost per borrowed dollar (% a year) →", domain: [0, 13], tickFormat: (v) => `${v}%` },
    y: { label: null, domain: rows.map((r) => r.name), axis: narrow ? null : "left", tickSize: 0 },
    marks: [
      Plot.gridX({ stroke: t.grid, strokeOpacity: 1 }),
      Plot.ruleX([b.fed_funds], { stroke: t.textPrimary, strokeWidth: 1 }),
      Plot.text([b.fed_funds], {
        x: (d) => d,
        frameAnchor: "top",
        text: () => `fed funds ${b.fed_funds.toFixed(2)}%`,
        textAnchor: "start",
        dx: 4,
        dy: -2,
        fill: t.textSecondary,
      }),
      Plot.ruleY(rows, {
        x1: "low",
        x2: (d) => Math.max(d.high, d.low + 0.12),
        y: "name",
        stroke: (d) => (d.letf ? t.series1 : t.textMuted),
        strokeWidth: 10,
        strokeLinecap: "round",
      }),
      narrow
        ? Plot.text(rows, { x: "high", y: "name", text: "name", textAnchor: "start", dx: 10, fill: t.textPrimary, fontSize: 11, ...halo(t) })
        : null,
      Plot.tip(
        rows,
        Plot.pointerY({
          x: "mid",
          y: "name",
          title: (d) =>
            `${d.low === d.high ? pctPts(d.low) : `${pctPts(d.low)}–${pctPts(d.high)}`}\n${d.name}\n${d.note}`,
          ...tip(t),
        }),
      ),
    ],
  });
}

// Figure: how outcomes spread with the horizon, baseline against a small 3x slice.
export function fan(data, share, width, t) {
  const L = data.letf["3"];
  const j = data.weights.findIndex((w) => Math.abs(w - share) < 1e-9);
  const rows = data.horizons.flatMap((h, a) => [
    { h, series: "100% S&P 500", p10: L.terminal_wealth[a][0][9], p50: L.terminal_wealth[a][0][49], p90: L.terminal_wealth[a][0][89] },
    {
      h,
      series: `${Math.round(share * 100)}% 3x`,
      p10: L.terminal_wealth[a][j][9],
      p50: L.terminal_wealth[a][j][49],
      p90: L.terminal_wealth[a][j][89],
    },
  ]);
  const ticks = logTicks(rows.flatMap((r) => [r.p10, r.p90]));
  const names = ["100% S&P 500", `${Math.round(share * 100)}% 3x`];
  const wide = rows.filter((r) => r.series === names[0]).map((b, i) => ({ ...b, mix: rows.filter((r) => r.series === names[1])[i] }));
  return Plot.plot({
    ...frame(width, 320, t),
    x: { label: "Horizon (years) →", domain: [1, 50] },
    y: { label: "↑ Real wealth (log scale)", type: "log", ticks, tickFormat: mult },
    color: { domain: names, range: [t.series2, t.series1] },
    marks: [
      Plot.gridY(ticks, { stroke: t.grid, strokeOpacity: 1 }),
      Plot.areaY(rows, { x: "h", y1: "p10", y2: "p90", fill: "series", fillOpacity: 0.14 }),
      Plot.line(rows, { x: "h", y: "p10", stroke: "series", strokeWidth: 1, strokeOpacity: 0.8 }),
      Plot.line(rows, { x: "h", y: "p90", stroke: "series", strokeWidth: 1, strokeOpacity: 0.8 }),
      Plot.line(rows, { x: "h", y: "p50", stroke: "series", strokeWidth: 2 }),
      Plot.ruleX(wide, Plot.pointerX({ x: "h", stroke: t.axis })),
      Plot.tip(
        wide,
        Plot.pointerX({
          x: "h",
          y: "p50",
          title: (d) =>
            `${d.h} years\n${names[1]}: ${mult(d.mix.p10)} · ${mult(d.mix.p50)} · ${mult(d.mix.p90)}\n` +
            `${names[0]}: ${mult(d.p10)} · ${mult(d.p50)} · ${mult(d.p90)}\n(10th · median · 90th percentile)`,
          ...tip(t),
        }),
      ),
    ],
  });
}
