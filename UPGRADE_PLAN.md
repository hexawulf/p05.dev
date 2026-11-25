# `probplots-web` v2 (`1.0.0`) — Architecture & Upgrade Plan

## 1. Phase 0 Audit Summary (Current State `v0.3.0`)

- **Repository & Runtime (`probplots-web`):**
  - **Footprint:** `4,420` lines across 20 files (`app/api.py` 646L, `app/dlbdss_core.py` 245L, `app/plotting.py` 571L, `static/index.html` 496L, `static/styles.css` 863L, `static/app.js` 1034L, `tests/` 219L, scripts & configs). Note: stale `plan.md` was removed in `ba68023` (original v1/v2 prompt remains in sibling `../probplots/plan.md`).
  - **Service & Ingress:** Bound to `127.0.0.1:5009` via `probplots-web.service` (`uvicorn app.api:app`, `OPENBLAS_NUM_THREADS=1`, Python `3.14.4` `.venv` with `fastapi 0.136.1`, `pydantic 2.13.3`, `scipy 1.17.1`, `numpy 2.4.4`, `matplotlib 3.10.9`, `pillow 12.2.0`). Fronted by `nginx-probplots.piapps.dev` (`https://probplots.piapps.dev/`).
  - **Library Imports & Sibling Dependency:**
    - `app/api.py` dynamically prepends `PROBPLOTS_HELPER_DIR` or `../probplots` to `sys.path` to import `stats_helper.compute_joint_stats` (`JointDist`), falling back to an in-process stub when `PROBPLOTS_STUB=1`.
    - `app/dlbdss_core.py` uses `scipy.stats` for scalar distributions and Markov/Chebyshev bounds.
    - `app/plotting.py` uses thread-safe OO `matplotlib.figure.Figure` + `FigureCanvasAgg` (no global `pyplot` state) for server-side PNG plots.
- **Key Findings Shaping v2 Design:**
  1. **Zero Nginx Changes Required:** `location /api/` already proxies `GET, POST, PUT, PATCH, DELETE, OPTIONS` (`client_max_body_size 10m`, `proxy_read_timeout 75s`) to `127.0.0.1:5009`, so all `/api/v2/*` `GET` and `POST` endpoints work immediately behind the existing reverse proxy.
  2. **Strict CSP Compliance (`app/api.py`):** Root `/` enforces `Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'`. All CSS/JS will remain 100% self-hosted (zero CDNs), and our custom SVG chart engine will use pure SVG presentation attributes (`d`, `transform`, `fill`, `stroke`, `stroke-dasharray`) + CSS classes — **never** inline `style="..."` attributes, which `style-src 'self'` blocks.
  3. **Extreme-Tail Numerical Precision:** v1 interval helpers (`cdf(upper) - cdf(lower)`) suffer floating-point cancellation in deep upper tails (e.g., $P(9 \le Z \le 10)$ on $N(0,1)$ collapses to `0.0`). v2 will systematically use `scipy.stats` survival functions (`sf`, `isf`) and median-split interval differences (`sf(a) - sf(b)` when $a$ is above the median).
  4. **Test Tooling in `.venv`:** `.venv` has runtime packages installed; we will add `requirements-dev.txt` (`pytest`, `httpx`, `ruff`) and install them into `.venv` so `.venv/bin/pytest` and `.venv/bin/ruff` run deterministically on-host.

---

## 2. Target File Layout (Compact, Modular, Zero Build Bloat)

Target total footprint: **~5,800–6,500 LOC** across backend, zero-dependency ES-module frontend, and comprehensive `pytest` suite.

