# Changelog

All notable changes to `p05.dev` (formerly `probplots-web`, [github.com/hexawulf/p05.dev](https://github.com/hexawulf/p05.dev)) are documented in this file.

## [1.0.0] - 2026-11-25

### Added
- **`p05.dev` Statistical Workbench & Brand Identity:** Graduated from a thin DLBDSS wrapper to a standalone interactive workbench with the canonical 256×256 teal `static/favicon.svg`, Swiss-minimalist light/dark themes (`static/css/workbench.css`), zero-build ES modules (`static/js/`), and an α = 0.05 Standard Normal two-tailed hero default.
- **`/api/v2/*` Modular SciPy Engine (`app/stats/`, `app/api_v2.py`):**
  - **14 Distributions:** Normal, Student's *t*, $\chi^2$, *F*, Exponential, Uniform, Gamma, Beta, Log-Normal, Binomial, Poisson, 0-indexed Geometric, Negative Binomial, and Hypergeometric with `sf`/`isf` extreme-tail precision, quantile inversion, and up to 3-curve overlays.
  - **Hypothesis Testing, CIs & Power:** 1/2-sample *z*/Student/Welch *t* (raw or summary + Cohen's *d*), 1/2-proportion *z* with Wilson score CIs and lift, Power vs. *n* / MDE curves, $\chi^2$ GOF & $R \times C$ independence (Cramér's *V*, adjusted residuals), and One-Way ANOVA ($\eta^2$, $\omega^2$).
  - **Data & MLE Fitter:** Raw data parser, descriptives, $1.5 \times \text{IQR}$ outliers, Freedman–Diaconis/Sturges/Scott/manual histogram + Gaussian KDE, MLE fitting ranked by AIC & KS test, and Q-Q coordinates.
  - **Simulators & Joint Matrix:** CLT sampling lab (6 populations) and standalone discrete $(X, Y)$ joint distribution analyzer with mutual information, marginals, and conditionals.
- **Developer DX & Exports:** Interactive SVG chart with pointer-captured draggable bound handles, URL state sharing, Python/R/LaTeX/`curl` snippet drawer, keyboard shortcuts (`1`–`4`, `/`, `d`, `c`, `r`, `?`), lossless SVG export, and CSP-safe 2× Retina backend PNG export (`POST /api/v2/export/png`).
- **Verification Suite:** Added `requirements-dev.txt` and `tests/test_v2_*.py` covering numerical accuracy against `scipy.stats`, deep-tail precision, static CSP hygiene, and WCAG 2.1 AA contrast ratios.

### Preserved
- **100% v1 Backwards Compatibility:** All existing `/api/*`, `/plot/*`, `/healthz`, `/about`, and `/docs` contracts remain intact under the `v1 Legacy` and `System` OpenAPI tags.

## [0.3.0] - 2026-11-24

### Added
- **Fleetwide Teal UI Refresher & Dark Mode:** Replaced external `cdn.tailwindcss.com` with self-hosted `static/styles.css`, `static/app.js`, `static/theme-init.js`, and canonical teal `static/favicon.svg` (zero external origins, WCAG AA contrast across light & dark themes).
- **Tabbed Calculator Workspace:** Organized Normal, Binomial, Poisson, Geo/Exp/Unif, CLT & Bounds, and Joint (X, Y) into focused two-column workspaces with unified parameter bars, decimal precision selector (`2 / 4 / 6 / Full` d.p.), copy-result buttons, PNG downloads, and Casio FX-991EX keystroke tips.
- **Interactive Discrete Joint Builder:** Added live editable contingency table synced with `x,y,p;...` pairs, `Σp` validation badge, one-click Normalize, preset distributions, formatted marginals & conditionals (`P(X|Y)`, `P(Y|X)`), and annotated teal heatmaps.
- **Expanded API Endpoints:** Added `/api/norm/pdf`, `/api/norm/interval`, `/api/pois/atleast`, `/api/pois/between`, `/api/geom/cdf`, `/api/exp/pdf`, `/api/exp/inv`, `/api/unif/pdf`, `/api/ineq/markov`, and `/api/ineq/chebyshev`, plus optional `?theme=light|dark`, shading, and bar highlighting on plot endpoints.
- **Security & Testing:** Added `HEAD` support for `/` and `/healthz`, strict CSP & security headers middleware, `requirements.txt`, `pyproject.toml`, and `tests/` (`pytest` unit + API + PNG plot suite).

### Fixed
- Resolved hardcoded `/home/zk/projects/probplots-web/static/index.html` path in `app/api.py` using `Path(__file__)`; added `PROBPLOTS_HELPER_DIR` + sibling `../probplots` auto-lookup and replaced bare `raise` (`PLE0704`) in fallback stub.
- Fixed off-by-one math bug in `plot_geometric_pmf` (0-indexed failures before first success now matches `geom_pmf` and axis label).
- Replaced global `matplotlib.pyplot` state with thread-safe OO `Figure` + `FigureCanvasAgg` and added strict input validation and upper bounds on simulation/discrete plot parameters.
- Fixed unhandled JS fetch errors with inline `role="alert"` banners and fixed About modal centering & backdrop dismissal.

### Removed
- Deleted unused dead module `app/utils_plot_png.py`, obsolete v1 build prompt `plan.md`, and unused imports in `app/dlbdss_core.py`.
- Removed third-party `https://cdn.tailwindcss.com` runtime dependency and stale `containeryard.org` CORS allowlist entry in `nginx-probplots.piapps.dev`.

## [0.2.0] - 2025-11-09

- Initial FastAPI wrapper, calculator dashboard UI, About modal, `/api/joint` integration, Poisson PMF, Binomial shortcuts, worked examples, and `/plot/png/*` endpoints.
