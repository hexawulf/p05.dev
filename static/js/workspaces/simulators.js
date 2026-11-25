/* Workspace 4: CLT Sampling Distribution Lab & Discrete Joint (X, Y) Matrix */

import { apiRequest, downloadBackendPng, downloadJson } from "../api.js";
import { downloadSvgElement, renderHistogramChart, renderJointHeatmapChart } from "../chart.js";
import { JOINT_PRESETS } from "../presets.js";
import { appState, escHtml, fmtNum, syncUrlState } from "../state.js";

let _lastData = null;
let _lastExport = null;
let _cltTimer = null;

let _jointState = {
  xValues: [0, 1],
  yValues: [0, 1],
  matrix: [
    [0.1, 0.2],
    [0.3, 0.4],
  ],
};

function qs(id) {
  return document.getElementById(id);
}

function showSimError(msg) {
  const el = qs("sim-error");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearSimError() {
  qs("sim-error").classList.add("hidden");
}

function renderMetrics(items) {
  qs("sim-metrics").innerHTML = items
    .map(([k, v]) => `<div class="metric-cell"><div class="metric-k">${escHtml(k)}</div><div class="metric-v mono">${escHtml(v)}</div></div>`)
    .join("");
}

function updateJointSumBadge() {
  const sum = _jointState.matrix.flat().reduce((a, b) => a + b, 0);
  const badge = qs("joint-sum-badge");
  badge.textContent = `Σp = ${sum.toFixed(4)}`;
  const ok = Math.abs(sum - 1.0) <= 1e-6;
  badge.className = `badge mono ${ok ? "badge-ok" : "badge-warn"}`;
}

function renderJointEditor() {
  const wrap = qs("joint-matrix-editor");
  let html = `<table class="data-table"><thead><tr><th>X \\ Y</th>`;
  _jointState.yValues.forEach((yv, j) => {
    html += `<th><input class="cell-input cell-axis jy-val" type="number" step="any" data-j="${j}" value="${yv}" aria-label="Y value"></th>`;
  });
  html += `</tr></thead><tbody>`;
  _jointState.xValues.forEach((xv, i) => {
    html += `<tr><th><input class="cell-input cell-axis jx-val" type="number" step="any" data-i="${i}" value="${xv}" aria-label="X value"></th>`;
    _jointState.yValues.forEach((_, j) => {
      html += `<td><input class="cell-input jp-val" type="number" min="0" step="0.01" data-i="${i}" data-j="${j}" value="${_jointState.matrix[i][j]}"></td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table>`;
  wrap.innerHTML = html;

  wrap.querySelectorAll(".jx-val").forEach((inp) => {
    inp.addEventListener("input", () => {
      const v = Number(inp.value);
      if (Number.isFinite(v)) _jointState.xValues[Number(inp.dataset.i)] = v;
    });
  });
  wrap.querySelectorAll(".jy-val").forEach((inp) => {
    inp.addEventListener("input", () => {
      const v = Number(inp.value);
      if (Number.isFinite(v)) _jointState.yValues[Number(inp.dataset.j)] = v;
    });
  });
  wrap.querySelectorAll(".jp-val").forEach((inp) => {
    inp.addEventListener("input", () => {
      _jointState.matrix[Number(inp.dataset.i)][Number(inp.dataset.j)] = Math.max(0, Number(inp.value) || 0);
      updateJointSumBadge();
    });
  });
  updateJointSumBadge();
}

async function runClt() {
  clearSimError();
  const seedRaw = qs("sim-clt-seed").value.trim();
  const body = {
    population: qs("sim-clt-pop").value,
    n: Number(qs("sim-clt-n").value),
    trials: Number(qs("sim-clt-trials").value),
    bins: Number(qs("sim-clt-bins").value),
    seed: seedRaw === "" ? null : Number(seedRaw),
  };
  try {
    const data = await apiRequest("/api/v2/sim/clt", { method: "POST", body, channel: "sim" });
    _lastData = data;
    appState.lastResult = data;
    qs("sim-chart-title").textContent = `CLT: ${data.population_label} (n = ${data.n}, N = ${data.trials.toLocaleString()})`;
    renderMetrics([
      ["Pop Mean μ", fmtNum(data.theoretical.pop_mean)],
      ["Theo SE (σ/√n)", fmtNum(data.theoretical.se)],
      ["Empirical Mean", fmtNum(data.empirical.mean)],
      ["Empirical SD", fmtNum(data.empirical.sd)],
      ["Skewness (X̄)", fmtNum(data.empirical.skewness)],
      ["Ex. Kurtosis", fmtNum(data.empirical.excess_kurtosis)],
      ["95% Coverage", `${(data.empirical.ci95_coverage * 100).toFixed(2)}%`],
      ["Trials N", data.trials.toLocaleString()],
    ]);
    qs("sim-extra").innerHTML = "";
    _lastExport = renderHistogramChart(
      qs("sim-svg"),
      data.histogram.edges,
      data.histogram.densities,
      [{ label: `Theoretical N(μ=${fmtNum(data.theoretical.pop_mean, "3")}, SE=${fmtNum(data.theoretical.se, "4")})`, x: data.normal_overlay.x, y: data.normal_overlay.y }],
      { title: qs("sim-chart-title").textContent, xlabel: "Sample Mean x̄", ylabel: "Density" }
    );
    appState.lastExportSpec = _lastExport;
    appState.snippetCtx = {
      workspace: "simulators",
      payload: {
        endpoint: "/api/v2/sim/clt",
        body,
        python: `import numpy as np\n# ${data.population_label}: SE = sigma / sqrt(${data.n}) = ${fmtNum(data.theoretical.se)}`,
        r: `# CLT simulation: n = ${data.n}, trials = ${data.trials}, SE = ${fmtNum(data.theoretical.se)}`,
        latex: `\\bar{X} \\approx \\mathcal{N}\\!\\left(\\mu = ${fmtNum(data.theoretical.pop_mean)},\\; \\frac{\\sigma^2}{${data.n}}\\right), \\quad \\mathrm{SE} = ${fmtNum(data.theoretical.se)}`,
      },
    };
    document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
  } catch (err) {
    if (err.name !== "AbortError") showSimError(err.message);
  }
}

async function runJoint(autoNormalize = false) {
  clearSimError();
  const body = {
    x_values: _jointState.xValues,
    y_values: _jointState.yValues,
    matrix: _jointState.matrix,
    auto_normalize: autoNormalize,
  };
  try {
    const data = await apiRequest("/api/v2/sim/joint", { method: "POST", body, channel: "sim" });
    if (autoNormalize) {
      _jointState.matrix = data.matrix.map((r) => r.map((v) => Number(v.toFixed(6))));
      renderJointEditor();
    }
    _lastData = data;
    appState.lastResult = data;
    qs("sim-chart-title").textContent = `Joint Distribution (X, Y) · ${data.independent ? "Independent" : "Dependent"}`;
    renderMetrics([
      ["E[X] / SD(X)", `${fmtNum(data.ex)} / ${fmtNum(data.sd_x)}`],
      ["E[Y] / SD(Y)", `${fmtNum(data.ey)} / ${fmtNum(data.sd_y)}`],
      ["Cov(X, Y)", fmtNum(data.cov)],
      ["Corr(X, Y)", data.corr !== null ? fmtNum(data.corr) : "Undefined"],
      ["Independent?", data.independent ? "Yes" : `No (Δ=${fmtNum(data.max_indep_diff)})`],
      ["I(X; Y) nats", fmtNum(data.mutual_information)],
      ["H(X, Y) nats", fmtNum(data.entropy_joint)],
      ["Σ p(x,y)", fmtNum(data.sum_p)],
    ]);

    // Conditional distribution table P(Y | X=x)
    const condRows = Object.entries(data.y_given_x)
      .map(([xv, dist]) => {
        const cells = data.y_values.map((yv) => `<td class="mono">${fmtNum(dist[String(yv)] ?? 0)}</td>`).join("");
        return `<tr><th class="mono">X = ${escHtml(xv)}</th>${cells}</tr>`;
      })
      .join("");
    qs("sim-extra").innerHTML = `<table class="data-table"><thead><tr><th>Conditional P(Y = y | X = x)</th>${data.y_values.map((y) => `<th class="mono">Y = ${y}</th>`).join("")}</tr></thead><tbody>${condRows}</tbody></table>`;

    _lastExport = renderJointHeatmapChart(qs("sim-svg"), data);
    appState.lastExportSpec = _lastExport;
    appState.snippetCtx = {
      workspace: "simulators",
      payload: {
        endpoint: "/api/v2/sim/joint",
        body,
        python: `import numpy as np\nP = np.array(${JSON.stringify(data.matrix)})\n# Cov = ${fmtNum(data.cov)}, Corr = ${fmtNum(data.corr)}, Independent = ${data.independent}`,
        r: `# Cov(X, Y) = ${fmtNum(data.cov)}, Corr(X, Y) = ${fmtNum(data.corr)}`,
        latex: `\\mathrm{Cov}(X,Y) = ${fmtNum(data.cov)}, \\quad \\rho_{XY} = ${fmtNum(data.corr)}`,
      },
    };
    document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
  } catch (err) {
    if (err.name !== "AbortError") showSimError(err.message);
  }
}

export function switchSimSub(sub) {
  appState.simSub = sub;
  syncUrlState();
  qs("sim-subtabs")
    .querySelectorAll(".seg-btn")
    .forEach((b) => b.classList.toggle("is-active", b.dataset.sim === sub));
  qs("sim-form-clt").classList.toggle("hidden", sub !== "clt");
  qs("sim-form-joint").classList.toggle("hidden", sub !== "joint");
  if (sub === "clt") runClt();
  else runJoint(false);
}

export function refreshSimTheme() {
  if (!_lastData) return;
  if (appState.simSub === "clt") {
    _lastExport = renderHistogramChart(
      qs("sim-svg"),
      _lastData.histogram.edges,
      _lastData.histogram.densities,
      [{ label: `Theoretical N(μ=${fmtNum(_lastData.theoretical.pop_mean, "3")}, SE=${fmtNum(_lastData.theoretical.se, "4")})`, x: _lastData.normal_overlay.x, y: _lastData.normal_overlay.y }],
      { title: qs("sim-chart-title").textContent, xlabel: "Sample Mean x̄", ylabel: "Density" }
    );
  } else {
    _lastExport = renderJointHeatmapChart(qs("sim-svg"), _lastData);
  }
  appState.lastExportSpec = _lastExport;
}

export function initSimulators() {
  qs("sim-subtabs")
    .querySelectorAll(".seg-btn")
    .forEach((btn) => btn.addEventListener("click", () => switchSimSub(btn.dataset.sim)));

  // CLT sliders
  const scheduleClt = () => {
    if (_cltTimer) clearTimeout(_cltTimer);
    _cltTimer = setTimeout(() => runClt(), 60);
  };
  qs("sim-clt-n-range").addEventListener("input", () => {
    qs("sim-clt-n").value = qs("sim-clt-n-range").value;
    scheduleClt();
  });
  qs("sim-clt-n").addEventListener("input", () => {
    qs("sim-clt-n-range").value = qs("sim-clt-n").value;
    scheduleClt();
  });
  qs("sim-clt-trials-range").addEventListener("input", () => {
    qs("sim-clt-trials").value = qs("sim-clt-trials-range").value;
    scheduleClt();
  });
  qs("sim-clt-trials").addEventListener("input", () => {
    qs("sim-clt-trials-range").value = qs("sim-clt-trials").value;
    scheduleClt();
  });
  qs("sim-clt-pop").addEventListener("change", () => runClt());
  qs("sim-form-clt").addEventListener("submit", (e) => {
    e.preventDefault();
    runClt();
  });

  // Joint matrix controls
  const jpBar = qs("joint-presets-bar");
  jpBar.replaceChildren();
  JOINT_PRESETS.forEach((pr) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "preset-pill";
    btn.textContent = pr.label;
    btn.addEventListener("click", () => {
      _jointState = {
        xValues: [...pr.xValues],
        yValues: [...pr.yValues],
        matrix: pr.matrix.map((r) => [...r]),
      };
      renderJointEditor();
      runJoint(false);
    });
    jpBar.appendChild(btn);
  });

  qs("btn-j-add-x").addEventListener("click", () => {
    if (_jointState.xValues.length >= 8) return;
    const nextX = Math.max(..._jointState.xValues) + 1;
    _jointState.xValues.push(nextX);
    _jointState.matrix.push(new Array(_jointState.yValues.length).fill(0));
    renderJointEditor();
  });
  qs("btn-j-add-y").addEventListener("click", () => {
    if (_jointState.yValues.length >= 8) return;
    const nextY = Math.max(..._jointState.yValues) + 1;
    _jointState.yValues.push(nextY);
    _jointState.matrix.forEach((r) => r.push(0));
    renderJointEditor();
  });
  qs("btn-j-normalize").addEventListener("click", () => runJoint(true));
  qs("btn-j-analyze").addEventListener("click", () => runJoint(false));
  renderJointEditor();

  // Exports
  qs("sim-export-svg").addEventListener("click", () => downloadSvgElement(qs("sim-svg"), `p05-${appState.simSub}.svg`));
  qs("sim-export-png").addEventListener("click", () => downloadBackendPng(_lastExport, `p05-${appState.simSub}.png`));
  qs("sim-export-json").addEventListener("click", () => downloadJson(_lastData, `p05-${appState.simSub}.json`));

  switchSimSub(appState.simSub);
}
