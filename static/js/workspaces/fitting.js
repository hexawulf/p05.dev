/* Workspace 3: Empirical Data, Histogram + KDE, MLE Auto-Fit & Q-Q Diagnostics */

import { apiRequest, downloadBackendPng, downloadJson } from "../api.js";
import { downloadSvgElement, renderHistogramChart, renderQQChart } from "../chart.js";
import { SAMPLE_DATASETS } from "../presets.js";
import { appState, escHtml, fmtNum } from "../state.js";

let _lastData = null;
let _selectedFitIdx = 0;
let _lastHistExport = null;

function qs(id) {
  return document.getElementById(id);
}

function renderDescriptives(d) {
  const cells = [
    ["n", String(d.n)],
    ["Mean (95% CI)", `${fmtNum(d.mean)} [${fmtNum(d.mean_ci_95[0], "2")}, ${fmtNum(d.mean_ci_95[1], "2")}]`],
    ["Trimmed (10%)", fmtNum(d.trimmed_mean_10)],
    ["Median", fmtNum(d.median)],
    ["Sample SD (s)", fmtNum(d.std_sample)],
    ["IQR (Q₃ − Q₁)", fmtNum(d.iqr)],
    ["Min / Max", `${fmtNum(d.min, "3")} / ${fmtNum(d.max, "3")}`],
    ["Skew / Kurt", `${fmtNum(d.skewness, "3")} / ${fmtNum(d.excess_kurtosis, "3")}`],
  ];
  qs("fit-descriptives").innerHTML = cells
    .map(([k, v]) => `<div class="metric-cell"><div class="metric-k">${escHtml(k)}</div><div class="metric-v mono">${escHtml(v)}</div></div>`)
    .join("");

  const outBanner = qs("fit-outliers-banner");
  if (d.outliers_iqr.count > 0) {
    outBanner.classList.remove("hidden");
    outBanner.textContent = `1.5×IQR Outliers (${d.outliers_iqr.count}): ${d.outliers_iqr.values.slice(0, 8).map((v) => fmtNum(v, "3")).join(", ")} (fences [${fmtNum(d.outliers_iqr.lower_fence, "2")}, ${fmtNum(d.outliers_iqr.upper_fence, "2")}])`;
  } else {
    outBanner.classList.add("hidden");
  }
}

function renderSelectedFitPlots() {
  if (!_lastData) return;
  const d = _lastData;
  const selected = d.fits[_selectedFitIdx] || d.fits[0];
  const curves = [{ label: "Gaussian KDE", x: d.x_grid, y: d.kde_y }];
  if (selected) {
    curves.push({ label: `${selected.name} MLE (${selected.param_summary})`, x: d.x_grid, y: selected.pdf_y });
    renderQQChart(qs("fit-qq-svg"), selected.qq.theoretical, selected.qq.sample, selected.name);
  }
  _lastHistExport = renderHistogramChart(qs("fit-hist-svg"), d.histogram.edges, d.histogram.densities, curves, {
    title: `Empirical Histogram (${d.histogram.bin_count} bins) + KDE${selected ? ` + ${selected.name} MLE` : ""}`,
    xlabel: "Observed Value",
    ylabel: "Density",
  });
  appState.lastExportSpec = _lastHistExport;
}

