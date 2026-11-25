/* Workspace 1: Distribution Explorer & Comparator */

import { apiRequest, downloadBackendPng, downloadJson } from "../api.js";
import { downloadSvgElement, renderDistributionChart } from "../chart.js";
import { DEFAULT_EXPLORER, appState, escHtml, fmtNum, fmtPct, syncUrlState } from "../state.js";

let _evalTimer = null;
let _lastData = null;
let _lastExport = null;

function qs(id) {
  return document.getElementById(id);
}

function currentMeta() {
  return appState.catalog?.distributions.find((d) => d.id === appState.explorer.dist);
}

function updateBoundVisibility() {
  const r = appState.explorer.region;
  const showA = r === "left" || r === "interval" || r === "two_tailed";
  const showB = r === "right" || r === "interval" || r === "two_tailed";
  qs("exp-a-wrap").classList.toggle("hidden", !showA);
  qs("exp-b-wrap").classList.toggle("hidden", !showB);
}

function renderParamControls() {
  const meta = currentMeta();
  if (!meta) return;
  const wrap = qs("exp-params-wrap");
  wrap.replaceChildren();
  qs("exp-note").textContent = `${meta.support} · ${meta.note}`;

  for (const ps of meta.params) {
    const curVal = appState.explorer.params[ps.name] ?? ps.default;
    const field = document.createElement("label");
    field.className = "field";
    field.textContent = ps.label;

    const row = document.createElement("div");
    row.className = "slider-row";

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = String(ps.slider_min);
    slider.max = String(ps.slider_max);
    slider.step = String(ps.step);
    slider.value = String(Math.min(ps.slider_max, Math.max(ps.slider_min, curVal)));

    const num = document.createElement("input");
    num.type = "number";
    num.className = "input";
    num.step = ps.kind === "int" ? "1" : "any";
    if (ps.min !== null) num.min = String(ps.min);
    if (ps.max !== null) num.max = String(ps.max);
    num.value = String(curVal);

    const applyVal = (raw) => {
      const v = ps.kind === "int" ? Math.round(Number(raw)) : Number(raw);
      if (!Number.isFinite(v)) return;
      appState.explorer.params[ps.name] = v;
      scheduleEvaluate(40);
    };

    slider.addEventListener("input", () => {
      num.value = slider.value;
      applyVal(slider.value);
    });
    num.addEventListener("input", () => {
      const n = Number(num.value);
      if (Number.isFinite(n)) {
        slider.value = String(Math.min(ps.slider_max, Math.max(ps.slider_min, n)));
        applyVal(n);
      }
    });

    row.append(slider, num);
    field.appendChild(row);
    wrap.appendChild(field);
  }
}

function renderOverlaysList() {
  const wrap = qs("exp-overlays-list");
  wrap.replaceChildren();
  const ovs = appState.explorer.overlays;
  if (!ovs.length) {
    const empty = document.createElement("div");
    empty.className = "chart-hint";
    empty.textContent = "None — click “+ Add Current” to pin a curve and compare.";
    wrap.appendChild(empty);
    return;
  }
  ovs.forEach((ov, idx) => {
    const chip = document.createElement("div");
    chip.className = "overlay-chip";
    const span = document.createElement("span");
    span.className = "mono";
    const args = Object.entries(ov.params || {})
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    span.textContent = ov.label || `${ov.dist}(${args})`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-sm";
    btn.textContent = "×";
    btn.setAttribute("aria-label", "Remove overlay");
    btn.addEventListener("click", () => {
      appState.explorer.overlays.splice(idx, 1);
      renderOverlaysList();
      evaluateNow();
    });
    chip.append(span, btn);
    wrap.appendChild(chip);
  });
}