```text
probplots-web/
├── app/
│   ├── __init__.py
│   ├── api.py                      # App entry (app.api:app), CSP/security middleware, System routes (/, /healthz,
│   │                               #   /about, /favicon.ico), preserved v1 /api/* & /plot/* routes, mounts api_v2
│   ├── api_v2.py                   # APIRouter(prefix="/api/v2") — OpenAPI-documented v2 JSON endpoints
│   ├── dlbdss_core.py              # Preserved v1 pure probability/inequality functions (untouched signatures)
│   ├── plotting.py                 # Preserved v1 Matplotlib Agg PNG plotters (untouched signatures)
│   └── stats/                      # Modular v2 statistical engine (scipy.stats + numpy)
│       ├── __init__.py
│       ├── schemas.py              # Pydantic v2 models, finite-float validators, domain constraints & examples
│       ├── distributions.py        # 14-distribution engine (9 continuous, 5 discrete), exact moments, sf/isf tails
│       ├── inference.py            # Means (z/t/Welch + d), Props (Wilson/lift/power), Chi2 (GOF/RxC/V), One-Way ANOVA
│       ├── fitting.py              # Raw data parser, descriptive stats, Hist+KDE, MLE auto-fit (AIC/KS), Q-Q coords
│       └── simulators.py           # CLT sampling lab (6 populations) + standalone Discrete Joint (X, Y) matrix engine
├── static/
│   ├── index.html                  # Swiss-minimalist 4-workspace shell + Code/Formula drawer + shortcuts/about modals
│   ├── favicon.svg                 # Vector brand mark (also served for /favicon.ico to eliminate 404 log noise)
│   ├── theme-init.js               # Synchronous <head> light/dark initializer (zero FOUC, CSP script-src 'self')
│   ├── css/
│   │   └── workbench.css           # Monochrome Swiss grid, 1px hairlines, tabular-nums, single high-contrast accent
│   └── js/
│       ├── main.js                 # ES module bootstrap: workspace router, keyboard shortcuts, theme, precision, export
│       ├── state.js                # Central state + URL query sync (history.replaceState) + Copy Share Link
│       ├── api.js                  # Fetch wrapper with AbortController & structured 400/422 math error rendering
│       ├── chart.js                # Custom zero-dep interactive SVG engine + 2x Retina Canvas PNG & SVG exporter
│       ├── snippets.js             # Live Python (scipy.stats), R, LaTeX, and curl snippet generator
│       ├── presets.js              # Curated distribution presets, sample empirical datasets, and test/joint presets
│       └── workspaces/
│           ├── explorer.js         # Workspace 1: Distribution Explorer & Comparator (drag bounds, inverse, 3x overlay)
│           ├── inference.js        # Workspace 2: Hypothesis Tests, CIs & Power Workbench
│           ├── fitting.js          # Workspace 3: Empirical Data, Hist+KDE, MLE Auto-Fit & Q-Q Plot
│           └── simulators.js       # Workspace 4: CLT Sampling Distribution Lab & Discrete Joint (X, Y) Matrix
├── tests/
│   ├── test_core.py                # Preserved v1 unit tests
│   ├── test_api.py                 # Preserved v1 API & PNG regression suite (+ OpenAPI tag checks)
│   ├── test_v2_distributions.py    # 14 distributions: moments, entropy, sf/isf deep-tail accuracy vs scipy.stats
│   ├── test_v2_inference.py        # z/t/Welch, Wilson CI, power/sample-size, Chi2 GOF/RxC, ANOVA reference checks
│   └── test_v2_fitting_sim.py      # Descriptives, bin rules/KDE, MLE AIC/KS ranking, Q-Q, CLT & Joint v2 checks
├── scripts/                        # Preserved install.sh, run-dev.sh, make-systemd.sh
├── probplots-web.service           # Preserved untouched (127.0.0.1:5009 -> app.api:app)
├── nginx-probplots.piapps.dev      # Preserved untouched
├── requirements.txt                # Runtime dependencies (unchanged)
├── requirements-dev.txt            # pytest, httpx, pillow, ruff
├── pyproject.toml                  # pytest + ruff config
├── CHANGELOG.md
├── README.md
└── UPGRADE_PLAN.md
```

> **Housekeeping note on v0.3 frontend files:** Upon approval, `static/app.js` and `static/styles.css` will be backed up to `/home/zk/backups/` before `index.html` transitions to `/static/css/workbench.css` and `/static/js/main.js` (keeping minimal redirect/compat stubs or retiring old files per operator preference; default: back up to `/home/zk/backups/` and keep repo clean).

---

## 3. 100% Backwards Compatibility Strategy

1. **System & Root Endpoints (`tags=["System"]`):**
   - `GET /` & `HEAD /` (HTML UI + strict security/CSP headers), `GET /healthz` & `HEAD /healthz` (`{"status": "ok"}`), `GET /about` (`app`, `version`, `bind`), `GET /docs`, `GET /openapi.json` preserved verbatim.
   - Add `GET /favicon.ico` (`include_in_schema=False`) redirecting (`302`) to `/static/favicon.svg` to stop browser favicon 404s in Uvicorn logs.
