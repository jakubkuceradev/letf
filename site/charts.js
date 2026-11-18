// Pure render functions. Each takes plain arrays and design tokens and returns an SVG
// element built with Observable Plot (global `Plot`, vendored UMD build).

/* global Plot */

const pct = (v) => `${Math.round(v * 100)}%`;
const mult = (v) => (v >= 100 ? `${v.toFixed(0)}×` : v >= 10 ? `${v.toFixed(1)}×` : `${v.toFixed(2)}×`);
export const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
};

export const METRICS = {
  terminal_wealth: {
    label: "Real terminal wealth (multiple of the starting amount)",
    short: "Wealth",
    fmt: mult,
    log: true,
    better: "higher",
  },
  max_drawdown: {
    label: "Maximum drawdown (worst fall from a peak)",
    short: "Max drawdown",
    fmt: pct,
    log: false,
    better: "lower",
  },
  underwater_years: {
    label: "Longest time below a previous peak (years)",
    short: "Time under water",
    fmt: (v) => `${v.toFixed(1)} yr`,
    log: false,
    better: "lower",
  },
};

// 1-2-5 ticks on a log scale, thinned to powers of ten when there are too many.
export function logTicks(values) {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const ticks = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** e;
      if (v >= lo / 1.05 && v <= hi * 1.05) ticks.push(v);
    }
  }
  if (ticks.length > 7) return ticks.filter((v) => Math.abs(Math.log10(v) % 1) < 1e-9);
  return ticks.length >= 2 ? ticks : [lo, hi];
}

const PERCENTILE_TICKS = [5, 25, 50, 75, 95];
const halo = (tokens) => ({ stroke: tokens.surface, strokeWidth: 4, paintOrder: "stroke" });

function base(width, height, tokens) {
  return {
    width,
    height,
    marginLeft: 56,
    marginRight: 24,
    marginBottom: 40,
    style: { background: "transparent", color: tokens.textSecondary, fontSize: "12px", overflow: "visible" },
  };
}

// View 1: selected metric at the selected percentile against the LETF share.
export function shareView({ rows, metric, wStar, width, tokens, letf }) {
  const m = METRICS[metric];
  const baseline = rows[0].value;
  const yTicks = m.log ? logTicks(rows.map((r) => r.value)) : undefined;
  const marks = [
    Plot.gridY(yTicks ?? { ticks: 5 }, { stroke: tokens.grid, strokeOpacity: 1 }),
    Plot.ruleY([baseline], { stroke: tokens.axis, strokeWidth: 1 }),
    Plot.text([{ x: 1, y: baseline }], {
      x: "x",
      y: "y",
      text: () => "100% S&P 500",
      textAnchor: "end",
      dy: -6,
      fill: tokens.textMuted,
      ...halo(tokens),
    }),
    Plot.line(rows, { x: "w", y: "value", stroke: tokens.series1, strokeWidth: 2 }),
    Plot.dot(rows, { x: "w", y: "value", fill: tokens.series1, r: 3 }),
  ];
  if (metric === "terminal_wealth") {
    const best = rows.find((r) => Math.abs(r.w - wStar) < 1e-9);
    marks.push(
      Plot.ruleX([wStar], { stroke: tokens.textPrimary, strokeWidth: 1 }),
      Plot.dot([best], { x: "w", y: "value", r: 6, fill: tokens.series1, stroke: tokens.surface, strokeWidth: 2 }),
      Plot.text([best], {
        x: "w",
        y: "value",
        text: () => `best: ${pct(wStar)}`,
        dy: -14,
        textAnchor: wStar > 0.7 ? "end" : "start",
        fill: tokens.textPrimary,
        fontWeight: 600,
        ...halo(tokens),
      }),
    );
  }
  marks.push(
    Plot.ruleX(rows, Plot.pointerX({ x: "w", stroke: tokens.axis })),
    Plot.tip(
      rows,
      Plot.pointerX({
        x: "w",
        y: "value",
        title: (d) => `${m.fmt(d.value)}\n${pct(d.w)} in ${letf}`,
        fill: tokens.surface,
        stroke: tokens.grid,
      }),
    ),
  );
  return Plot.plot({
    ...base(width, 300, tokens),
    x: { label: `Share in the ${letf} LETF →`, tickFormat: pct, domain: [0, 1], ticks: width < 500 ? 3 : 6 },
    y: {
      label: `↑ ${m.short} (${m.better} is better)`,
      type: m.log ? "log" : "linear",
      tickFormat: m.fmt,
      nice: !m.log,
      zero: !m.log,
      ticks: yTicks ?? 5,
      // Headroom above the highest point so the "best" label never meets the axis title.
      domain: m.log
        ? [Math.min(...rows.map((r) => r.value)) / 1.15, Math.max(...rows.map((r) => r.value)) * 1.8]
        : undefined,
    },
    marks,
  });
}