function renderSummaryStrip(summary) {
  const strip = qs("exp-summary-strip");
  const cells = [
    ["Mean", summary.mean, summary.moment_notes?.mean],
    ["Variance", summary.variance, summary.moment_notes?.variance],
    ["Std Dev", summary.std, summary.moment_notes?.variance],
    ["Median", summary.median, null],
    ["Mode", summary.mode_label || summary.mode, summary.moment_notes?.mode],
    ["Skewness", summary.skewness, summary.moment_notes?.skewness],
    ["Ex. Kurtosis", summary.excess_kurtosis, summary.moment_notes?.excess_kurtosis],
    ["Entropy (nats)", summary.entropy, null],
  ];
  strip.innerHTML = cells
    .map(([k, v, note]) => {
      const display = typeof v === "string" ? escHtml(v) : v !== null && v !== undefined ? fmtNum(v) : "Undefined";
      const title = note ? ` title="${escHtml(note)}"` : "";
      return `<div class="metric-cell"${title}><div class="metric-k">${escHtml(k)}</div><div class="metric-v mono">${display}</div></div>`;
    })
    .join("");
}

function renderExplorerData(data) {
  _lastData = data;
  appState.lastResult = data;
  qs("exp-error").classList.add("hidden");
  qs("exp-notation").textContent = data.notation;
  qs("exp-chart-title").textContent = `${data.name} · ${data.expression}`;
  qs("exp-prob-expr").textContent = data.expression;
  qs("exp-prob-val").textContent = data.probability !== null ? fmtNum(data.probability) : "—";
  qs("exp-comp-text").textContent =
    data.complement !== null ? `Complement: ${fmtNum(data.complement)} (${fmtPct(data.complement)})` : "";

  renderSummaryStrip(data.summary);

  _lastExport = renderDistributionChart(qs("exp-svg"), data, {
    onDragBounds: (a, b) => {
      if (a !== null && Number.isFinite(a)) {
        appState.explorer.a = a;
        qs("exp-bound-a").value = fmtNum(a, "6");
      }
      if (b !== null && Number.isFinite(b)) {
        appState.explorer.b = b;
        qs("exp-bound-b").value = fmtNum(b, "6");
      }
      scheduleEvaluate(70);
    },
    onCommitBounds: (a, b) => {
      if (a !== null && Number.isFinite(a)) appState.explorer.a = a;
      if (b !== null && Number.isFinite(b)) appState.explorer.b = b;
      evaluateNow();
    },
  });
  appState.lastExportSpec = _lastExport;
  appState.snippetCtx = {
    workspace: "explorer",
    payload: {
      endpoint: "/api/v2/dist/evaluate",
      body: {
        dist: appState.explorer.dist,
        params: appState.explorer.params,
        region: appState.explorer.region,
        a: appState.explorer.a,
        b: appState.explorer.b,
        view: appState.explorer.view,
        overlays: appState.explorer.overlays,
      },
      meta: {
        dist: data.dist,
        params: data.params,
        region: data.region,
        a: data.a,
        b: data.b,
        expression: data.expression,
        formulaLatex: data.formula_latex,
      },
    },
  };
  document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
}

export async function evaluateNow() {
  syncUrlState();
  try {
    const body = {
      dist: appState.explorer.dist,
      params: appState.explorer.params,
      region: appState.explorer.region,
      a: appState.explorer.a,
      b: appState.explorer.b,
      view: appState.explorer.view,
      overlays: appState.explorer.overlays,
    };
    const data = await apiRequest("/api/v2/dist/evaluate", {
      method: "POST",
      body,
      channel: "explorer-eval",
    });
    renderExplorerData(data);
  } catch (err) {
    if (err.name === "AbortError") return;
    const errBox = qs("exp-error");
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  }
}

function scheduleEvaluate(ms = 60) {
  if (_evalTimer) clearTimeout(_evalTimer);
  _evalTimer = setTimeout(() => evaluateNow(), ms);
}

