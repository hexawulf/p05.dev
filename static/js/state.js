/* Central state store, precision formatter, and URL query persistence (history.replaceState) */

export const DEFAULT_EXPLORER = {
  dist: "normal",
  params: { mu: 0, sigma: 1 },
  region: "two_tailed",
  a: -1.959963984540054,
  b: 1.959963984540054,
  view: "pdf",
  overlays: [],
};

export const appState = {
  workspace: "explorer",
  precision: "4",
  theme: document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light",
  drawerOpen: false,
  drawerLang: "python",
  catalog: null,
  explorer: structuredClone(DEFAULT_EXPLORER),
  lastResult: null,
  lastExportSpec: null,
  inferenceSub: "means",
  simSub: "clt",
  snippetCtx: {
    workspace: "explorer",
    payload: null,
  },
};

export function loadInitialPrecision() {
  try {
    const saved = localStorage.getItem("p05-precision") || localStorage.getItem("probplots-precision");
    if (saved && ["2", "4", "6", "full"].includes(saved)) {
      appState.precision = saved;
    }
  } catch {
    // ignore storage errors
  }
  return appState.precision;
}

export function savePrecision(prec) {
  appState.precision = prec;
  try {
    localStorage.setItem("p05-precision", prec);
  } catch {
    // ignore
  }
}

export function fmtNum(val, overrideDigits) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  const n = Number(val);
  if (!Number.isFinite(n)) return String(n);
  if (Math.abs(n) < 1e-14) return "0";
  const prec = overrideDigits !== undefined ? overrideDigits : appState.precision;
  if (prec === "full") return String(n);
  const d = Number(prec);
  if (Math.abs(n) > 0 && Math.abs(n) < Math.pow(10, -d)) {
    return n.toExponential(Math.max(2, d - 1));
  }
  return n.toFixed(d);
}

export function fmtPct(prob) {
  if (prob === null || prob === undefined || !Number.isFinite(Number(prob))) return "";
  return `${(Number(prob) * 100).toFixed(2)}%`;
}

export function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function readUrlState() {
  try {
    const sp = new URLSearchParams(window.location.search);
    const ws = sp.get("ws");
    if (ws && ["explorer", "inference", "fitting", "simulators"].includes(ws)) {
      appState.workspace = ws;
    }
    const inf = sp.get("inf");
    if (inf && ["means", "props", "power", "chisq", "anova"].includes(inf)) {
      appState.inferenceSub = inf;
    }
    const sim = sp.get("sim");
    if (sim && ["clt", "joint"].includes(sim)) {
      appState.simSub = sim;
    }
    const dist = sp.get("dist");
    if (dist) {
      appState.explorer.dist = dist;
      const rawParams = sp.get("p");
      if (rawParams) {
        const parsed = JSON.parse(rawParams);
        if (parsed && typeof parsed === "object") appState.explorer.params = parsed;
      }
      const reg = sp.get("region");
      if (reg && ["left", "right", "interval", "two_tailed", "none"].includes(reg)) {
        appState.explorer.region = reg;
      }
      const view = sp.get("view");
      if (view === "pdf" || view === "cdf") appState.explorer.view = view;
      const a = sp.get("a");
      const b = sp.get("b");
      if (a !== null && Number.isFinite(Number(a))) appState.explorer.a = Number(a);
      if (b !== null && Number.isFinite(Number(b))) appState.explorer.b = Number(b);
      const ov = sp.get("ov");
      if (ov) {
        const parsedOv = JSON.parse(ov);
        if (Array.isArray(parsedOv)) appState.explorer.overlays = parsedOv.slice(0, 2);
      }
    }
  } catch {
    // Fallback cleanly to hero default state on malformed URL params
  }
}

export function syncUrlState() {
  try {
    const sp = new URLSearchParams();
    sp.set("ws", appState.workspace);
    if (appState.workspace === "explorer") {
      sp.set("dist", appState.explorer.dist);
      sp.set("p", JSON.stringify(appState.explorer.params));
      sp.set("region", appState.explorer.region);
      sp.set("view", appState.explorer.view);
      if (appState.explorer.a !== null && Number.isFinite(appState.explorer.a)) {
        sp.set("a", Number(appState.explorer.a).toPrecision(8));
      }
      if (appState.explorer.b !== null && Number.isFinite(appState.explorer.b)) {
        sp.set("b", Number(appState.explorer.b).toPrecision(8));
      }
      if (appState.explorer.overlays.length > 0) {
        sp.set("ov", JSON.stringify(appState.explorer.overlays));
      }
    } else if (appState.workspace === "inference") {
      sp.set("inf", appState.inferenceSub);
    } else if (appState.workspace === "simulators") {
      sp.set("sim", appState.simSub);
    }
    const nextUrl = `${window.location.pathname}?${sp.toString()}`;
    window.history.replaceState(null, "", nextUrl);
  } catch {
    // Ignore history API errors
  }
}