// View 2: terminal wealth across percentiles for the baseline and the selected mix.
export function distributionView({ rows, crossings, percentile, mixLabel, width, tokens }) {
  const long = rows.flatMap((r) => [
    { p: r.p, value: r.base, series: "100% S&P 500" },
    { p: r.p, value: r.mix, series: mixLabel },
  ]);
  const cross = crossings.map((c) => {
    const i = Math.min(98, Math.max(0, Math.floor(c) - 1));
    const a = rows[i];
    const b = rows[Math.min(98, i + 1)];
    const t = c - a.p;
    const v = Math.exp(Math.log(a.base) + t * (Math.log(b.base) - Math.log(a.base)));
    return { p: c, value: v };
  });
  const yTicks = logTicks(rows.flatMap((r) => [r.base, r.mix]));
  return Plot.plot({
    ...base(width, 300, tokens),
    x: { label: "Percentile of outcomes →", domain: [1, 99], ticks: PERCENTILE_TICKS },
    y: { label: "↑ Real terminal wealth", type: "log", tickFormat: mult, ticks: yTicks },
    color: { domain: ["100% S&P 500", mixLabel], range: [tokens.series2, tokens.series1] },
    marks: [
      Plot.gridY(yTicks, { stroke: tokens.grid, strokeOpacity: 1 }),
      Plot.ruleX([percentile], { stroke: tokens.textPrimary, strokeWidth: 1 }),
      Plot.line(long, { x: "p", y: "value", stroke: "series", strokeWidth: 2 }),
      Plot.dot(cross, { x: "p", y: "value", r: 5, fill: tokens.surface, stroke: tokens.textPrimary, strokeWidth: 2 }),
      Plot.text(cross, {
        x: "p",
        y: "value",
        text: (d) => `crossover ≈ ${ordinal(Math.round(d.p))}`,
        dy: -14,
        textAnchor: "end",
        dx: -6,
        fill: tokens.textPrimary,
        ...halo(tokens),
      }),
      Plot.ruleX(rows, Plot.pointerX({ x: "p", stroke: tokens.axis })),
      Plot.tip(
        rows,
        Plot.pointerX({
          x: "p",
          y: "mix",
          title: (d) =>
            `${ordinal(d.p)} percentile\n${mult(d.mix)}  ${mixLabel}\n${mult(d.base)}  100% S&P 500`,
          fill: tokens.surface,
          stroke: tokens.grid,
        }),
      ),
    ],
  });
}

// View 3: heatmap of w* by horizon and percentile cutoff.
export function heatmapView({ cells, horizon, percentile, width, tokens, letf, onPick }) {
  const plot = Plot.plot({
    ...base(width, 340, tokens),
    marginBottom: 44,
    x: { label: "Horizon (years) →", domain: [0.5, 50.5], ticks: width < 500 ? [1, 25, 50] : [1, 10, 20, 30, 40, 50] },
    y: { label: "↑ Percentile cutoff", domain: [0.5, 99.5], ticks: PERCENTILE_TICKS },
    color: {
      type: "linear",
      domain: [0, 1],
      range: tokens.seq,
      interpolate: "rgb",
      legend: true,
      label: `Best share in ${letf}`,
      tickFormat: pct,
    },
    marks: [
      Plot.rect(cells, {
        x1: (d) => d.h - 0.5,
        x2: (d) => d.h + 0.5,
        y1: (d) => d.p - 0.5,
        y2: (d) => d.p + 0.5,
        fill: "w",
        inset: 0,
        shapeRendering: "crispEdges",
      }),
      Plot.rect([{ h: horizon, p: percentile }], {
        x1: (d) => d.h - 0.5,
        x2: (d) => d.h + 0.5,
        y1: (d) => d.p - 0.5,
        y2: (d) => d.p + 0.5,
        stroke: tokens.textPrimary,
        strokeWidth: 2,
        fill: "none",
      }),
      Plot.ruleX([horizon], { stroke: tokens.textPrimary, strokeOpacity: 0.35 }),
      Plot.ruleY([percentile], { stroke: tokens.textPrimary, strokeOpacity: 0.35 }),
      Plot.tip(
        cells,
        Plot.pointer({
          x: "h",
          y: "p",
          title: (d) => `${pct(d.w)} best share\n${ordinal(d.p)} percentile, ${d.h} years`,
          fill: tokens.surface,
          stroke: tokens.grid,
        }),
      ),
    ],
  });
  const svg = plot.tagName.toLowerCase() === "svg" ? plot : plot.querySelector("svg:last-of-type");
  plot.addEventListener("click", () => {
    const d = plot.value;
    if (d) onPick(d.h, d.p);
  });
  svg?.setAttribute("role", "img");
  return plot;
}