export function selectDistribution(distId, customParams = null) {
  appState.explorer.dist = distId;
  const meta = currentMeta();
  if (!meta) return;
  if (customParams) {
    appState.explorer.params = { ...customParams };
  } else {
    const defaults = {};
    meta.params.forEach((ps) => {
      defaults[ps.name] = ps.default;
    });
    appState.explorer.params = defaults;
    // Sensible default bounds per distribution
    if (distId === "normal") {
      appState.explorer.a = -1.959964;
      appState.explorer.b = 1.959964;
    } else if (distId === "beta") {
      appState.explorer.a = 0.2;
      appState.explorer.b = 0.8;
    } else if (distId === "uniform") {
      appState.explorer.a = 0.25;
      appState.explorer.b = 0.75;
    } else if (meta.family === "discrete") {
      appState.explorer.a = 1;
      appState.explorer.b = 5;
    } else {
      appState.explorer.a = 1.0;
      appState.explorer.b = 4.0;
    }
    qs("exp-bound-a").value = String(appState.explorer.a);
    qs("exp-bound-b").value = String(appState.explorer.b);
  }
  qs("exp-dist-select").value = distId;
  renderParamControls();
  updateBoundVisibility();
  evaluateNow();
}

export function applyPreset(preset) {
  appState.explorer.dist = preset.dist;
  appState.explorer.params = { ...preset.params };
  appState.explorer.region = preset.region;
  appState.explorer.a = preset.a;
  appState.explorer.b = preset.b;
  appState.explorer.overlays = structuredClone(preset.overlays || []);
  qs("exp-dist-select").value = preset.dist;
  if (preset.a !== null) qs("exp-bound-a").value = String(preset.a);
  if (preset.b !== null) qs("exp-bound-b").value = String(preset.b);
  qs("exp-region-group")
    .querySelectorAll(".seg-btn")
    .forEach((btn) => btn.classList.toggle("is-active", btn.dataset.region === preset.region));
  renderParamControls();
  renderOverlaysList();
  updateBoundVisibility();
  evaluateNow();
}

export function resetExplorer() {
  appState.explorer = structuredClone(DEFAULT_EXPLORER);
  qs("exp-dist-select").value = DEFAULT_EXPLORER.dist;
  qs("exp-bound-a").value = String(DEFAULT_EXPLORER.a);
  qs("exp-bound-b").value = String(DEFAULT_EXPLORER.b);
  qs("exp-region-group")
    .querySelectorAll(".seg-btn")
    .forEach((btn) => btn.classList.toggle("is-active", btn.dataset.region === DEFAULT_EXPLORER.region));
  qs("exp-view-toggle")
    .querySelectorAll(".seg-btn")
    .forEach((btn) => btn.classList.toggle("is-active", btn.dataset.view === DEFAULT_EXPLORER.view));
  renderParamControls();
  renderOverlaysList();
  updateBoundVisibility();
  evaluateNow();
}

export function refreshExplorerTheme() {
  if (_lastData) renderExplorerData(_lastData);
}

