/* Workspace 2: Hypothesis Testing, Confidence Intervals & Power Workbench */

import { apiRequest, downloadBackendPng, downloadJson } from "../api.js";
import { downloadSvgElement, renderLineCurveChart, renderNullTailChart } from "../chart.js";
import { appState, escHtml, fmtNum, syncUrlState } from "../state.js";

let _lastData = null;
let _lastExport = null;
let _powerMode = "n"; // "n" | "mde"

let _chiMatrix = [
  [42, 18],
  [28, 32],
];

let _anovaGroups = [
  { label: "Control", n: 25, mean: 12.1, sd: 2.4, values: "11.5, 12.8, 10.9, 13.1, 12.2" },
  { label: "Dose A", n: 25, mean: 13.8, sd: 2.6, values: "13.2, 14.5, 12.9, 14.1, 14.3" },
  { label: "Dose B", n: 25, mean: 15.2, sd: 2.5, values: "14.8, 15.9, 14.4, 15.5, 15.4" },
];

function qs(id) {
  return document.getElementById(id);
}

function showInfError(msg) {
  const el = qs("inf-error");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearInfError() {
  qs("inf-error").classList.add("hidden");
}

function renderMetrics(items) {
  qs("inf-metrics").innerHTML = items
    .map(([k, v]) => `<div class="metric-cell"><div class="metric-k">${escHtml(k)}</div><div class="metric-v mono">${escHtml(v)}</div></div>`)
    .join("");
}

function renderChiGrid() {
  const wrap = qs("inf-chi-grid");
  const cols = _chiMatrix[0].length;
  let html = `<table class="data-table"><thead><tr><th>Row \\ Col</th>`;
  for (let c = 0; c < cols; c += 1) html += `<th>Col ${c + 1}</th>`;
  html += `</tr></thead><tbody>`;
  _chiMatrix.forEach((row, r) => {
    html += `<tr><th class="cell-axis">Row ${r + 1}</th>`;
    row.forEach((val, c) => {
      html += `<td><input class="cell-input chi-cell" type="number" min="0" step="1" data-r="${r}" data-c="${c}" value="${val}"></td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table>`;
  wrap.innerHTML = html;
  wrap.querySelectorAll(".chi-cell").forEach((inp) => {
    inp.addEventListener("input", () => {
      const r = Number(inp.dataset.r);
      const c = Number(inp.dataset.c);
      _chiMatrix[r][c] = Math.max(0, Number(inp.value) || 0);
    });
  });
}

function renderAnovaGroups() {
  const wrap = qs("inf-anova-groups");
  const mode = qs("inf-anova-mode").value;
  wrap.replaceChildren();
  _anovaGroups.forEach((grp, idx) => {
    const box = document.createElement("div");
    box.className = "sub-block";
    if (mode === "summary") {
      box.innerHTML = `
        <div class="grid-4">
          <label class="field">Label<input class="input an-lbl" data-i="${idx}" value="${escHtml(grp.label)}"></label>
          <label class="field">n<input class="input an-n" type="number" min="2" step="1" data-i="${idx}" value="${grp.n}"></label>
          <label class="field">Mean<input class="input an-mean" type="number" step="any" data-i="${idx}" value="${grp.mean}"></label>
          <label class="field">SD<input class="input an-sd" type="number" step="any" min="0" data-i="${idx}" value="${grp.sd}"></label>
        </div>`;
    } else {
      box.innerHTML = `
        <label class="field">Group ${idx + 1} Label<input class="input an-lbl" data-i="${idx}" value="${escHtml(grp.label)}"></label>
        <label class="field">Values (comma/space)<input class="input an-vals" data-i="${idx}" value="${escHtml(grp.values)}"></label>`;
    }
    wrap.appendChild(box);
  });
  wrap.querySelectorAll(".an-lbl").forEach((el) => el.addEventListener("input", () => { _anovaGroups[Number(el.dataset.i)].label = el.value; }));
  wrap.querySelectorAll(".an-n").forEach((el) => el.addEventListener("input", () => { _anovaGroups[Number(el.dataset.i)].n = Number(el.value) || 2; }));
  wrap.querySelectorAll(".an-mean").forEach((el) => el.addEventListener("input", () => { _anovaGroups[Number(el.dataset.i)].mean = Number(el.value) || 0; }));
  wrap.querySelectorAll(".an-sd").forEach((el) => el.addEventListener("input", () => { _anovaGroups[Number(el.dataset.i)].sd = Number(el.value) || 0; }));
  wrap.querySelectorAll(".an-vals").forEach((el) => el.addEventListener("input", () => { _anovaGroups[Number(el.dataset.i)].values = el.value; }));
}

async function runMeans() {
  clearInfError();
  const testType = qs("inf-means-type").value;
  const inputMode = qs("inf-means-mode").value;
  const body = {
    test_type: testType,
    input_mode: inputMode,
    alternative: qs("inf-means-alt").value,
    alpha: Number(qs("inf-means-alpha").value),
    mu0: Number(qs("inf-means-mu0").value),
    pop_sigma: Number(qs("inf-means-popsig").value),
  };
  if (inputMode === "summary") {
    body.mean1 = Number(qs("inf-m1").value);
    body.sd1 = Number(qs("inf-s1").value);
    body.n1 = Number(qs("inf-n1").value);
    if (testType.startsWith("two")) {
      body.mean2 = Number(qs("inf-m2").value);
      body.sd2 = Number(qs("inf-s2").value);
      body.n2 = Number(qs("inf-n2").value);
    }
  } else {
    body.raw1 = qs("inf-raw1").value;
    if (testType.startsWith("two")) body.raw2 = qs("inf-raw2").value;
  }

  const data = await apiRequest("/api/v2/inference/means", { method: "POST", body, channel: "inf" });
  _lastData = data;
  appState.lastResult = data;
  qs("inf-power-curve-toggle").classList.add("hidden");
  qs("inf-chart-title").textContent = `${data.plot.label} · Rejection Region (α = ${data.alpha})`;
  qs("inf-verdict").textContent = data.reject_h0 ? `Reject H₀ at α = ${data.alpha}` : `Fail to reject H₀ at α = ${data.alpha}`;
  qs("inf-subreadout").textContent = `${data.statistic_name} = ${fmtNum(data.statistic)} · CI(${Math.round(data.ci_level * 100)}%): [${fmtNum(data.ci[0])}, ${fmtNum(data.ci[1])}]`;
  qs("inf-main-stat").textContent = `p = ${fmtNum(data.p_value)}`;
  renderMetrics([
    [`${data.statistic_name}-statistic`, fmtNum(data.statistic)],
    ["df", data.df !== null ? fmtNum(data.df) : "∞ (z)"],
    ["p-value", fmtNum(data.p_value)],
    ["Cohen's d", fmtNum(data.cohens_d)],
  ]);
  qs("inf-extra-tables").innerHTML = "";
  _lastExport = renderNullTailChart(qs("inf-svg"), data.plot, qs("inf-chart-title").textContent);
  appState.lastExportSpec = _lastExport;
  appState.snippetCtx = {
    workspace: "inference",
    payload: {
      endpoint: "/api/v2/inference/means",
      body,
      python: `from scipy import stats\n# ${testType}: stat=${data.statistic?.toFixed(5)}, p=${data.p_value?.toExponential(4)}, cohens_d=${data.cohens_d?.toFixed(4)}`,
      r: `# ${testType}: stat = ${data.statistic?.toFixed(5)}, p.value = ${data.p_value?.toExponential(4)}`,
      latex: `\\text{stat} = ${fmtNum(data.statistic)}, \\quad p = ${fmtNum(data.p_value)}, \\quad d = ${fmtNum(data.cohens_d)}`,
    },
  };
  document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
}

async function runProps() {
  clearInfError();
  const testType = qs("inf-props-type").value;
  const body = {
    test_type: testType,
    alternative: qs("inf-props-alt").value,
    alpha: Number(qs("inf-props-alpha").value),
    x1: Number(qs("inf-px1").value),
    n1: Number(qs("inf-pn1").value),
    p0: Number(qs("inf-pp0").value),
  };
  if (testType === "two_prop") {
    body.x2 = Number(qs("inf-px2").value);
    body.n2 = Number(qs("inf-pn2").value);
  }
  const data = await apiRequest("/api/v2/inference/proportions", { method: "POST", body, channel: "inf" });
  _lastData = data;
  appState.lastResult = data;
  qs("inf-power-curve-toggle").classList.add("hidden");
  qs("inf-chart-title").textContent = `Proportions z-Test · N(0, 1) (α = ${data.alpha})`;
  qs("inf-verdict").textContent = data.reject_h0 ? `Reject H₀ at α = ${data.alpha}` : `Fail to reject H₀ at α = ${data.alpha}`;
  qs("inf-main-stat").textContent = `p = ${fmtNum(data.p_value)}`;

  if (testType === "two_prop") {
    qs("inf-subreadout").textContent = `p₁=${fmtNum(data.p1)}, p₂=${fmtNum(data.p2)} · Diff CI: [${fmtNum(data.diff_ci[0])}, ${fmtNum(data.diff_ci[1])}]`;
    renderMetrics([
      ["z-statistic", fmtNum(data.statistic)],
      ["Abs Lift", fmtNum(data.lift_abs)],
      ["Rel Lift", data.lift_rel !== null ? `${(data.lift_rel * 100).toFixed(2)}%` : "—"],
      ["Cohen's h", fmtNum(data.cohens_h)],
    ]);
    qs("inf-extra-tables").innerHTML = `<table class="data-table"><thead><tr><th>Group</th><th>Proportion</th><th>Wilson ${Math.round(data.ci_level * 100)}% CI</th></tr></thead><tbody><tr><td>Control</td><td class="mono">${fmtNum(data.p1)}</td><td class="mono">[${fmtNum(data.wilson_ci_1[0])}, ${fmtNum(data.wilson_ci_1[1])}]</td></tr><tr><td>Variant</td><td class="mono">${fmtNum(data.p2)}</td><td class="mono">[${fmtNum(data.wilson_ci_2[0])}, ${fmtNum(data.wilson_ci_2[1])}]</td></tr></tbody></table>`;
  } else {
    qs("inf-subreadout").textContent = `p̂=${fmtNum(data.p1)} vs p₀=${fmtNum(data.p0)} · Wilson CI: [${fmtNum(data.wilson_ci_1[0])}, ${fmtNum(data.wilson_ci_1[1])}]`;
    renderMetrics([
      ["z-statistic", fmtNum(data.statistic)],
      ["p̂", fmtNum(data.p1)],
      ["p-value", fmtNum(data.p_value)],
      ["Cohen's h", fmtNum(data.cohens_h)],
    ]);
    qs("inf-extra-tables").innerHTML = "";
  }
  _lastExport = renderNullTailChart(qs("inf-svg"), data.plot, qs("inf-chart-title").textContent);
  appState.lastExportSpec = _lastExport;
  appState.snippetCtx = { workspace: "inference", payload: { endpoint: "/api/v2/inference/proportions", body } };
  document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
}

function drawPowerChart(data) {
  const btn = qs("inf-power-curve-toggle");
  btn.classList.remove("hidden");
  btn.textContent = _powerMode === "n" ? "Switch Curve: vs MDE" : "Switch Curve: vs Sample Size n";
  if (_powerMode === "n") {
    const xs = data.power_vs_n.map((pt) => pt.n);
    const ys = data.power_vs_n.map((pt) => pt.power);
    _lastExport = renderLineCurveChart(qs("inf-svg"), xs, ys, {
      title: `Statistical Power vs Sample Size n/group (${data.effect_summary})`,
      xlabel: "Sample Size per Group (n)",
      ylabel: "Power (1 − β)",
      refX: data.n_per_group,
      refY: data.achieved_power,
    });
  } else {
    const xs = data.power_vs_mde.map((pt) => pt.mde);
    const ys = data.power_vs_mde.map((pt) => pt.power);
    _lastExport = renderLineCurveChart(qs("inf-svg"), xs, ys, {
      title: `Statistical Power vs Minimum Detectable Effect (n=${data.n_per_group}/group)`,
      xlabel: "Minimum Detectable Effect (MDE)",
      ylabel: "Power (1 − β)",
      refX: data.mde,
      refY: data.achieved_power,
    });
  }
  appState.lastExportSpec = _lastExport;
}

async function runPower() {
  clearInfError();
  const body = {
    mode: qs("inf-pw-mode").value,
    solve_for: qs("inf-pw-solve").value,
    alternative: qs("inf-pw-alt").value,
    alpha: Number(qs("inf-pw-alpha").value),
    target_power: Number(qs("inf-pw-target").value),
    n_per_group: Number(qs("inf-pw-n").value),
    p1: Number(qs("inf-pw-p1").value),
    p2: Number(qs("inf-pw-p2").value),
    mean_diff: Number(qs("inf-pw-diff").value),
    sd: Number(qs("inf-pw-sd").value),
  };
  const data = await apiRequest("/api/v2/inference/power", { method: "POST", body, channel: "inf" });
  _lastData = data;
  appState.lastResult = data;
  qs("inf-chart-title").textContent = "Statistical Power Curve";
  qs("inf-verdict").textContent = `${data.mode} · ${data.effect_summary}`;
  qs("inf-subreadout").textContent = `Total N = ${data.total_n.toLocaleString()} · α = ${data.alpha} (${data.alternative})`;
  qs("inf-main-stat").textContent =
    body.solve_for === "sample_size" ? `n = ${data.n_per_group}/grp` : `Power = ${(data.achieved_power * 100).toFixed(2)}%`;
  renderMetrics([
    ["n / group", String(data.n_per_group)],
    ["Total N", String(data.total_n)],
    ["Achieved Power", fmtNum(data.achieved_power)],
    ["MDE", fmtNum(data.mde)],
  ]);
  qs("inf-extra-tables").innerHTML = "";
  drawPowerChart(data);
  appState.snippetCtx = { workspace: "inference", payload: { endpoint: "/api/v2/inference/power", body } };
  document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
}

async function runChisq() {
  clearInfError();
  const mode = qs("inf-chi-mode").value;
  const body = { mode, alpha: Number(qs("inf-chi-alpha").value) };
  if (mode === "gof") {
    body.observed_1d = qs("inf-chi-obs").value.split(/[\s,;]+/).filter(Boolean).map(Number);
    const expRaw = qs("inf-chi-exp").value.trim();
    if (expRaw) body.expected_1d = expRaw.split(/[\s,;]+/).filter(Boolean).map(Number);
  } else {
    body.table = _chiMatrix;
  }
  const data = await apiRequest("/api/v2/inference/chisq", { method: "POST", body, channel: "inf" });
  _lastData = data;
  appState.lastResult = data;
  qs("inf-power-curve-toggle").classList.add("hidden");
  qs("inf-chart-title").textContent = `χ²(df = ${data.df}) Test`;
  qs("inf-verdict").textContent = data.reject_h0 ? `Reject H₀ at α = ${data.alpha}` : `Fail to reject H₀ at α = ${data.alpha}`;
  qs("inf-subreadout").textContent = data.low_expected_warning
    ? `Warning: ${data.low_expected_cells} cell(s) have expected count < 5`
    : `All expected cell counts ≥ 5`;
  qs("inf-main-stat").textContent = `p = ${fmtNum(data.p_value)}`;
  renderMetrics([
    ["χ² statistic", fmtNum(data.statistic)],
    ["df", String(data.df)],
    ["p-value", fmtNum(data.p_value)],
    [data.effect_size_name, fmtNum(data.effect_size)],
  ]);

  if (mode === "independence") {
    const rows = data.expected
      .map((row, r) => {
        const cells = row
          .map((eVal, c) => `<td class="mono">${fmtNum(eVal, "2")} <span class="chart-hint">(z=${fmtNum(data.standardized_residuals[r][c], "2")})</span></td>`)
          .join("");
        return `<tr><th>Row ${r + 1}</th>${cells}</tr>`;
      })
      .join("");
    qs("inf-extra-tables").innerHTML = `<table class="data-table"><thead><tr><th>Expected (Adj. Residual)</th>${data.expected[0].map((_, c) => `<th>Col ${c + 1}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
  } else {
    const rows = data.observed
      .map((o, i) => `<tr><th>Cat ${i + 1}</th><td class="mono">${fmtNum(o, "2")}</td><td class="mono">${fmtNum(data.expected[i], "2")}</td><td class="mono">${fmtNum(data.standardized_residuals[i], "2")}</td></tr>`)
      .join("");
    qs("inf-extra-tables").innerHTML = `<table class="data-table"><thead><tr><th>Category</th><th>Observed</th><th>Expected</th><th>Std Residual</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  _lastExport = renderNullTailChart(qs("inf-svg"), data.plot, qs("inf-chart-title").textContent);
  appState.lastExportSpec = _lastExport;
  appState.snippetCtx = { workspace: "inference", payload: { endpoint: "/api/v2/inference/chisq", body } };
  document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
}

async function runAnova() {
  clearInfError();
  const mode = qs("inf-anova-mode").value;
  const body = { input_mode: mode, alpha: Number(qs("inf-anova-alpha").value) };
  if (mode === "summary") {
    body.groups_summary = _anovaGroups.map((g) => ({ label: g.label, n: g.n, mean: g.mean, sd: g.sd }));
  } else {
    body.groups_raw = _anovaGroups.map((g) => ({ label: g.label, values: g.values }));
  }
  const data = await apiRequest("/api/v2/inference/anova", { method: "POST", body, channel: "inf" });
  _lastData = data;
  appState.lastResult = data;
  qs("inf-power-curve-toggle").classList.add("hidden");
  qs("inf-chart-title").textContent = `One-Way ANOVA · F(${data.df_between}, ${data.df_within})`;
  qs("inf-verdict").textContent = data.reject_h0 ? `Reject H₀ (group means differ)` : `Fail to reject H₀`;
  qs("inf-subreadout").textContent = `Grand Mean = ${fmtNum(data.grand_mean)} · df = (${data.df_between}, ${data.df_within})`;
  qs("inf-main-stat").textContent = `p = ${fmtNum(data.p_value)}`;
  renderMetrics([
    ["F statistic", fmtNum(data.f_stat)],
    ["p-value", fmtNum(data.p_value)],
    ["η² (Eta-sq)", fmtNum(data.eta_squared)],
    ["ω² (Omega-sq)", fmtNum(data.omega_squared)],
  ]);

  const tblRows = data.table
    .map(
      (r) =>
        `<tr><td>${escHtml(r.source)}</td><td class="mono">${fmtNum(r.ss)}</td><td class="mono">${r.df}</td><td class="mono">${r.ms !== null ? fmtNum(r.ms) : "—"}</td><td class="mono">${r.f !== null ? fmtNum(r.f) : "—"}</td><td class="mono">${r.p_value !== null ? fmtNum(r.p_value) : "—"}</td></tr>`
    )
    .join("");
  qs("inf-extra-tables").innerHTML = `<table class="data-table"><thead><tr><th>Source</th><th>SS</th><th>df</th><th>MS</th><th>F</th><th>p-value</th></tr></thead><tbody>${tblRows}</tbody></table>`;

  _lastExport = renderNullTailChart(qs("inf-svg"), data.plot, qs("inf-chart-title").textContent);
  appState.lastExportSpec = _lastExport;
  appState.snippetCtx = { workspace: "inference", payload: { endpoint: "/api/v2/inference/anova", body } };
  document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
}

async function runActiveSub() {
  try {
    if (appState.inferenceSub === "means") await runMeans();
    else if (appState.inferenceSub === "props") await runProps();
    else if (appState.inferenceSub === "power") await runPower();
    else if (appState.inferenceSub === "chisq") await runChisq();
    else if (appState.inferenceSub === "anova") await runAnova();
  } catch (err) {
    if (err.name !== "AbortError") showInfError(err.message);
  }
}

export function switchInferenceSub(sub) {
  appState.inferenceSub = sub;
  syncUrlState();
  qs("inf-subtabs")
    .querySelectorAll(".seg-btn")
    .forEach((b) => b.classList.toggle("is-active", b.dataset.inf === sub));
  ["means", "props", "power", "chisq", "anova"].forEach((s) => {
    qs(`inf-form-${s}`).classList.toggle("hidden", s !== sub);
  });
  runActiveSub();
}

export function refreshInferenceTheme() {
  if (!_lastData) return;
  if (appState.inferenceSub === "power") drawPowerChart(_lastData);
  else if (_lastData.plot) _lastExport = renderNullTailChart(qs("inf-svg"), _lastData.plot, qs("inf-chart-title").textContent);
}

export function initInference() {
  qs("inf-subtabs")
    .querySelectorAll(".seg-btn")
    .forEach((btn) => btn.addEventListener("click", () => switchInferenceSub(btn.dataset.inf)));

  // Means dynamic toggles
  const syncMeansFields = () => {
    const t = qs("inf-means-type").value;
    const m = qs("inf-means-mode").value;
    const isOne = t.startsWith("one");
    qs("inf-means-one-opts").classList.toggle("hidden", !isOne);
    qs("inf-means-popsig-wrap").classList.toggle("hidden", t !== "one_sample_z");
    qs("inf-means-summary-fields").classList.toggle("hidden", m !== "summary");
    qs("inf-means-raw-fields").classList.toggle("hidden", m !== "raw");
    qs("inf-means-g2-summary").classList.toggle("hidden", isOne);
    qs("inf-means-g2-raw").classList.toggle("hidden", isOne);
  };
  qs("inf-means-type").addEventListener("change", syncMeansFields);
  qs("inf-means-mode").addEventListener("change", syncMeansFields);
  syncMeansFields();

  // Props toggle
  const syncPropsFields = () => {
    const t = qs("inf-props-type").value;
    qs("inf-props-g2").classList.toggle("hidden", t !== "two_prop");
    qs("inf-props-p0-wrap").classList.toggle("hidden", t !== "one_prop");
  };
  qs("inf-props-type").addEventListener("change", syncPropsFields);
  syncPropsFields();

  // Power toggles
  const syncPowerFields = () => {
    const mode = qs("inf-pw-mode").value;
    const solve = qs("inf-pw-solve").value;
    qs("inf-pw-prop-fields").classList.toggle("hidden", mode !== "two_prop");
    qs("inf-pw-mean-fields").classList.toggle("hidden", mode === "two_prop");
    qs("inf-pw-target-wrap").classList.toggle("hidden", solve !== "sample_size");
    qs("inf-pw-n-wrap").classList.toggle("hidden", solve !== "power");
  };
  qs("inf-pw-mode").addEventListener("change", syncPowerFields);
  qs("inf-pw-solve").addEventListener("change", syncPowerFields);
  syncPowerFields();

  qs("inf-power-curve-toggle").addEventListener("click", () => {
    _powerMode = _powerMode === "n" ? "mde" : "n";
    if (_lastData && appState.inferenceSub === "power") drawPowerChart(_lastData);
  });

  // Chi-squared table controls
  const syncChiMode = () => {
    const m = qs("inf-chi-mode").value;
    qs("inf-chi-rxc-wrap").classList.toggle("hidden", m !== "independence");
    qs("inf-chi-gof-wrap").classList.toggle("hidden", m !== "gof");
  };
  qs("inf-chi-mode").addEventListener("change", syncChiMode);
  renderChiGrid();
  qs("btn-chi-add-row").addEventListener("click", () => {
    if (_chiMatrix.length >= 8) return;
    _chiMatrix.push(new Array(_chiMatrix[0].length).fill(10));
    renderChiGrid();
  });
  qs("btn-chi-rem-row").addEventListener("click", () => {
    if (_chiMatrix.length <= 2) return;
    _chiMatrix.pop();
    renderChiGrid();
  });
  qs("btn-chi-add-col").addEventListener("click", () => {
    if (_chiMatrix[0].length >= 8) return;
    _chiMatrix.forEach((r) => r.push(10));
    renderChiGrid();
  });
  qs("btn-chi-rem-col").addEventListener("click", () => {
    if (_chiMatrix[0].length <= 2) return;
    _chiMatrix.forEach((r) => r.pop());
    renderChiGrid();
  });

  // ANOVA controls
  renderAnovaGroups();
  qs("inf-anova-mode").addEventListener("change", renderAnovaGroups);
  qs("btn-anova-add-grp").addEventListener("click", () => {
    if (_anovaGroups.length >= 8) return;
    _anovaGroups.push({ label: `Group ${_anovaGroups.length + 1}`, n: 20, mean: 14.0, sd: 2.5, values: "13, 14, 15, 14.5" });
    renderAnovaGroups();
  });
  qs("btn-anova-rem-grp").addEventListener("click", () => {
    if (_anovaGroups.length <= 2) return;
    _anovaGroups.pop();
    renderAnovaGroups();
  });

  // Form submits
  ["means", "props", "power", "chisq", "anova"].forEach((s) => {
    qs(`inf-form-${s}`).addEventListener("submit", (e) => {
      e.preventDefault();
      runActiveSub();
    });
  });

  // Exports
  qs("inf-export-svg").addEventListener("click", () => downloadSvgElement(qs("inf-svg"), `p05-${appState.inferenceSub}.svg`));
  qs("inf-export-png").addEventListener("click", () => downloadBackendPng(_lastExport, `p05-${appState.inferenceSub}.png`));
  qs("inf-export-json").addEventListener("click", () => downloadJson(_lastData, `p05-${appState.inferenceSub}.json`));

  switchInferenceSub(appState.inferenceSub);
}
