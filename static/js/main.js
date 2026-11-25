/* p05.dev ES-module workbench bootstrap */

import { apiRequest } from "./api.js";
import { buildSnippets } from "./snippets.js";
import {
  appState,
  loadInitialPrecision,
  readUrlState,
  savePrecision,
  syncUrlState,
} from "./state.js";
import {
  evaluateNow,
  initExplorer,
  refreshExplorerTheme,
  resetExplorer,
  selectDistribution,
} from "./workspaces/explorer.js";
import { initFitting, refreshFittingTheme, runAnalyze } from "./workspaces/fitting.js";
import { initInference, refreshInferenceTheme } from "./workspaces/inference.js";
import { initSimulators, refreshSimTheme } from "./workspaces/simulators.js";

function qs(id) {
  return document.getElementById(id);
}

function updateThemeUi(theme) {
  appState.theme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  qs("icon-sun").classList.toggle("hidden", theme !== "dark");
  qs("icon-moon").classList.toggle("hidden", theme === "dark");
  try {
    localStorage.setItem("p05-theme", theme);
  } catch {
    // ignore storage errors
  }
  refreshExplorerTheme();
  refreshInferenceTheme();
  refreshFittingTheme();
  refreshSimTheme();
}

function toggleTheme() {
  updateThemeUi(appState.theme === "dark" ? "light" : "dark");
}

function activateWorkspace(ws) {
  appState.workspace = ws;
  syncUrlState();
  document.querySelectorAll(".ws-tab").forEach((btn) => {
    btn.setAttribute("aria-selected", btn.dataset.ws === ws ? "true" : "false");
  });
  ["explorer", "inference", "fitting", "simulators"].forEach((name) => {
    qs(`ws-${name}`).classList.toggle("hidden", name !== ws);
  });
}

function refreshSnippetDrawer() {
  qs("snippet-output").textContent = buildSnippets(appState.snippetCtx, appState.drawerLang);
}

function toggleDrawer(forceOpen = null) {
  const next = forceOpen !== null ? forceOpen : !appState.drawerOpen;
  appState.drawerOpen = next;
  qs("code-drawer").classList.toggle("hidden", !next);
  qs("btn-code-drawer").classList.toggle("btn-active", next);
  if (next) refreshSnippetDrawer();
}

function initSearch(catalog) {
  const input = qs("dist-search");
  const drop = qs("dist-search-results");

  const renderMatches = (q) => {
    const term = q.trim().toLowerCase();
    const matches = catalog.distributions.filter(
      (d) =>
        !term ||
        d.name.toLowerCase().includes(term) ||
        d.id.toLowerCase().includes(term) ||
        d.family.toLowerCase().includes(term)
    );
    drop.replaceChildren();
    if (!matches.length) {
      drop.classList.add("hidden");
      return;
    }
    matches.forEach((d) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "search-item";
      btn.innerHTML = `<span>${d.name}</span><span class="badge">${d.family}</span>`;
      btn.addEventListener("click", () => {
        drop.classList.add("hidden");
        input.value = "";
        activateWorkspace("explorer");
        selectDistribution(d.id);
      });
      drop.appendChild(btn);
    });
    drop.classList.remove("hidden");
  };

  input.addEventListener("focus", () => renderMatches(input.value));
  input.addEventListener("input", () => renderMatches(input.value));
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box")) drop.classList.add("hidden");
  });
}

function initModalsAndKeys() {
  const modal = qs("help-modal");
  const openModal = () => modal.classList.remove("hidden");
  const closeModal = () => modal.classList.add("hidden");

  qs("btn-help").addEventListener("click", openModal);
  qs("help-close").addEventListener("click", closeModal);
  qs("help-ok").addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeModal();
      qs("dist-search-results").classList.add("hidden");
      return;
    }
    const tag = document.activeElement?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    if (e.key === "1") activateWorkspace("explorer");
    else if (e.key === "2") activateWorkspace("inference");
    else if (e.key === "3") activateWorkspace("fitting");
    else if (e.key === "4") activateWorkspace("simulators");
    else if (e.key === "/") {
      e.preventDefault();
      qs("dist-search").focus();
    } else if (e.key === "d") {
      toggleTheme();
    } else if (e.key === "c") {
      toggleDrawer();
    } else if (e.key === "r") {
      if (appState.workspace === "explorer") resetExplorer();
      else if (appState.workspace === "fitting") runAnalyze();
    } else if (e.key === "?") {
      openModal();
    }
  });
}

async function boot() {
  readUrlState();
  const prec = loadInitialPrecision();
  qs("precision-select").value = prec;
  qs("precision-select").addEventListener("change", (e) => {
    savePrecision(e.target.value);
    if (appState.workspace === "explorer") evaluateNow();
  });

  updateThemeUi(appState.theme);
  qs("btn-theme").addEventListener("click", toggleTheme);

  // Share link
  qs("btn-share").addEventListener("click", async () => {
    syncUrlState();
    try {
      await navigator.clipboard.writeText(window.location.href);
      qs("btn-share").textContent = "Link Copied";
      setTimeout(() => {
        qs("btn-share").textContent = "Copy Share Link";
      }, 1500);
    } catch {
      qs("btn-share").textContent = "URL Updated";
    }
  });

  // Code drawer
  qs("btn-code-drawer").addEventListener("click", () => toggleDrawer());
  qs("btn-close-drawer").addEventListener("click", () => toggleDrawer(false));
  qs("code-drawer")
    .querySelectorAll("[data-lang]")
    .forEach((btn) => {
      btn.addEventListener("click", () => {
        appState.drawerLang = btn.dataset.lang;
        qs("code-drawer")
          .querySelectorAll("[data-lang]")
          .forEach((b) => b.classList.toggle("is-active", b === btn));
        refreshSnippetDrawer();
      });
    });
  qs("btn-copy-snippet").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(qs("snippet-output").textContent);
      qs("btn-copy-snippet").textContent = "Copied";
      setTimeout(() => {
        qs("btn-copy-snippet").textContent = "Copy Snippet";
      }, 1200);
    } catch {
      // ignore clipboard errors
    }
  });
  document.addEventListener("p05:snippet-updated", () => {
    if (appState.drawerOpen) refreshSnippetDrawer();
  });

  // Workspace tab clicks
  document.querySelectorAll(".ws-tab").forEach((btn) => {
    btn.addEventListener("click", () => activateWorkspace(btn.dataset.ws));
  });

  const catalog = await apiRequest("/api/v2/dist/catalog");
  initSearch(catalog);
  initExplorer(catalog);
  initInference();
  initFitting();
  initSimulators();
  initModalsAndKeys();
  activateWorkspace(appState.workspace);
}

boot().catch((err) => {
  const errEl = qs("exp-error");
  if (errEl) {
    errEl.textContent = `Workbench failed to initialize: ${err.message}`;
    errEl.classList.remove("hidden");
  }
});