2. **Legacy Numeric Endpoints (`tags=["v1 Legacy"]`):**
   - All 22 existing `GET /api/*` routes (`/api/norm/{pdf,cdf,interval,inv}`, `/api/binom/{pmf,cdf,cdf-range,atmost,atleast,between}`, `/api/pois/{pmf,cdf,atleast,between}`, `/api/geom/{pmf,cdf}`, `/api/exp/{pdf,cdf,inv}`, `/api/unif/{pdf,cdf}`, `/api/clt`, `/api/ineq/{markov,chebyshev}`, `/api/joint`) keep identical query signatures, HTTP `400`/`422` validation semantics, and JSON response keys (`{"value": ...}`, joint dict with `conditionals`, etc.).
3. **Legacy Server-Side PNG Endpoints (`tags=["v1 Legacy"]`):**
   - All 14 `/plot/png/*` routes and all 8 `/plot/{pdf,pmf,cdf,sim,clt,heat}/*` aliases keep identical query parameters, DoS caps (`MAX_SIM_N`, `MAX_DISCRETE_N`, `MAX_KMAX`, `MAX_BINS`), and `theme=light|dark` PNG output.
4. **Sibling `probplots` Compatibility:**
   - `app/api.py` retains `PROBPLOTS_HELPER_DIR` / `../probplots` lookup + `PROBPLOTS_STUB=1` for `/api/joint`, while `/api/v2/sim/joint` uses a standalone pure-Python/NumPy implementation in `app/stats/simulators.py` so v2 has zero external repo coupling.

---

## 4. `/api/v2/*` Engine & Mathematical Specification

All `/api/v2/*` endpoints use strict **Pydantic v2** schemas (`extra="forbid"`, finite-float checks rejecting `NaN`/`Inf`), explicit mathematical error messages on domain violations (`HTTP 422`/`400`), and OpenAPI examples grouped under:
- `v2 Distributions`
- `v2 Hypothesis Tests`
- `v2 Data & Fitting`
- `v2 Simulators`

### 4.1 Unified Distribution Engine (`app/stats/distributions.py`)
- **`GET /api/v2/dist/catalog`** — Parameter specs, domain bounds, LaTeX density formulas, parameterization notes, and curated presets for **14 distributions**:
  - **Continuous (9):** `normal` ($\mu, \sigma>0$), `student_t` ($\nu>0, \mu=0, \sigma=1$), `chi2` ($k>0$), `f` ($d_1>0, d_2>0$), `exponential` (rate $\lambda>0$, scale $1/\lambda$), `uniform` ($a<b$), `gamma` (shape $\alpha>0$, rate $\beta>0$), `beta` ($\alpha>0, \beta>0$), `lognormal` (log-mean $\mu$, log-sd $\sigma>0$).
  - **Discrete (5):** `binomial` ($n \ge 1, p \in [0,1]$), `poisson` ($\lambda>0$), `geometric` ($p \in (0,1]$, **explicitly $k \in \{0,1,2,\dots\}$ failures before first success** via `scipy.stats.geom(p, loc=-1)`), `negbinom` ($r>0$ successes, $p \in (0,1]$, $k \ge 0$ failures), `hypergeom` (population $M \ge 1$, success states $K \in [0,M]$, draws $n \in [1,M]$).
- **`POST /api/v2/dist/evaluate`** — Computes:
  - Exact summary strip: `mean`, `variance`, `std`, `median`, `mode` (analytic closed-form including boundary/undefined notes for $t, F, \text{Beta}, \text{Uniform}$), `skewness`, `excess_kurtosis`, `entropy` (differential or Shannon nats).
  - Exact probability for region `left` ($P(X \le a)$), `right` ($P(X \ge b)$), `interval` ($P(a \le X \le b)$), or `two_tailed` ($P(X \le a \text{ or } X \ge b)$):
    - Right tails use `dist.sf(b)` (continuous) and `dist.sf(ceil(b) - 1)` (discrete).
    - Upper-half intervals ($a > \text{median}$) use `dist.sf(a) - dist.sf(b)` (continuous) and `dist.sf(kmin - 1) - dist.sf(kmax)` (discrete) to prevent `1 - 1` cancellation.
    - Two-tailed regions sum `cdf` (left) + `sf` (right) directly without subtracting from `1`.
  - Plot series (`x`, `pdf`/`pmf`, `cdf`) across unified auto-scaled support + up to **3 overlaid comparison curves**.
- **`POST /api/v2/dist/quantile`** — Inverse/quantile solver snapping critical bound(s) $(a, b)$ to target probability $p \in (0,1)$ using `ppf` (left) and `isf` (right/central/two-tailed).

