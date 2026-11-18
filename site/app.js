import { distributionView, heatmapView, METRICS, ordinal, outcomeIndex, shareView } from "./charts.js";
import * as figs from "./figures.js";

const SETTINGS = {
  main: { label: "Main: annual rebalancing, 1-year blocks, fitted spread", file: "chart.json" },
  rebalance_quarterly: { label: "Quarterly rebalancing" },
  rebalance_none: { label: "No rebalancing" },
  block_1m: { label: "1-month blocks" },
  block_6m: { label: "6-month blocks" },
  block_2y: { label: "2-year blocks" },
  block_5y: { label: "5-year blocks" },
  block_10y: { label: "10-year blocks" },
  spread_min: { label: "Borrowing spread at its rolling minimum" },
  spread_max: { label: "Borrowing spread at its rolling maximum" },
};

const state = { letf: "3", percentile: 10, horizon: 50, mix: 0.1, metric: "terminal_wealth", setting: "main" };
const cache = new Map();
let current = null; // data currently shown
let shownSetting = "main"; // setting whose data is in `current`

const $ = (sel) => document.querySelector(sel);
const pct = (v, digits = 0) => `${(v * 100).toFixed(digits)}%`;
const years = (n) => `${n} ${n === 1 ? "year" : "years"}`;

// ---------- number binding for the article text ----------

const FORMATS = {
  pct: (v) => pct(v),
  pct1: (v) => pct(v, 1),
  pct2: (v) => pct(v, 2),
  pctabs: (v) => pct(Math.abs(v)),
  pctsigned: (v) => `${v >= 0 ? "+" : "−"}${pct(Math.abs(v))}`,
  pctsigned1: (v) => `${v >= 0 ? "+" : "−"}${pct(Math.abs(v), 1)}`,
  xplain: (v) => `${v.toFixed(1)}×`,
  x: (v) => `${v.toFixed(2)}×`,
  x1: (v) => `${v.toFixed(1)}×`,
  int: (v) => Math.round(v).toLocaleString("en-US"),
  dec2: (v) => v.toFixed(2),
  years: (v) => `${v.toFixed(1)} years`,
  yearsint: (v) => `${Math.round(v)}`,
  ord: (v) => ordinal(Math.round(v)),
  pp: (v) => `${Math.abs(v).toFixed(2)} percentage points`,
  date: (v) => new Date(`${v}T00:00:00Z`).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" }),
  year: (v) => v.slice(0, 4),
  text: (v) => String(v),
};

async function bindNumbers() {
  const res = await fetch("data/summary.json");
  if (!res.ok) throw new Error(`summary.json: HTTP ${res.status}`);
  const nums = await res.json();
  for (const el of document.querySelectorAll("[data-num]")) {
    const v = nums[el.dataset.num];
    const fmt = FORMATS[el.dataset.fmt || "text"];
    el.textContent = v === undefined || v === null ? "n/a" : fmt(v);
    el.classList.remove("pending");
  }
}

// ---------- data ----------

function load(setting) {
  if (!cache.has(setting)) {
    const file = SETTINGS[setting].file || `chart_${setting}.json`;
    cache.set(
      setting,
      fetch(`data/${file}`)
        .then((r) => {
          if (!r.ok) throw new Error(`${file}: HTTP ${r.status}`);
          return r.json();
        })
        .catch((err) => {
          cache.delete(setting); // let the next selection retry
          throw err;
        }),
    );
  }
  return cache.get(setting);
}

const hi = () => state.horizon - 1;
const pi = () => state.percentile - 1;
const wi = (w) => current.weights.findIndex((x) => Math.abs(x - w) < 1e-9);

// ---------- tokens ----------

function tokens() {
  const css = getComputedStyle(document.documentElement);
  const get = (n) => css.getPropertyValue(n).trim();
  return {
    surface: get("--surface-1"),
    textPrimary: get("--text-primary"),
    textSecondary: get("--text-secondary"),
    textMuted: get("--text-muted"),
    grid: get("--grid"),
    axis: get("--axis"),
    series1: get("--series-1"),
    series2: get("--series-2"),
    series3: get("--series-3"),
    seq: get("--seq").split(",").map((s) => s.trim()),
  };
}

// ---------- tables (the accessible twin of each view) ----------

function fillTable(container, headers, rows) {
  const table = document.createElement("table");
  const head = table.createTHead().insertRow();
  for (const h of headers) {
    const th = document.createElement("th");
    th.textContent = h;
    head.appendChild(th);
  }
  const body = table.createTBody();
  for (const r of rows) {
    const tr = body.insertRow();
    for (const c of r) tr.insertCell().textContent = c;
  }
  container.replaceChildren(table);
}

