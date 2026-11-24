/* probplots-web — client controller (zero external dependencies) */
(function () {
  "use strict";

  const qs = (id) => document.getElementById(id);
  const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    precision: "4",
    activeTab: "normal",
    lastPlot: {}, // tab -> { baseUrl, imgId, phId, dlId, labelId, label }
    lastNormShade: { shade_low: null, shade_high: null },
    lastBinomHL: { highlight_k: 10, highlight_min: null, highlight_max: null },
    lastPoisHL: { highlight_k: 2, highlight_min: null, highlight_max: null },
  };

  // ---- Theme handling ----
  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function updateThemeIcons(theme) {
    qs("icon-sun").classList.toggle("hidden", theme !== "dark");
    qs("icon-moon").classList.toggle("hidden", theme === "dark");
    qs("btn-theme").setAttribute(
      "aria-label",
      theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
    );
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("probplots-theme", theme);
    } catch {
      // ignore storage errors
    }
    updateThemeIcons(theme);
    // Refresh any already-visible plots in the new theme
    Object.values(state.lastPlot).forEach((entry) => {
      if (entry && entry.baseUrl) {
        loadPlot(entry.tab, entry.baseUrl, entry.imgId, entry.phId, entry.dlId, entry.labelId, entry.label);
      }
    });
  }

  updateThemeIcons(currentTheme());
  qs("btn-theme").addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });

  // ---- Precision selector ----
  try {
    const savedPrec = localStorage.getItem("probplots-precision");
    if (savedPrec && ["2", "4", "6", "full"].includes(savedPrec)) {
      state.precision = savedPrec;
      qs("precision-select").value = savedPrec;
    }
  } catch {
    // ignore
  }
  qs("precision-select").addEventListener("change", (e) => {
    state.precision = e.target.value;
    try {
      localStorage.setItem("probplots-precision", state.precision);
    } catch {
      // ignore
    }
  });

  function fmt(num, overrideDigits) {
    if (num === null || num === undefined || Number.isNaN(Number(num))) return "—";
    const n = Number(num);
    if (!Number.isFinite(n)) return String(n);
    if (Math.abs(n) < 1e-12) return "0";
    const prec = overrideDigits !== undefined ? overrideDigits : state.precision;
    if (prec === "full") return String(n);
    const d = Number(prec);
    if (Math.abs(n) > 0 && Math.abs(n) < Math.pow(10, -d)) {
      return n.toExponential(Math.max(2, d - 1));
    }
    return n.toFixed(d);
  }

  function fmtPct(prob) {
    if (!Number.isFinite(prob)) return "";
    return `${(prob * 100).toFixed(2)}%`;
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ---- Network helpers ----
  async function jfetch(url) {
    const res = await fetch(url);
    const text = await res.text();
    let parsed = null;
    try {
      parsed = JSON.parse(text);
    } catch {
      // plain text fallback
    }
    if (!res.ok) {
      const msg =
        (parsed && (typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail))) ||
        text ||
        `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return parsed;
  }

  function showError(containerId, err) {
    const el = qs(containerId);
    el.innerHTML = `<div class="error-banner" role="alert"><strong>Error:</strong> ${escHtml(err.message || String(err))}</div>`;
  }

  function renderResult(containerId, { expr, value, isProb = true, extras = [], casio = "", rawObj = null }) {
    const el = qs(containerId);
    const formatted = fmt(value);
    const pct = isProb && Number.isFinite(Number(value)) ? `<span><strong>${fmtPct(Number(value))}</strong></span>` : "";
    const extraHtml = extras
      .map(([k, v]) => `<span>${escHtml(k)}: <strong>${escHtml(v)}</strong></span>`)
      .join("");
    const casioHtml = casio ? `<div class="casio-tip"><strong>FX-991EX:</strong> ${escHtml(casio)}</div>` : "";
    const rawHtml = rawObj
      ? `<details class="raw-details"><summary>Raw API JSON</summary><pre class="code-out" tabindex="0">${escHtml(JSON.stringify(rawObj, null, 2))}</pre></details>`
      : "";

    el.innerHTML = `
      <div class="result-header">
        <div>
          <div class="result-expr">${escHtml(expr)}</div>
          <div class="result-value">${escHtml(formatted)}</div>
        </div>
        <button type="button" class="btn btn-ghost btn-sm copy-btn" data-copy="${escHtml(String(value))}">Copy</button>
      </div>
      <div class="result-meta">${pct}${extraHtml}</div>
      ${casioHtml}
      ${rawHtml}
    `;

    const copyBtn = el.querySelector(".copy-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(formatted);
          copyBtn.textContent = "Copied";
          setTimeout(() => {
            copyBtn.textContent = "Copy";
          }, 1200);
        } catch {
          copyBtn.textContent = "Copy failed";
        }
      });
    }
  }

  function loadPlot(tab, baseUrl, imgId, phId, dlId, labelId, label) {
    state.lastPlot[tab] = { tab, baseUrl, imgId, phId, dlId, labelId, label };
    const sep = baseUrl.includes("?") ? "&" : "?";
    const themedUrl = `${baseUrl}${sep}theme=${currentTheme()}&_=${Date.now()}`;
    const img = qs(imgId);
    const ph = qs(phId);
    const dl = qs(dlId);
    if (labelId && label) qs(labelId).textContent = label;

    ph.textContent = "Rendering PNG…";
    ph.classList.remove("hidden");
    img.classList.add("hidden");

    img.onload = () => {
      ph.classList.add("hidden");
      img.classList.remove("hidden");
      if (dl) {
        dl.href = themedUrl;
        dl.classList.remove("hidden");
      }
    };
    img.onerror = async () => {
      let detail = "Unable to render plot. Check parameter bounds.";
      try {
        const res = await fetch(themedUrl);
        const body = await res.json();
        if (body && body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        // fallback message
      }
      ph.textContent = `Plot error: ${detail}`;
      ph.classList.remove("hidden");
      img.classList.add("hidden");
      if (dl) dl.classList.add("hidden");
    };
    img.src = themedUrl;
  }

  // ---- Tabs ----
  const TAB_NAMES = ["normal", "binomial", "poisson", "other", "clt", "joint"];

  function activateTab(tab, updateHash = true) {
    if (!TAB_NAMES.includes(tab)) tab = "normal";
    state.activeTab = tab;
    qsa(".tab-btn").forEach((btn) => {
      btn.setAttribute("aria-selected", btn.dataset.tab === tab ? "true" : "false");
    });
    TAB_NAMES.forEach((name) => {
      qs(`panel-${name}`).classList.toggle("hidden", name !== tab);
    });
    if (updateHash && window.location.hash !== `#${tab}`) {
      history.replaceState(null, "", `#${tab}`);
    }
  }

  qsa(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  if (window.location.hash) {
    activateTab(window.location.hash.slice(1), false);
  }

  // ---- About modal ----
  const aboutModal = qs("about-modal");
  let lastFocused = null;

  function openAbout() {
    lastFocused = document.activeElement;
    aboutModal.classList.remove("hidden");
    qs("about-close").focus();
  }

  function closeAbout() {
    if (aboutModal.classList.contains("hidden")) return;
    aboutModal.classList.add("hidden");
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
  }

  qs("btn-about").addEventListener("click", openAbout);
  qs("about-close").addEventListener("click", closeAbout);
  qs("about-ok").addEventListener("click", closeAbout);
  aboutModal.addEventListener("click", (e) => {
    if (e.target === aboutModal) closeAbout();
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAbout();
  });

  // ---- NORMAL ----
  function updateNormMeta() {
    const mu = Number(qs("norm-mu").value);
    const sigma = Number(qs("norm-sigma").value);
    qs("norm-badge").textContent = `X ~ N(${mu}, ${sigma}²)`;
    qs("f-ncdf").elements.mu.value = qs("norm-mu").value;
    qs("f-ncdf").elements.sigma.value = qs("norm-sigma").value;
    if (Number.isFinite(mu) && Number.isFinite(sigma) && sigma > 0) {
      qs("norm-moments").innerHTML = `<span>E[X] = <strong>${fmt(mu, 4)}</strong></span><span>Var(X) = <strong>${fmt(sigma * sigma, 4)}</strong></span><span>68% ≈ <strong>[${fmt(mu - sigma, 2)}, ${fmt(mu + sigma, 2)}]</strong></span>`;
    } else {
      qs("norm-moments").innerHTML = `<span>Enter σ &gt; 0 for distribution moments.</span>`;
    }
  }
  qs("norm-mu").addEventListener("input", updateNormMeta);
  qs("norm-sigma").addEventListener("input", updateNormMeta);
  updateNormMeta();

  qs("f-ncdf").addEventListener("submit", async (e) => {
    e.preventDefault();
    const x = Number(e.target.elements.x.value);
    const mu = Number(qs("norm-mu").value);
    const sigma = Number(qs("norm-sigma").value);
    const q = new URLSearchParams({ x, mu, sigma }).toString();
    try {
      const [cdf, pdf] = await Promise.all([jfetch(`/api/norm/cdf?${q}`), jfetch(`/api/norm/pdf?${q}`)]);
      const z = (x - mu) / sigma;
      state.lastNormShade = { shade_low: null, shade_high: x };
      renderResult("r-norm", {
        expr: `P(X ≤ ${x}) for N(${mu}, ${sigma}²)`,
        value: cdf.value,
        isProb: true,
        extras: [
          ["Upper tail P(X ≥ x)", fmt(1 - cdf.value)],
          ["Density f(x)", fmt(pdf.value)],
          ["Z-score", fmt(z)],
        ],
        casio: `MENU → 7 → 2:Normal CD · Lower=-1E99, Upper=${x}, σ=${sigma}, μ=${mu}`,
        rawObj: { cdf: cdf.value, upper_tail: 1 - cdf.value, pdf: pdf.value, z },
      });
    } catch (err) {
      showError("r-norm", err);
    }
  });

  qs("f-nint").addEventListener("submit", async (e) => {
    e.preventDefault();
    const lower = Number(e.target.elements.lower.value);
    const upper = Number(e.target.elements.upper.value);
    const mu = Number(qs("norm-mu").value);
    const sigma = Number(qs("norm-sigma").value);
    const q = new URLSearchParams({ lower, upper, mu, sigma }).toString();
    try {
      const out = await jfetch(`/api/norm/interval?${q}`);
      state.lastNormShade = { shade_low: lower, shade_high: upper };
      renderResult("r-norm", {
        expr: `P(${Math.min(lower, upper)} ≤ X ≤ ${Math.max(lower, upper)}) for N(${mu}, ${sigma}²)`,
        value: out.value,
        isProb: true,
        extras: [
          ["z₁", fmt((lower - mu) / sigma)],
          ["z₂", fmt((upper - mu) / sigma)],
        ],
        casio: `MENU → 7 → 2:Normal CD · Lower=${lower}, Upper=${upper}, σ=${sigma}, μ=${mu}`,
        rawObj: out,
      });
    } catch (err) {
      showError("r-norm", err);
    }
  });

  qs("f-ninv").addEventListener("submit", async (e) => {
    e.preventDefault();
    const p = Number(e.target.elements.p.value);
    const mu = Number(qs("norm-mu").value);
    const sigma = Number(qs("norm-sigma").value);
    const q = new URLSearchParams({ p, mu, sigma }).toString();
    try {
      const out = await jfetch(`/api/norm/inv?${q}`);
      state.lastNormShade = { shade_low: null, shade_high: out.value };
      renderResult("r-norm", {
        expr: `Inverse Normal Φ⁻¹(${p}) for N(${mu}, ${sigma}²)`,
        value: out.value,
        isProb: false,
        extras: [["Z-quantile", fmt((out.value - mu) / sigma)]],
        casio: `MENU → 7 → 3:Inverse Normal · Area=${p}, σ=${sigma}, μ=${mu}`,
        rawObj: out,
      });
    } catch (err) {
      showError("r-norm", err);
    }
  });

  qs("btn-npdf").addEventListener("click", () => {
    const mu = qs("norm-mu").value;
    const sigma = qs("norm-sigma").value;
    const params = new URLSearchParams({ mu, sigma });
    if (state.lastNormShade.shade_low !== null) params.set("shade_low", state.lastNormShade.shade_low);
    if (state.lastNormShade.shade_high !== null) params.set("shade_high", state.lastNormShade.shade_high);
    loadPlot("normal", `/plot/png/normal?${params.toString()}`, "img-npdf", "ph-norm", "dl-norm", "plot-label-norm", `Shaded Normal PDF N(${mu}, ${sigma}²)`);
  });

  qs("btn-npdf-plain").addEventListener("click", () => {
    const mu = qs("norm-mu").value;
    const sigma = qs("norm-sigma").value;
    const params = new URLSearchParams({ mu, sigma });
    loadPlot("normal", `/plot/png/normal?${params.toString()}`, "img-npdf", "ph-norm", "dl-norm", "plot-label-norm", `Normal PDF N(${mu}, ${sigma}²)`);
  });

  // ---- BINOMIAL ----
  function updateBinomMeta() {
    const n = Number(qs("binom-n").value);
    const p = Number(qs("binom-p").value);
    qs("binom-badge").textContent = `X ~ Bin(${n}, ${p})`;
    if (Number.isInteger(n) && n >= 1 && Number.isFinite(p) && p >= 0 && p <= 1) {
      const mean = n * p;
      const variance = n * p * (1 - p);
      qs("binom-moments").innerHTML = `<span>E[X] = <strong>${fmt(mean, 4)}</strong></span><span>Var(X) = <strong>${fmt(variance, 4)}</strong></span><span>σ = <strong>${fmt(Math.sqrt(variance), 4)}</strong></span>`;
    } else {
      qs("binom-moments").innerHTML = `<span>Enter n ≥ 1 and 0 ≤ p ≤ 1.</span>`;
    }
  }
  qs("binom-n").addEventListener("input", updateBinomMeta);
  qs("binom-p").addEventListener("input", updateBinomMeta);
  updateBinomMeta();

  async function runBinomSingle(mode) {
    const n = qs("binom-n").value;
    const p = qs("binom-p").value;
    const k = qs("binom-k").value;
    const q = new URLSearchParams({ n, p, k }).toString();
    const map = {
      pmf: { url: `/api/binom/pmf?${q}`, expr: `P(X = ${k}) for Bin(${n}, ${p})`, casio: `MENU → 7 → 1:Binomial PD · x=${k}, N=${n}, p=${p}` },
      atmost: { url: `/api/binom/atmost?${q}`, expr: `P(X ≤ ${k}) for Bin(${n}, ${p})`, casio: `MENU → 7 → 3:Binomial CD · x=${k}, N=${n}, p=${p}` },
      atleast: { url: `/api/binom/atleast?${q}`, expr: `P(X ≥ ${k}) for Bin(${n}, ${p})`, casio: `1 − Binomial CD(x=${Math.max(0, Number(k) - 1)}, N=${n}, p=${p})` },
    };
    const cfg = map[mode];
    try {
      const out = await jfetch(cfg.url);
      if (mode === "pmf") {
        state.lastBinomHL = { highlight_k: Number(k), highlight_min: null, highlight_max: null };
      } else if (mode === "atmost") {
        state.lastBinomHL = { highlight_k: null, highlight_min: 0, highlight_max: Number(k) };
      } else {
        state.lastBinomHL = { highlight_k: null, highlight_min: Number(k), highlight_max: Number(n) };
      }
      renderResult("r-binom", { expr: cfg.expr, value: out.value, isProb: true, casio: cfg.casio, rawObj: out });
    } catch (err) {
      showError("r-binom", err);
    }
  }

  qs("f-bpmf").addEventListener("submit", (e) => {
    e.preventDefault();
    runBinomSingle("pmf");
  });
  qs("btn-binom-atmost").addEventListener("click", () => runBinomSingle("atmost"));
  qs("btn-binom-atleast").addEventListener("click", () => runBinomSingle("atleast"));

  qs("f-bcdf-range").addEventListener("submit", async (e) => {
    e.preventDefault();
    const n = qs("binom-n").value;
    const p = qs("binom-p").value;
    const kmin = qs("binom-kmin").value;
    const kmax = qs("binom-kmax").value;
    const q = new URLSearchParams({ n, p, kmin, kmax }).toString();
    try {
      const out = await jfetch(`/api/binom/between?${q}`);
      state.lastBinomHL = { highlight_k: null, highlight_min: Number(kmin), highlight_max: Number(kmax) };
      renderResult("r-binom", {
        expr: `P(${kmin} ≤ X ≤ ${kmax}) for Bin(${n}, ${p})`,
        value: out.value,
        isProb: true,
        casio: `Binomial CD(x=${kmax}) − Binomial CD(x=${Math.max(0, Number(kmin) - 1)})`,
        rawObj: out,
      });
    } catch (err) {
      showError("r-binom", err);
    }
  });

  qs("btn-binom-pmf-plot").addEventListener("click", () => {
    const n = qs("binom-n").value;
    const p = qs("binom-p").value;
    const params = new URLSearchParams({ n, p });
    if (state.lastBinomHL.highlight_k !== null) params.set("highlight_k", state.lastBinomHL.highlight_k);
    if (state.lastBinomHL.highlight_min !== null) {
      params.set("highlight_min", state.lastBinomHL.highlight_min);
      params.set("highlight_max", state.lastBinomHL.highlight_max);
    }
    loadPlot("binomial", `/plot/png/binomial_pmf?${params.toString()}`, "img-binom-plot", "ph-binom", "dl-binom", "plot-label-binom", `Binomial PMF (n=${n}, p=${p})`);
  });

  qs("btn-binom-cdf-plot").addEventListener("click", () => {
    const n = qs("binom-n").value;
    const p = qs("binom-p").value;
    const k = qs("binom-k").value;
    const params = new URLSearchParams({ n, p, highlight_k: k });
    loadPlot("binomial", `/plot/png/binomial_cdf?${params.toString()}`, "img-binom-plot", "ph-binom", "dl-binom", "plot-label-binom", `Binomial CDF (n=${n}, p=${p})`);
  });

  qs("btn-binom-sim").addEventListener("click", () => {
    const N = qs("binom-n").value;
    const p = qs("binom-p").value;
    const params = new URLSearchParams({ n: 50000, N, p, bins: 50 });
    loadPlot("binomial", `/plot/png/binomial_sim?${params.toString()}`, "img-binom-plot", "ph-binom", "dl-binom", "plot-label-binom", `Binomial Simulation (n=50,000, N=${N}, p=${p})`);
  });

  // ---- POISSON ----
  function updatePoisMeta() {
    const lam = Number(qs("pois-lam").value);
    qs("pois-badge").textContent = `X ~ Pois(λ = ${lam})`;
    if (Number.isFinite(lam) && lam > 0) {
      qs("pois-moments").innerHTML = `<span>E[X] = <strong>${fmt(lam, 4)}</strong></span><span>Var(X) = <strong>${fmt(lam, 4)}</strong></span><span>σ = <strong>${fmt(Math.sqrt(lam), 4)}</strong></span>`;
    } else {
      qs("pois-moments").innerHTML = `<span>Enter λ &gt; 0.</span>`;
    }
  }
  qs("pois-lam").addEventListener("input", updatePoisMeta);
  updatePoisMeta();

  async function runPois(mode) {
    const lam = qs("pois-lam").value;
    const k = qs("pois-k").value;
    const q = new URLSearchParams({ lam, k }).toString();
    const map = {
      pmf: { url: `/api/pois/pmf?${q}`, expr: `P(X = ${k}) for Pois(λ=${lam})`, casio: `MENU → 7 → 2:Poisson PD · x=${k}, λ=${lam}` },
      cdf: { url: `/api/pois/cdf?${q}`, expr: `P(X ≤ ${k}) for Pois(λ=${lam})`, casio: `MENU → 7 → 3:Poisson CD · x=${k}, λ=${lam}` },
      atleast: { url: `/api/pois/atleast?${q}`, expr: `P(X ≥ ${k}) for Pois(λ=${lam})`, casio: `1 − Poisson CD(x=${Math.max(0, Number(k) - 1)}, λ=${lam})` },
    };
    const cfg = map[mode];
    try {
      const out = await jfetch(cfg.url);
      if (mode === "pmf") {
        state.lastPoisHL = { highlight_k: Number(k), highlight_min: null, highlight_max: null };
      } else if (mode === "cdf") {
        state.lastPoisHL = { highlight_k: null, highlight_min: 0, highlight_max: Number(k) };
      } else {
        state.lastPoisHL = { highlight_k: null, highlight_min: Number(k), highlight_max: Math.max(20, Math.ceil(Number(lam) + 5 * Math.sqrt(Math.max(1, Number(lam))))) };
      }
      renderResult("r-pois", { expr: cfg.expr, value: out.value, isProb: true, casio: cfg.casio, rawObj: out });
    } catch (err) {
      showError("r-pois", err);
    }
  }

  qs("btn-pois-pmf").addEventListener("click", () => runPois("pmf"));
  qs("btn-pois-cdf").addEventListener("click", () => runPois("cdf"));
  qs("btn-pois-atleast").addEventListener("click", () => runPois("atleast"));

  qs("f-prange").addEventListener("submit", async (e) => {
    e.preventDefault();
    const lam = qs("pois-lam").value;
    const kmin = qs("pois-kmin").value;
    const kmax = qs("pois-kmax").value;
    const q = new URLSearchParams({ lam, kmin, kmax }).toString();
    try {
      const out = await jfetch(`/api/pois/between?${q}`);
      state.lastPoisHL = { highlight_k: null, highlight_min: Number(kmin), highlight_max: Number(kmax) };
      renderResult("r-pois", {
        expr: `P(${kmin} ≤ X ≤ ${kmax}) for Pois(λ=${lam})`,
        value: out.value,
        isProb: true,
        casio: `Poisson CD(x=${kmax}) − Poisson CD(x=${Math.max(0, Number(kmin) - 1)})`,
        rawObj: out,
      });
    } catch (err) {
      showError("r-pois", err);
    }
  });

  qs("btn-pois-pmf-exact").addEventListener("click", () => {
    const lam = qs("pois-lam").value;
    const params = new URLSearchParams({ lam });
    if (state.lastPoisHL.highlight_k !== null) params.set("highlight_k", state.lastPoisHL.highlight_k);
    if (state.lastPoisHL.highlight_min !== null) {
      params.set("highlight_min", state.lastPoisHL.highlight_min);
      params.set("highlight_max", state.lastPoisHL.highlight_max);
    }
    loadPlot("poisson", `/plot/png/poisson_pmf?${params.toString()}`, "img-pois", "ph-pois", "dl-pois", "plot-label-pois", `Poisson Exact PMF (λ=${lam})`);
  });

  qs("btn-pois-cdf-plot").addEventListener("click", () => {
    const lam = qs("pois-lam").value;
    const k = qs("pois-k").value;
    const params = new URLSearchParams({ lam, highlight_k: k });
    loadPlot("poisson", `/plot/png/poisson_cdf?${params.toString()}`, "img-pois", "ph-pois", "dl-pois", "plot-label-pois", `Poisson Exact CDF (λ=${lam})`);
  });

  qs("btn-pois-sim").addEventListener("click", () => {
    const lam = qs("pois-lam").value;
    const params = new URLSearchParams({ n: 50000, lam, bins: 50 });
    loadPlot("poisson", `/plot/png/poisson_sim?${params.toString()}`, "img-pois", "ph-pois", "dl-pois", "plot-label-pois", `Poisson Simulation (n=50,000, λ=${lam})`);
  });

  // ---- OTHER: GEOMETRIC / EXPONENTIAL / UNIFORM ----
  qs("f-geom").addEventListener("submit", async (e) => {
    e.preventDefault();
    const p = Number(e.target.elements.p.value);
    const k = Number(e.target.elements.k.value);
    const q = new URLSearchParams({ p, k }).toString();
    try {
      const [pmf, cdf] = await Promise.all([jfetch(`/api/geom/pmf?${q}`), jfetch(`/api/geom/cdf?${q}`)]);
      renderResult("r-other", {
        expr: `Geometric PMF P(X = ${k}) · p=${p} (failures before 1st success)`,
        value: pmf.value,
        isProb: true,
        extras: [
          [`CDF P(X ≤ ${k})`, fmt(cdf.value)],
          ["E[X] = (1−p)/p", fmt((1 - p) / p)],
          ["Var(X)", fmt((1 - p) / (p * p))],
        ],
        casio: `(1 − ${p})^${k} × ${p}`,
        rawObj: { pmf: pmf.value, cdf: cdf.value },
      });
    } catch (err) {
      showError("r-other", err);
    }
  });

  qs("btn-geom-plot").addEventListener("click", () => {
    const f = qs("f-geom");
    const p = f.elements.p.value;
    const k = f.elements.k.value;
    const kmax = Math.max(15, Number(k) + 8);
    const params = new URLSearchParams({ p, kmax, highlight_k: k });
    loadPlot("other", `/plot/png/geometric_pmf?${params.toString()}`, "img-other", "ph-other", "dl-other", "plot-label-other", `Geometric PMF (p=${p}, 0-indexed failures)`);
  });

  qs("f-exp").addEventListener("submit", async (e) => {
    e.preventDefault();
    const lam = Number(e.target.elements.lam.value);
    const x = Number(e.target.elements.x.value);
    const q = new URLSearchParams({ lam, x }).toString();
    try {
      const [cdf, pdf] = await Promise.all([jfetch(`/api/exp/cdf?${q}`), jfetch(`/api/exp/pdf?${q}`)]);
      renderResult("r-other", {
        expr: `Exponential CDF P(X ≤ ${x}) · λ=${lam}`,
        value: cdf.value,
        isProb: true,
        extras: [
          [`Survival P(X > ${x})`, fmt(1 - cdf.value)],
          ["Density f(x)", fmt(pdf.value)],
          ["E[X] = 1/λ", fmt(1 / lam)],
        ],
        casio: `1 − e^(−${lam} × ${x})`,
        rawObj: { cdf: cdf.value, survival: 1 - cdf.value, pdf: pdf.value },
      });
    } catch (err) {
      showError("r-other", err);
    }
  });

  qs("btn-exp-pdf-plot").addEventListener("click", () => {
    const f = qs("f-exp");
    const params = new URLSearchParams({ lam: f.elements.lam.value, highlight_x: f.elements.x.value });
    loadPlot("other", `/plot/png/exponential_pdf?${params.toString()}`, "img-other", "ph-other", "dl-other", "plot-label-other", `Exponential PDF (λ=${f.elements.lam.value})`);
  });

  qs("btn-exp-cdf-plot").addEventListener("click", () => {
    const f = qs("f-exp");
    const params = new URLSearchParams({ lam: f.elements.lam.value, highlight_x: f.elements.x.value });
    loadPlot("other", `/plot/png/exponential_cdf?${params.toString()}`, "img-other", "ph-other", "dl-other", "plot-label-other", `Exponential CDF (λ=${f.elements.lam.value})`);
  });

  qs("f-unif").addEventListener("submit", async (e) => {
    e.preventDefault();
    const a = Number(e.target.elements.a.value);
    const b = Number(e.target.elements.b.value);
    const x = Number(e.target.elements.x.value);
    const q = new URLSearchParams({ a, b, x }).toString();
    try {
      const [cdf, pdf] = await Promise.all([jfetch(`/api/unif/cdf?${q}`), jfetch(`/api/unif/pdf?${q}`)]);
      renderResult("r-other", {
        expr: `Uniform CDF P(X ≤ ${x}) on [${a}, ${b}]`,
        value: cdf.value,
        isProb: true,
        extras: [
          ["Density f(x)", fmt(pdf.value)],
          ["E[X]", fmt((a + b) / 2)],
          ["Var(X)", fmt(((b - a) * (b - a)) / 12)],
        ],
        casio: `(${x} − ${a}) / (${b} − ${a})`,
        rawObj: { cdf: cdf.value, pdf: pdf.value },
      });
    } catch (err) {
      showError("r-other", err);
    }
  });

  qs("btn-unif-pdf-plot").addEventListener("click", () => {
    const f = qs("f-unif");
    const params = new URLSearchParams({ a: f.elements.a.value, b: f.elements.b.value, highlight_x: f.elements.x.value });
    loadPlot("other", `/plot/png/uniform_pdf?${params.toString()}`, "img-other", "ph-other", "dl-other", "plot-label-other", `Uniform PDF [${f.elements.a.value}, ${f.elements.b.value}]`);
  });

  qs("btn-unif-cdf-plot").addEventListener("click", () => {
    const f = qs("f-unif");
    const params = new URLSearchParams({ a: f.elements.a.value, b: f.elements.b.value, highlight_x: f.elements.x.value });
    loadPlot("other", `/plot/png/uniform_cdf?${params.toString()}`, "img-other", "ph-other", "dl-other", "plot-label-other", `Uniform CDF [${f.elements.a.value}, ${f.elements.b.value}]`);
  });

  // ---- CLT & BOUNDS ----
  qs("f-clt").addEventListener("submit", async (e) => {
    e.preventDefault();
    const mu = Number(e.target.elements.mu.value);
    const sigma = Number(e.target.elements.sigma.value);
    const n = Number(e.target.elements.n.value);
    const lower = Number(e.target.elements.lower.value);
    const upper = Number(e.target.elements.upper.value);
    const q = new URLSearchParams({ mu, sigma, n, lower, upper }).toString();
    try {
      const out = await jfetch(`/api/clt?${q}`);
      const se = sigma / Math.sqrt(n);
      renderResult("r-clt", {
        expr: `P(${Math.min(lower, upper)} ≤ X̄ ≤ ${Math.max(lower, upper)}) · n=${n}`,
        value: out.value,
        isProb: true,
        extras: [
          ["σ̄ = σ/√n", fmt(se)],
          ["z₁", fmt((lower - mu) / se)],
          ["z₂", fmt((upper - mu) / se)],
        ],
        casio: `MENU → 7 → 2:Normal CD · Lower=${lower}, Upper=${upper}, σ=${fmt(se, 4)}, μ=${mu}`,
        rawObj: { value: out.value, mu_bar: mu, sigma_bar: se },
      });
    } catch (err) {
      showError("r-clt", err);
    }
  });

  qs("btn-clt-plot").addEventListener("click", () => {
    const f = qs("f-clt");
    const q = new URLSearchParams(new FormData(f)).toString();
    loadPlot("clt", `/plot/png/clt?${q}`, "img-clt", "ph-clt", "dl-clt", "plot-label-clt", "CLT Sample Mean Shaded Area");
  });

  qs("f-markov").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = new URLSearchParams(new FormData(e.target)).toString();
    try {
      const out = await jfetch(`/api/ineq/markov?${q}`);
      renderResult("r-clt", {
        expr: `Markov Upper Bound: P(X ≥ ${e.target.elements.t.value}) ≤`,
        value: out.bound,
        isProb: true,
        extras: [
          ["Raw ratio E[X]/t", fmt(out.raw_ratio)],
          ["Trivial bound", out.trivial ? "Yes (≥ 1)" : "No"],
        ],
        rawObj: out,
      });
    } catch (err) {
      showError("r-clt", err);
    }
  });

  qs("f-chebyshev").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = new URLSearchParams(new FormData(e.target)).toString();
    try {
      const out = await jfetch(`/api/ineq/chebyshev?${q}`);
      renderResult("r-clt", {
        expr: `Chebyshev Outer Bound: P(|X − μ| ≥ ${e.target.elements.t.value}) ≤`,
        value: out.outer_bound,
        isProb: true,
        extras: [
          ["Inner bound P(|X−μ| < t) ≥", fmt(out.inner_bound)],
          ["k = t/σ", out.k_sigmas !== null ? fmt(out.k_sigmas) : "∞"],
        ],
        rawObj: out,
      });
    } catch (err) {
      showError("r-clt", err);
    }
  });

  // ---- JOINT (DISCRETE) INTERACTIVE GRID ----
  const jointGrid = {
    xs: [0, 1],
    ys: [0, 1],
    cells: [
      [0.1, 0.3], // y=0 -> x=0, x=1
      [0.2, 0.4], // y=1 -> x=0, x=1
    ],
  };

  function updateSumBadge() {
    let total = 0;
    for (const row of jointGrid.cells) {
      for (const val of row) total += Number(val) || 0;
    }
    const badge = qs("joint-sum-badge");
    badge.textContent = `Σp = ${total.toFixed(4)}`;
    const ok = Math.abs(total - 1.0) <= 1e-6;
    badge.className = ok ? "badge badge-success" : "badge badge-warn";
  }

  function gridToPairsString() {
    const parts = [];
    for (let xi = 0; xi < jointGrid.xs.length; xi++) {
      for (let yi = 0; yi < jointGrid.ys.length; yi++) {
        const p = jointGrid.cells[yi][xi];
        parts.push(`${jointGrid.xs[xi]},${jointGrid.ys[yi]},${Number(p.toPrecision(12))}`);
      }
    }
    return parts.join(";");
  }

  function syncInputFromGrid() {
    qs("joint-pairs-input").value = gridToPairsString();
    updateSumBadge();
  }

  function parsePairsToGrid(str) {
    const items = str.split(";").map((s) => s.trim()).filter(Boolean);
    const map = new Map();
    const xSet = new Set();
    const ySet = new Set();
    for (const item of items) {
      const parts = item.split(",").map((s) => Number(s.trim()));
      if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return false;
      const [x, y, p] = parts;
      xSet.add(x);
      ySet.add(y);
      const key = `${x}|${y}`;
      map.set(key, (map.get(key) || 0) + p);
    }
    if (xSet.size === 0 || ySet.size === 0 || xSet.size > 8 || ySet.size > 8) return false;
    jointGrid.xs = Array.from(xSet).sort((a, b) => a - b);
    jointGrid.ys = Array.from(ySet).sort((a, b) => a - b);
    jointGrid.cells = jointGrid.ys.map((y) => jointGrid.xs.map((x) => map.get(`${x}|${y}`) || 0));
    return true;
  }

  function renderJointTable() {
    const wrap = qs("joint-table-wrap");
    let html = `<table class="data-table"><thead><tr><th>Y \\ X</th>`;
    jointGrid.xs.forEach((x, xi) => {
      html += `<th><input class="grid-input grid-input-axis" type="number" step="any" data-axis="x" data-idx="${xi}" value="${x}" aria-label="X value ${xi + 1}"></th>`;
    });
    html += `</tr></thead><tbody>`;
    jointGrid.ys.forEach((y, yi) => {
      html += `<tr><th><input class="grid-input grid-input-axis" type="number" step="any" data-axis="y" data-idx="${yi}" value="${y}" aria-label="Y value ${yi + 1}"></th>`;
      jointGrid.xs.forEach((_, xi) => {
        const val = jointGrid.cells[yi][xi];
        html += `<td><input class="grid-input" type="number" step="any" min="0" data-yi="${yi}" data-xi="${xi}" value="${val}" aria-label="p(${jointGrid.xs[xi]},${y})"></td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table>`;
    wrap.innerHTML = html;

    qsa("input", wrap).forEach((inp) => {
      inp.addEventListener("input", () => {
        const v = Number(inp.value);
        if (!Number.isFinite(v)) return;
        if (inp.dataset.axis === "x") {
          jointGrid.xs[Number(inp.dataset.idx)] = v;
        } else if (inp.dataset.axis === "y") {
          jointGrid.ys[Number(inp.dataset.idx)] = v;
        } else {
          jointGrid.cells[Number(inp.dataset.yi)][Number(inp.dataset.xi)] = v;
        }
        syncInputFromGrid();
      });
    });
    updateSumBadge();
  }

  renderJointTable();

  qs("joint-pairs-input").addEventListener("input", (e) => {
    if (parsePairsToGrid(e.target.value)) {
      renderJointTable();
    }
  });

  qsa(".joint-preset").forEach((btn) => {
    btn.addEventListener("click", () => {
      qs("joint-pairs-input").value = btn.dataset.pairs;
      if (parsePairsToGrid(btn.dataset.pairs)) renderJointTable();
    });
  });

  qs("btn-joint-add-x").addEventListener("click", () => {
    if (jointGrid.xs.length >= 6) return;
    const nextX = jointGrid.xs.length ? Math.max(...jointGrid.xs) + 1 : 0;
    jointGrid.xs.push(nextX);
    jointGrid.cells.forEach((row) => row.push(0));
    renderJointTable();
    syncInputFromGrid();
  });

  qs("btn-joint-add-y").addEventListener("click", () => {
    if (jointGrid.ys.length >= 6) return;
    const nextY = jointGrid.ys.length ? Math.max(...jointGrid.ys) + 1 : 0;
    jointGrid.ys.push(nextY);
    jointGrid.cells.push(jointGrid.xs.map(() => 0));
    renderJointTable();
    syncInputFromGrid();
  });

  qs("btn-joint-norm").addEventListener("click", () => {
    let total = 0;
    for (const row of jointGrid.cells) {
      for (const val of row) total += Math.max(0, Number(val) || 0);
    }
    if (total <= 0) return;
    jointGrid.cells = jointGrid.cells.map((row) => row.map((v) => Number((Math.max(0, v) / total).toPrecision(12))));
    renderJointTable();
    syncInputFromGrid();
  });

  function renderJointOutput(data) {
    const el = qs("r-joint");
    const indBadge = data.independent
      ? `<span class="badge badge-success">Independent: Yes</span>`
      : `<span class="badge badge-warn">Independent: No (Dependent)</span>`;

    const mxRows = Object.entries(data.marginal_X || {})
      .map(([k, v]) => `<tr><td>${escHtml(k)}</td><td>${escHtml(fmt(v))}</td></tr>`)
      .join("");
    const myRows = Object.entries(data.marginal_Y || {})
      .map(([k, v]) => `<tr><td>${escHtml(k)}</td><td>${escHtml(fmt(v))}</td></tr>`)
      .join("");

    let condHtml = "";
    if (data.conditionals && data.conditionals.X_given_Y) {
      const xg = Object.entries(data.conditionals.X_given_Y)
        .map(([y, dist]) => {
          const vals = Object.entries(dist).map(([x, p]) => `P(X=${x}|Y=${y})=${fmt(p)}`).join(" · ");
          return `<div>${escHtml(vals)}</div>`;
        })
        .join("");
      const yg = Object.entries(data.conditionals.Y_given_X)
        .map(([x, dist]) => {
          const vals = Object.entries(dist).map(([y, p]) => `P(Y=${y}|X=${x})=${fmt(p)}`).join(" · ");
          return `<div>${escHtml(vals)}</div>`;
        })
        .join("");
      condHtml = `
        <details class="raw-details">
          <summary>Conditional Distributions P(X|Y) &amp; P(Y|X)</summary>
          <div class="cond-list">${xg}${yg}</div>
        </details>
      `;
    }

    el.innerHTML = `
      <div class="card-head">
        <strong>Summary Statistics</strong>
        ${indBadge}
      </div>
      <div class="stats-grid">
        <div class="stat-tile"><div class="stat-label">E[X]</div><div class="stat-value">${escHtml(fmt(data.E?.EX))}</div></div>
        <div class="stat-tile"><div class="stat-label">E[Y]</div><div class="stat-value">${escHtml(fmt(data.E?.EY))}</div></div>
        <div class="stat-tile"><div class="stat-label">Var(X)</div><div class="stat-value">${escHtml(fmt(data.Var?.VarX))}</div></div>
        <div class="stat-tile"><div class="stat-label">Var(Y)</div><div class="stat-value">${escHtml(fmt(data.Var?.VarY))}</div></div>
        <div class="stat-tile"><div class="stat-label">Cov(X, Y)</div><div class="stat-value">${escHtml(fmt(data.Cov))}</div></div>
        <div class="stat-tile"><div class="stat-label">Corr(X, Y)</div><div class="stat-value">${data.Corr === null ? "undef" : escHtml(fmt(data.Corr))}</div></div>
      </div>
      <div class="field-grid cols-2">
        <div class="table-scroll"><table class="data-table"><thead><tr><th>x</th><th>f_X(x)</th></tr></thead><tbody>${mxRows}</tbody></table></div>
        <div class="table-scroll"><table class="data-table"><thead><tr><th>y</th><th>f_Y(y)</th></tr></thead><tbody>${myRows}</tbody></table></div>
      </div>
      ${condHtml}
      <details class="raw-details">
        <summary>Raw API JSON</summary>
        <pre class="code-out" tabindex="0">${escHtml(JSON.stringify(data, null, 2))}</pre>
      </details>
    `;
  }

  qs("f-joint").addEventListener("submit", async (e) => {
    e.preventDefault();
    const pairs = qs("joint-pairs-input").value;
    try {
      const data = await jfetch(`/api/joint?${new URLSearchParams({ pairs }).toString()}`);
      renderJointOutput(data);
    } catch (err) {
      showError("r-joint", err);
    }
  });

  qs("btn-joint-heat").addEventListener("click", () => {
    const pairs = qs("joint-pairs-input").value;
    loadPlot("joint", `/plot/png/joint_discrete?${new URLSearchParams({ pairs }).toString()}`, "img-joint-heat", "ph-joint", "dl-joint", null, null);
  });

  // ---- WORKED EXAMPLES ----
  function showExampleBox(title, lines) {
    const box = qs("r-examples");
    box.classList.remove("hidden");
    box.innerHTML = `<div class="result-expr">${escHtml(title)}</div><pre class="code-out" tabindex="0">${escHtml(lines.join("\n"))}</pre>`;
  }

  qs("ex-normal").addEventListener("click", async () => {
    activateTab("normal");
    qs("norm-mu").value = "0";
    qs("norm-sigma").value = "1";
    updateNormMeta();
    qs("f-ncdf").elements.x.value = "1.96";
    qs("f-ninv").elements.p.value = "0.975";
    try {
      const [cdf, inv] = await Promise.all([
        jfetch("/api/norm/cdf?x=1.96&mu=0&sigma=1"),
        jfetch("/api/norm/inv?p=0.975&mu=0&sigma=1"),
      ]);
      state.lastNormShade = { shade_low: null, shade_high: 1.96 };
      qs("f-ncdf").dispatchEvent(new Event("submit", { cancelable: true }));
      qs("btn-npdf").click();
      showExampleBox("Worked Example — Standard Normal N(0, 1)", [
        "1. Compute CDF: Φ(1.96) = " + fmt(cdf.value) + " (" + fmtPct(cdf.value) + ")",
        "2. Compute Inverse: Φ⁻¹(0.975) = " + fmt(inv.value),
        "3. FX-991EX check: MENU → 7 → 2:Normal CD (Lower=-1E99, Upper=1.96) & 3:Inverse Normal (Area=0.975)",
      ]);
    } catch (err) {
      showError("r-examples", err);
    }
  });

  qs("ex-binom").addEventListener("click", async () => {
    activateTab("binomial");
    qs("binom-n").value = "20";
    qs("binom-p").value = "0.5";
    qs("binom-kmin").value = "8";
    qs("binom-kmax").value = "12";
    updateBinomMeta();
    try {
      const out = await jfetch("/api/binom/between?n=20&p=0.5&kmin=8&kmax=12");
      state.lastBinomHL = { highlight_k: null, highlight_min: 8, highlight_max: 12 };
      qs("f-bcdf-range").dispatchEvent(new Event("submit", { cancelable: true }));
      qs("btn-binom-pmf-plot").click();
      showExampleBox("Worked Example — Binomial(n=20, p=0.5) Range", [
        "1. P(8 ≤ X ≤ 12) = P(X ≤ 12) − P(X ≤ 7)",
        "2. Result = " + fmt(out.value) + " (" + fmtPct(out.value) + ")",
        "3. FX-991EX check: Binomial CD(x=12) − Binomial CD(x=7)",
      ]);
    } catch (err) {
      showError("r-examples", err);
    }
  });

  qs("ex-pois").addEventListener("click", async () => {
    activateTab("poisson");
    qs("pois-lam").value = "3";
    qs("pois-k").value = "2";
    updatePoisMeta();
    try {
      const pmf = await jfetch("/api/pois/pmf?lam=3&k=2");
      state.lastPoisHL = { highlight_k: 2, highlight_min: null, highlight_max: null };
      await runPois("pmf");
      qs("btn-pois-pmf-exact").click();
      showExampleBox("Worked Example — Poisson(λ=3) Point Mass", [
        "1. P(X = 2) = e⁻³ · 3² / 2! = " + fmt(pmf.value) + " (" + fmtPct(pmf.value) + ")",
        "2. FX-991EX check: MENU → 7 → 2:Poisson PD (x=2, λ=3)",
      ]);
    } catch (err) {
      showError("r-examples", err);
    }
  });

  qs("ex-joint").addEventListener("click", async () => {
    activateTab("joint");
    const pairs = "0,0,0.1;0,1,0.2;1,0,0.3;1,1,0.4";
    qs("joint-pairs-input").value = pairs;
    parsePairsToGrid(pairs);
    renderJointTable();
    try {
      const data = await jfetch(`/api/joint?${new URLSearchParams({ pairs }).toString()}`);
      renderJointOutput(data);
      qs("btn-joint-heat").click();
      showExampleBox("Worked Example — Discrete Joint 2×2", [
        `1. Marginals: f_X(0)=${fmt(data.marginal_X["0.0"] ?? data.marginal_X["0"])}, f_X(1)=${fmt(data.marginal_X["1.0"] ?? data.marginal_X["1"])}`,
        `2. Independence: ${data.independent ? "Yes" : "No"} (e.g. f(0,0)=0.1 ≠ 0.3×0.4=0.12)`,
        `3. Cov(X,Y) = ${fmt(data.Cov)}, Corr(X,Y) = ${fmt(data.Corr)}`,
      ]);
    } catch (err) {
      showError("r-examples", err);
    }
  });
})();