export function initExplorer(catalog) {
  appState.catalog = catalog;
  const sel = qs("exp-dist-select");
  sel.replaceChildren();
  const contGrp = document.createElement("optgroup");
  contGrp.label = "Continuous (9)";
  const discGrp = document.createElement("optgroup");
  discGrp.label = "Discrete (5)";
  for (const d of catalog.distributions) {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = d.name;
    (d.family === "continuous" ? contGrp : discGrp).appendChild(opt);
  }
  sel.append(contGrp, discGrp);
  sel.value = appState.explorer.dist;

  // Presets bar
  const pBar = qs("exp-presets-bar");
  pBar.replaceChildren();
  for (const preset of catalog.presets) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "preset-pill";
    btn.textContent = preset.title;
    btn.title = preset.subtitle;
    btn.addEventListener("click", () => applyPreset(preset));
    pBar.appendChild(btn);
  }

  sel.addEventListener("change", () => selectDistribution(sel.value));

  // Region buttons
  qs("exp-region-group")
    .querySelectorAll(".seg-btn")
    .forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.region === appState.explorer.region);
      btn.addEventListener("click", () => {
        appState.explorer.region = btn.dataset.region;
        qs("exp-region-group")
          .querySelectorAll(".seg-btn")
          .forEach((b) => b.classList.toggle("is-active", b === btn));
        updateBoundVisibility();
        evaluateNow();
      });
    });

  // PDF/CDF toggle
  qs("exp-view-toggle")
    .querySelectorAll(".seg-btn")
    .forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.view === appState.explorer.view);
      btn.addEventListener("click", () => {
        appState.explorer.view = btn.dataset.view;
        qs("exp-view-toggle")
          .querySelectorAll(".seg-btn")
          .forEach((b) => b.classList.toggle("is-active", b === btn));
        evaluateNow();
      });
    });

  // Direct bound inputs
  qs("exp-bound-a").value = appState.explorer.a ?? "";
  qs("exp-bound-b").value = appState.explorer.b ?? "";
  qs("exp-bound-a").addEventListener("input", () => {
    const v = Number(qs("exp-bound-a").value);
    if (Number.isFinite(v)) {
      appState.explorer.a = v;
      scheduleEvaluate(80);
    }
  });
  qs("exp-bound-b").addEventListener("input", () => {
    const v = Number(qs("exp-bound-b").value);
    if (Number.isFinite(v)) {
      appState.explorer.b = v;
      scheduleEvaluate(80);
    }
  });

  // Two-way Quantile / Inverse snap
  async function snapToTargetP(pVal) {
    const q = Number(pVal);
    if (!Number.isFinite(q) || q <= 0 || q >= 1) {
      qs("exp-error").textContent = "Target probability p must be strictly in (0, 1)";
      qs("exp-error").classList.remove("hidden");
      return;
    }
    const region = appState.explorer.region === "none" ? "two_tailed" : appState.explorer.region;
    try {
      const res = await apiRequest("/api/v2/dist/quantile", {
        method: "POST",
        body: { dist: appState.explorer.dist, params: appState.explorer.params, target_p: q, region },
      });
      if (res.a !== null) {
        appState.explorer.a = res.a;
        qs("exp-bound-a").value = fmtNum(res.a, "6");
      }
      if (res.b !== null) {
        appState.explorer.b = res.b;
        qs("exp-bound-b").value = fmtNum(res.b, "6");
      }
      await evaluateNow();
    } catch (err) {
      qs("exp-error").textContent = err.message;
      qs("exp-error").classList.remove("hidden");
    }
  }

  qs("btn-snap-p").addEventListener("click", () => snapToTargetP(qs("exp-target-p").value));
  qs("exp-target-p").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      snapToTargetP(qs("exp-target-p").value);
    }
  });
  document.querySelectorAll(".p-quick").forEach((btn) => {
    btn.addEventListener("click", () => {
      qs("exp-target-p").value = btn.dataset.p;
      snapToTargetP(btn.dataset.p);
    });
  });

  // Add overlay
  qs("btn-add-overlay").addEventListener("click", () => {
    if (appState.explorer.overlays.length >= 2) {
      qs("exp-error").textContent = "Maximum of 3 total curves (1 primary + 2 overlays) reached.";
      qs("exp-error").classList.remove("hidden");
      return;
    }
    const args = Object.entries(appState.explorer.params)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    appState.explorer.overlays.push({
      dist: appState.explorer.dist,
      params: { ...appState.explorer.params },
      label: `${currentMeta()?.name || appState.explorer.dist} (${args})`,
    });
    renderOverlaysList();
    evaluateNow();
  });

  // Exports
  qs("exp-export-svg").addEventListener("click", () => downloadSvgElement(qs("exp-svg"), `p05-${appState.explorer.dist}.svg`));
  qs("exp-export-png").addEventListener("click", () => downloadBackendPng(_lastExport, `p05-${appState.explorer.dist}.png`));
  qs("exp-export-json").addEventListener("click", () => downloadJson(_lastData, `p05-${appState.explorer.dist}.json`));

  renderParamControls();
  renderOverlaysList();
  updateBoundVisibility();
  evaluateNow();
}
