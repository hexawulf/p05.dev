# Changelog

All notable changes to `probplots-web` are documented in this file.

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