// ---------- render ----------

function render() {
  if (!current) return;
  const L = current.letf[state.letf];
  const t = tokens();
  const letfName = `${state.letf}x`;
  const wStar = L.w_star[hi()][pi()];
  const m = METRICS[state.metric];

  // View 1
  const k = outcomeIndex(state.metric, state.percentile);
  const shareRows = current.weights.map((w, j) => ({ w, value: L[state.metric][hi()][j][k] }));
  const v1 = $("#view-share");
  v1.querySelector(".sub").textContent =
    `${m.label}, ${ordinal(state.percentile)} percentile of outcomes after ${years(state.horizon)} ` +
    `(${100 - state.percentile}% or more of paths do at least this well).`;
  v1.querySelector("figure").replaceChildren(
    shareView({ rows: shareRows, metric: state.metric, wStar, width: v1.clientWidth, tokens: t, letf: letfName }),
  );
  fillTable(
    v1.querySelector(".scroll"),
    [`Share in ${letfName}`, m.short],
    shareRows.map((r) => [pct(r.w), m.fmt(r.value)]),
  );

  // View 2
  const j = wi(state.mix);
  const mixLabel = `${pct(state.mix)} ${letfName} + ${pct(1 - state.mix)} S&P 500`;
  const distRows = current.percentiles.map((p, k) => ({
    p,
    base: L.terminal_wealth[hi()][0][k],
    mix: L.terminal_wealth[hi()][j][k],
  }));
  const crossings = L.crossovers[hi()][j];
  const v2 = $("#view-dist");
  v2.querySelector(".sub").textContent =
    `Real terminal wealth after ${years(state.horizon)}, every percentile. Log scale.`;
  v2.querySelector(".legend").replaceChildren(
    ...[
      [t.series2, "100% S&P 500"],
      [t.series1, mixLabel],
    ].map(([color, name]) => {
      const span = document.createElement("span");
      const key = document.createElement("span");
      key.className = "key";
      key.style.background = color;
      span.append(key, document.createTextNode(name));
      return span;
    }),
  );
  v2.querySelector("figure").replaceChildren(
    distributionView({
      rows: distRows,
      crossings,
      percentile: state.percentile,
      mixLabel,
      width: v2.clientWidth,
      tokens: t,
    }),
  );
  fillTable(
    v2.querySelector(".scroll"),
    ["Percentile", "100% S&P 500", mixLabel],
    distRows.map((r) => [ordinal(r.p), METRICS.terminal_wealth.fmt(r.base), METRICS.terminal_wealth.fmt(r.mix)]),
  );

  // View 3
  const cells = [];
  current.horizons.forEach((h, a) =>
    current.percentiles.forEach((p, b) => cells.push({ h, p, w: L.w_star[a][b] })),
  );
  const v3 = $("#view-heat");
  v3.querySelector("figure").replaceChildren(
    heatmapView({
      cells,
      horizon: state.horizon,
      percentile: state.percentile,
      width: v3.clientWidth,
      tokens: t,
      letf: letfName,
      onPick: (h, p) => {
        state.horizon = h;
        state.percentile = p;
        syncControls();
        render();
      },
    }),
  );
  fillTable(
    v3.querySelector(".scroll"),
    ["Percentile", `Best share in ${letfName} after ${years(state.horizon)}`],
    current.percentiles.map((p, b) => [ordinal(p), pct(L.w_star[hi()][b])]),
  );

  // Readout
  const beat = 1 - L.p_below_base[hi()][j];
  const ruin = L.p_letf_ruin[hi()];
  const readout = $("#readout");
  readout.replaceChildren();
  const add = (text, strong = false) => {
    const node = strong ? document.createElement("strong") : document.createTextNode(text);
    if (strong) node.textContent = text;
    readout.append(node);
  };
  add(`At the ${ordinal(state.percentile)} percentile after ${years(state.horizon)}, the best share in ${letfName} is `);
  add(pct(wStar), true);
  add(`. A ${pct(state.mix)} mix ends ahead of 100% S&P 500 on `);
  add(pct(beat), true);
  add(` of paths. The ${letfName} part loses 90% or more between rebalances on `);
  add(pct(ruin, 1), true);
  add(" of paths.");
  describeHeatmap();
}

// ---------- controls ----------