### 4.2 Hypothesis Testing, CIs & Power (`app/stats/inference.py`)
- **`POST /api/v2/inference/means`** — 1-sample $z$, 1-sample $t$, 2-sample Student's pooled $t$, and 2-sample Welch's $t$ (from summary stats OR raw pasted arrays; two-sided/less/greater; $\alpha \in (0, 0.5)$). Reports statistic, exact $df$, `sf`-based $p$-value, $(1-\alpha)$ CI, critical value(s), **Cohen's $d$**, and null curve + tail shading coordinates.
- **`POST /api/v2/inference/proportions`** — 1-proportion and 2-proportion $z$-test with **Wilson score CIs**, difference CI, **absolute & relative lift**, Cohen's $h$, $z$-stat, exact $p$-value, and null $N(0,1)$ shading coordinates.
- **`POST /api/v2/inference/power`** — Sample size $n$ & statistical power solver for two-proportion A/B tests and 1/2-sample means, returning exact required $n$ (or achieved power) plus interactive **Power vs. $n$** and **Power vs. MDE** curve coordinates.
- **`POST /api/v2/inference/chisq`** — Goodness-of-Fit and $R \times C$ Contingency Table Independence (`scipy.stats.chi2_contingency`), returning $\chi^2$, $df$, exact $p$-value, expected counts matrix, **standardized Pearson residuals**, **Cramér's $V$** (or Cohen's $w$ for GOF), low-expected-count warning ($E_{ij} < 5$), and $\chi^2(df)$ tail curve.
- **`POST /api/v2/inference/anova`** — One-Way ANOVA ($k \ge 2$ groups from raw columns OR summary stats $(n_i, \bar{x}_i, s_i)$), outputting standard ANOVA table ($SS_B, df_B, MS_B, SS_W, df_W, MS_W, SS_T, df_T, F, p$), **$\eta^2$** & $\omega^2$, per-group CIs, and $F(df_B, df_W)$ tail curve.

### 4.3 Empirical Data & Distribution Fitter (`app/stats/fitting.py`)
- **`POST /api/v2/fit/analyze`** — Parses raw numeric values ($2 \le n \le 50,000$), computes full descriptive stats ($n$, mean, 10% trimmed mean, median, sample/pop std, IQR, min/max, skewness, excess kurtosis, 95% $t$-CI for mean, $1.5 \times \text{IQR}$ outliers), histogram (`fd`, `sturges`, `scott`, or `manual` bins) + **Gaussian KDE**, and fits **Normal, Log-Normal, Exponential, Gamma, and Uniform** via MLE (cleanly skipping positive-only families with explanation if $\min(x) \le 0$), ranked by **AIC** with **Kolmogorov-Smirnov $(D, p)$** and **Q-Q plot** theoretical vs. sample quantiles.

### 4.4 Interactive Simulators & Joint Matrix (`app/stats/simulators.py`)
- **`POST /api/v2/sim/clt`** — Draws $N \in [100, 50,000]$ sample means of size $n \in [1, 200]$ (optional `seed`) from `uniform`, `exponential`, `skewed_beta`, `bimodal`, `bernoulli`, or `poisson`, returning empirical $\bar{X}$ histogram, sample moments, theoretical population $(\mu, \sigma)$, live SE $\sigma/\sqrt{n}$, and overlaid $N(\mu, \sigma^2/n)$ density.
- **`POST /api/v2/sim/joint`** — Validates $R \times C$ probability table ($p_{ij} \ge 0$, $|\sum p_{ij} - 1| \le 10^{-9}$, optional `auto_normalize`), returning marginals, conditionals $P(Y \mid X=x)$ & $P(X \mid Y=y)$, independence check + max deviation, $E[X], E[Y], \text{Var}(X), \text{Var}(Y), \text{Cov}(X,Y), \text{Corr}(X,Y)$, and mutual information $I(X; Y)$.

---

## 5. Frontend Architecture (Zero-Build ES Modules + Custom SVG Engine)