function renderRankingTable(fits, skipped) {
  const wrap = qs("fit-ranking-table");
  if (!fits.length) {
    wrap.innerHTML = `<div class="chart-hint">No candidate MLE fits converged.</div>`;
    return;
  }
  const rows = fits
    .map(
      (f, idx) =>
        `<tr class="row-selectable ${idx === _selectedFitIdx ? "row-selected" : ""}" data-idx="${idx}">
          <td class="mono">${f.rank}</td>
          <td><strong>${escHtml(f.name)}</strong><div class="chart-hint mono">${escHtml(f.param_summary)}</div></td>
          <td class="mono">${fmtNum(f.aic, "2")}</td>
          <td class="mono">${fmtNum(f.ks_stat, "4")}</td>
          <td class="mono">${fmtNum(f.ks_pvalue, "4")}</td>
        </tr>`
    )
    .join("");
  wrap.innerHTML = `<table class="data-table"><thead><tr><th>#</th><th>Model (MLE)</th><th>AIC</th><th>KS D</th><th>KS p</th></tr></thead><tbody>${rows}</tbody></table>`;
  wrap.querySelectorAll("tr.row-selectable").forEach((tr) => {
    tr.addEventListener("click", () => {
      _selectedFitIdx = Number(tr.dataset.idx);
      renderRankingTable(fits, skipped);
      renderSelectedFitPlots();
    });
  });

  qs("fit-skipped-note").textContent = skipped.length
    ? `Skipped: ${skipped.map((s) => `${s.name} (${s.reason})`).join("; ")}`
    : "";
}

export async function runAnalyze() {
  const errBox = qs("fit-error");
  errBox.classList.add("hidden");
  const body = {
    raw_text: qs("fit-raw-input").value,
    bin_rule: qs("fit-bin-rule").value,
    bins: Number(qs("fit-manual-bins").value) || 20,
  };
  try {
    const data = await apiRequest("/api/v2/fit/analyze", { method: "POST", body, channel: "fit" });
    _lastData = data;
    _selectedFitIdx = 0;
    appState.lastResult = data;
    renderDescriptives(data.descriptives);
    renderRankingTable(data.fits, data.skipped_models);
    renderSelectedFitPlots();
    appState.snippetCtx = {
      workspace: "fitting",
      payload: {
        endpoint: "/api/v2/fit/analyze",
        body,
        python: `import numpy as np\nfrom scipy import stats\nx = np.array([${data.n} values])\n# Best AIC fit: ${data.fits[0]?.name || "Normal"} (${data.fits[0]?.param_summary || ""})`,
        r: `# n = ${data.n}, mean = ${fmtNum(data.descriptives.mean)}, sd = ${fmtNum(data.descriptives.std_sample)}`,
        latex: `\\bar{x} = ${fmtNum(data.descriptives.mean)}, \\quad s = ${fmtNum(data.descriptives.std_sample)}, \\quad n = ${data.n}`,
      },
    };
    document.dispatchEvent(new CustomEvent("p05:snippet-updated"));
  } catch (err) {
    if (err.name === "AbortError") return;
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  }
}

export function refreshFittingTheme() {
  if (_lastData) renderSelectedFitPlots();
}

export function initFitting() {
  const sBar = qs("fit-samples-bar");
  sBar.replaceChildren();
  SAMPLE_DATASETS.forEach((ds) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "preset-pill";
    btn.textContent = ds.label;
    btn.addEventListener("click", () => {
      qs("fit-raw-input").value = ds.data;
      qs("fit-bin-rule").value = ds.binRule;
      qs("fit-manual-bins-wrap").classList.toggle("hidden", ds.binRule !== "manual");
      runAnalyze();
    });
    sBar.appendChild(btn);
  });

  qs("fit-raw-input").value = SAMPLE_DATASETS[0].data;
  const syncBinInput = () => {
    qs("fit-manual-bins-wrap").classList.toggle("hidden", qs("fit-bin-rule").value !== "manual");
  };
  qs("fit-bin-rule").addEventListener("change", () => {
    syncBinInput();
    runAnalyze();
  });
  syncBinInput();

  qs("fit-form").addEventListener("submit", (e) => {
    e.preventDefault();
    runAnalyze();
  });

  qs("fit-export-svg").addEventListener("click", () => downloadSvgElement(qs("fit-hist-svg"), "p05-fit-histogram.svg"));
  qs("fit-export-png").addEventListener("click", () => downloadBackendPng(_lastHistExport, "p05-fit-histogram.png"));
  qs("fit-export-json").addEventListener("click", () => downloadJson(_lastData, "p05-fit-analysis.json"));

  runAnalyze();
}