function syncControls() {
  $("#percentile").value = state.percentile;
  $("#percentile-out").textContent = ordinal(state.percentile);
  $("#horizon").value = state.horizon;
  $("#horizon-out").textContent = `${state.horizon} yr`;
  $("#mix").value = Math.round(state.mix * 100);
  $("#mix-out").textContent = pct(state.mix);
  $("#metric").value = state.metric;
  $("#setting").value = state.setting;
  for (const b of document.querySelectorAll("#letf button")) {
    b.setAttribute("aria-pressed", String(b.dataset.letf === state.letf));
  }
}

let loadSeq = 0; // only the latest selection may update the views

async function selectSetting(setting) {
  const token = ++loadSeq;
  state.setting = setting;
  syncControls(); // the dropdown always names the setting being loaded or shown
  $("#retry").hidden = true;
  const views = $("#views");
  views.classList.add("loading");
  views.setAttribute("aria-busy", "true");
  try {
    const data = await load(setting);
    if (token !== loadSeq) return;
    current = data;
    shownSetting = setting;
    render();
    $("#chart-error").textContent = "";
  } catch (err) {
    if (token !== loadSeq) return;
    $("#chart-error").textContent = `Could not load ${SETTINGS[setting].label}: ${err.message}`;
    const retry = $("#retry");
    retry.hidden = false;
    retry.onclick = () => selectSetting(setting);
    if (current) {
      state.setting = shownSetting; // the views still show this setting's data
      syncControls();
    } else {
      $("#readout").textContent = "Results are unavailable until the data loads.";
    }
  } finally {
    if (token === loadSeq) {
      views.classList.remove("loading");
      views.setAttribute("aria-busy", "false");
    }
  }
}

function wireControls() {
  const setting = $("#setting");
  for (const [key, s] of Object.entries(SETTINGS)) setting.add(new Option(s.label, key));
  const metric = $("#metric");
  for (const [key, m] of Object.entries(METRICS)) metric.add(new Option(m.short, key));

  const onInput = (id, apply) =>
    $(id).addEventListener("input", (e) => {
      apply(e.target.value);
      syncControls();
      render();
    });
  onInput("#percentile", (v) => (state.percentile = Number(v)));
  onInput("#horizon", (v) => (state.horizon = Number(v)));
  onInput("#mix", (v) => (state.mix = Number(v) / 100));
  onInput("#metric", (v) => (state.metric = v));
  setting.addEventListener("change", (e) => selectSetting(e.target.value));
  for (const b of document.querySelectorAll("#letf button")) {
    b.addEventListener("click", () => {
      state.letf = b.dataset.letf;
      syncControls();
      render();
    });
  }
  syncControls();
}

// Keyboard access for the heatmap: arrows move the selected cell.
function wireHeatmapKeys() {
  const fig = $("#view-heat figure");
  fig.tabIndex = 0;
  fig.setAttribute("role", "group");
  fig.addEventListener("keydown", (e) => {
    const moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowDown: [0, -1], ArrowUp: [0, 1] };
    const mv = moves[e.key];
    if (!mv) return;
    e.preventDefault();
    state.horizon = Math.min(50, Math.max(1, state.horizon + mv[0]));
    state.percentile = Math.min(99, Math.max(1, state.percentile + mv[1]));
    syncControls();
    render();
  });
}

function describeHeatmap() {
  if (!current) return;
  const w = current.letf[state.letf].w_star[hi()][pi()];
  $("#view-heat figure").setAttribute(
    "aria-label",
    `Best share heatmap. Selected: ${years(state.horizon)}, ${ordinal(state.percentile)} percentile, ` +
      `best share ${pct(w)}. Use arrow keys to move.`,
  );
}

// ---------- method figures ----------

let method = null;

function legend(container, items) {
  container.replaceChildren(
    ...items.map(([color, name]) => {
      const span = document.createElement("span");
      const key = document.createElement("span");
      key.className = "key";
      key.style.background = color;
      span.append(key, document.createTextNode(name));
      return span;
    }),
  );
}

const mult = METRICS.terminal_wealth.fmt;