- **Strictly No Build Pipeline:** Native browser ES modules (`static/js/*.js`) + single stylesheet (`static/css/workbench.css`). Zero `package.json`, zero `node_modules`, zero external fonts/CDNs.
- **Why Custom `<svg>` (`static/js/chart.js`) Over a Vendored Library:**
  - ~15 KB of purpose-built code vs. 200 KB+ generic charting libraries.
  - Native pointer-captured (`setPointerCapture`) **draggable vertical handles $(a, b)$** directly on the axes with instant 60fps local polygon shading during drag + debounced `/api/v2/dist/evaluate` exact `scipy.stats` sync.
  - Supports multi-curve overlays (solid, dashed, dotted strokes + clean legend), discrete stem/bar shading, test-stat + critical markers, Hist+KDE + fitted PDF, Q-Q scatter + $45^\circ$ line, power curves, and joint heatmap + marginal bars.
  - **100% CSP-safe** (pure SVG attributes + CSS classes, zero inline `style` attributes) and enables lossless **1-click SVG export** + **2x Retina PNG export** (rendered onto an offscreen `2x` `<canvas>` via `Blob` URL matching light or dark theme).
- **Swiss-Minimalist UI & Developer DX:**
  - Monochrome light/dark surfaces (`1px` crisp hairline borders, `font-variant-numeric: tabular-nums` across all metrics/tables/inputs, single high-contrast teal accent for probability mass/density shading).
  - **URL State Persistence (`state.js`):** Syncs active workspace, parameters, bounds, and overlays into URL query params (`history.replaceState`) + **Copy Share Link** button.
  - **Code & Formula Drawer (`snippets.js`):** Live copy-ready **Python (`scipy.stats`)**, **R**, **LaTeX** formula, and **`curl`** `/api/v2/...` snippet.
  - **Keyboard-First Navigation:** `1`–`4` workspaces, `/` search distributions, `d` dark/light toggle, `r` reset workspace, `c` code/formula drawer, `?` shortcuts/about, `Esc` close.

---

## 6. Verification & Test Plan

1. **Preserved v1 Regression Suite (`tests/test_core.py`, `tests/test_api.py`):**
   - All existing unit tests, 22 `/api/*` endpoints, 22 `/plot/*` light & dark PNG endpoints, DoS caps, and CSP/security header checks must pass with zero modifications to expected v1 contracts.
2. **Numerical Accuracy Suite (`tests/test_v2_distributions.py`):**
   - Cross-check PDF/PMF, CDF, SF, quantiles (`ppf`/`isf`), moments, and entropy across all **14 distributions** against direct `scipy.stats` reference calls (`rel_tol=1e-10`).
   - Explicit **extreme-tail tests** (e.g., Normal $z \in \{8, 15, 30\}$, $\chi^2$, Student's $t$, Binomial/Poisson tail probabilities $< 10^{-18}$) verifying `sf`/`isf` accuracy where `1 - cdf` underflows to `0.0`, plus `quantile -> evaluate` round-trip consistency.
   - Verify undefined/infinite moment edge cases ($t(\nu=1, 2)$, $F(d_1=2, d_2=2)$, $\text{Beta}(0.5, 0.5)$) serialize cleanly without `NaN` JSON errors.
3. **Hypothesis Tests & Power Suite (`tests/test_v2_inference.py`):**
   - Verify 1/2-sample $z$, pooled $t$, and Welch $t$ (confirming summary-stats mode matches raw-data mode to `< 1e-12`), Cohen's $d$, 1/2-proportion $z$ + Wilson score CIs, monotonic sample-size/power curves against analytical normal-approximation formulas, $\chi^2$ GOF & $R \times C$ contingency (`chi2_contingency`, standardized residuals, Cramér's $V$), and One-Way ANOVA (`f_oneway` equivalence between raw and summary inputs + $\eta^2$).
4. **Empirical Fitter & Simulators Suite (`tests/test_v2_fitting_sim.py`):**
   - Verify raw text parsing (CSV/TSV/whitespace/newlines), descriptive stats & $1.5 \times \text{IQR}$ outliers, histogram bin rules (`fd`, `sturges`, `scott`, `manual`), MLE parameter recovery & AIC/KS ranking on seeded synthetic data (including non-positive data guard for Log-Normal/Gamma/Exponential), Q-Q plot monotonicity, seeded CLT SE $\sigma/\sqrt{n}$ convergence, and Joint $(X,Y)$ sum-to-1 tolerance ($10^{-9}$), independence, moments, and conditionals.
5. **End-to-End Smoke & Lint Gate:**
   - `.venv/bin/ruff check app tests` -> zero warnings/errors.
   - `.venv/bin/pytest` -> 100% green.
   - Local `uvicorn` verification on ephemeral loopback port (`127.0.0.1:15009`) checking `/`, `/healthz`, `/about`, `/docs`, `/openapi.json`, key `/api/v2/*` endpoints, and legacy `/api/*` + `/plot/*` routes without disrupting live `:5009` until approved.