function renderFigures() {
  if (!method) return;
  const t = tokens();
  const panelWidth = (fig, i = 0) => fig.querySelector(`[data-panel="${i}"]`)?.clientWidth || fig.clientWidth;

  // Cost fit
  let fig = $("#fig-costfit");
  method.tracking.forEach((f, i) => {
    fig.querySelector(`[data-panel="${i}"]`).replaceChildren(figs.costFit(f, panelWidth(fig, i), t));
  });
  fillTable(
    fig.querySelector(".scroll"),
    ["Fund", "Leverage", "Rate multiple (fitted)", "Spread (% a year)", "Months"],
    method.tracking.map((f) => [f.ticker, `${f.leverage}x`, f.fit_k.toFixed(2), f.fit_s.toFixed(2), String(f.month.length)]),
  );

  // Model check
  fig = $("#fig-check");
  legend(fig.querySelector(".legend"), [
    [t.series1, "Real fund"],
    [t.series2, "Model"],
  ]);
  method.actual_vs_rebuilt.forEach((f, i) => {
    fig.querySelector(`[data-panel="${i}"]`).replaceChildren(figs.actualVsRebuilt(f, panelWidth(fig, i), t));
  });
  fillTable(
    fig.querySelector(".scroll"),
    ["Fund", "From", "Real fund, growth of 1", "Model, growth of 1", "Out-of-sample tracking difference"],
    method.actual_vs_rebuilt.map((f) => [
      f.ticker,
      f.month[0].slice(0, 7),
      mult(f.actual.at(-1)),
      mult(f.rebuilt.at(-1)),
      `${(100 * f.oos_tracking_diff).toFixed(2)} pp/yr`,
    ]),
  );

  // History
  fig = $("#fig-history");
  legend(fig.querySelector(".legend"), [
    [t.series2, "S&P 500"],
    [t.series3, "Rebuilt 2x"],
    [t.series1, "Rebuilt 3x"],
  ]);
  fig.querySelector('[data-panel="0"]').replaceChildren(figs.history(method.history, panelWidth(fig, 0), t));
  fig.querySelector('[data-panel="1"]').replaceChildren(figs.fedFunds(method.history, panelWidth(fig, 1), t));
  const h = method.history;
  const decades = h.month.map((m, i) => [m, i]).filter(([m]) => m.endsWith("12-31") && Number(m.slice(0, 4)) % 5 === 0);
  fillTable(
    fig.querySelector(".scroll"),
    ["End of year", "S&P 500", "Rebuilt 2x", "Rebuilt 3x", "Fed funds"],
    decades.map(([m, i]) => [m.slice(0, 4), mult(h.sp500[i]), mult(h.letf2[i]), mult(h.letf3[i]), `${h.fed_funds[i].toFixed(2)}%`]),
  );

  // Borrowing
  fig = $("#fig-borrow");
  fig.querySelector(".plot").replaceChildren(figs.borrowing(method.borrowing, fig.querySelector(".plot").clientWidth, t));
  fillTable(
    fig.querySelector(".scroll"),
    ["Route", "Cost (% a year)", "Basis"],
    method.borrowing.rows.map((r) => [
      r.name,
      r.low === r.high ? r.low.toFixed(1) : `${r.low.toFixed(1)}–${r.high.toFixed(1)}`,
      r.note,
    ]),
  );

  // Fan (always the main setting)
  load("main").then((data) => {
    const f = $("#fig-fan");
    legend(f.querySelector(".legend"), [
      [t.series2, "100% S&P 500"],
      [t.series1, "10% 3x + 90% S&P 500"],
    ]);
    f.querySelector(".plot").replaceChildren(figs.fan(data, 0.1, f.querySelector(".plot").clientWidth, t));
    const j = data.weights.findIndex((w) => Math.abs(w - 0.1) < 1e-9);
    const L = data.letf["3"].terminal_wealth;
    fillTable(
      f.querySelector(".scroll"),
      ["Horizon", "Index 10th", "Index median", "Index 90th", "10% 3x 10th", "10% 3x median", "10% 3x 90th"],
      [5, 10, 20, 30, 40, 50].map((hz) => [
        `${hz} yr`,
        ...[0, j].flatMap((w) => [9, 49, 89].map((p) => mult(L[hz - 1][w][p]))),
      ]),
    );
  });
}

async function loadMethod() {
  const res = await fetch("data/method.json");
  if (!res.ok) throw new Error(`method.json: HTTP ${res.status}`);
  method = await res.json();
  renderFigures();
}

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    render();
    renderFigures();
  }, 150);
});
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  render();
  renderFigures();
});

wireControls();
wireHeatmapKeys();
bindNumbers().catch((err) => console.error(err));
loadMethod().catch((err) => console.error(err));
selectSetting("main");

// Exposed for automated checks.
window.__letf = { state, get data() { return current; }, render, selectSetting };
