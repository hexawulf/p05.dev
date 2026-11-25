# p05.dev (`probplots-web`)

Self-hosted interactive probability & statistics workbench built with FastAPI, SciPy/NumPy, and zero-build vanilla ES modules + custom SVG plotting (`https://p05.dev` / `https://probplots.piapps.dev`).

Repository: [github.com/hexawulf/p05.dev](https://github.com/hexawulf/p05.dev) · Author: Erling Wulf Weinreich ([0xWulf](https://0xwulf.dev)) · `dev@0xwulf.dev`

## Highlights (`v1.0.0`)

- **Workspace 1 — Distribution Explorer & Comparator:** 14 distributions (9 continuous: Normal, Student's *t*, $\chi^2$, *F*, Exponential, Uniform, Gamma, Beta, Log-Normal; 5 discrete: Binomial, Poisson, 0-indexed Geometric, Negative Binomial, Hypergeometric). Features draggable bound handles directly on the SVG chart, two-way inverse quantile snapping, up to 3 overlaid comparison curves, PDF/CDF toggle, and exact moments/entropy powered by `scipy.stats` survival functions (`sf` / `isf`) to avoid tail cancellation.
- **Workspace 2 — Hypothesis Testing, CIs & Power:** 1/2-sample *z*, Student's *t*, and Welch's *t* (raw or summary stats + Cohen's *d*), 1/2-proportion *z*-tests with Wilson score CIs and lift, sample size & statistical power solver (Power vs. *n* and Power vs. MDE curves), $\chi^2$ Goodness-of-Fit & interactive $R \times C$ Contingency Table (Cramér's *V* & adjusted standardized residuals), and One-Way ANOVA ($\eta^2$, $\omega^2$).
- **Workspace 3 — Empirical Data & MLE Fitter:** Paste raw numbers or load sample datasets for full descriptive stats, $1.5 \times \text{IQR}$ outlier flags, Histogram (Freedman–Diaconis / Sturges / Scott / manual) + Gaussian KDE, MLE distribution fitting ranked by AIC & Kolmogorov–Smirnov tests, and interactive Q-Q plots.
- **Workspace 4 — CLT & Discrete Joint Matrix:** Live Central Limit Theorem sampling simulator across 6 source populations (`n = 1..200`, `N = 100..50,000`) and an editable discrete $(X, Y)$ joint probability table with auto-normalize, SVG heatmap, marginal bar charts, conditionals, mutual information, Cov, and Corr.
- **Standalone-Domain Polish:** URL state persistence (`Copy Share Link`), live Python (`scipy.stats`) / R / LaTeX / `curl` snippet drawer, lossless `.svg` + 2× Retina `.png` + `.json` exports, keyboard shortcuts (`1`–`4`, `/`, `d`, `c`, `r`, `?`), 0xWulf Canonical Teal light/dark themes, and strict `Content-Security-Policy: default-src 'self'`.

## Architecture

```text
app/
├── api.py                 # FastAPI entrypoint, CSP middleware, System & v1 Legacy routes
├── api_v2.py              # /api/v2/* OpenAPI-documented workbench routes
├── dlbdss_core.py         # Preserved v1 probability & inequality functions
├── plotting.py            # Preserved v1 Matplotlib Agg PNG plotters
└── stats/
    ├── schemas.py         # Pydantic v2 models & finite-float validators
    ├── distributions.py   # 14-distribution sf/isf engine & catalog
    ├── inference.py       # Means, Proportions, Power, Chi-Squared & ANOVA
    ├── fitting.py         # Descriptives, KDE, MLE AIC/KS fitter & Q-Q coords
    ├── simulators.py      # CLT simulator & Joint (X, Y) matrix analyzer
    └── export_png.py      # Thread-safe 2x Retina Matplotlib PNG exporter
static/
├── index.html             # Zero-build workbench shell (strict CSP compliant)
├── favicon.svg            # Canonical 256×256 teal curve mark
├── css/workbench.css      # Monochrome Swiss grid + 0xWulf Teal tokens
└── js/                    # Native ES modules (state, api, chart, snippets, workspaces/*)
```

## API Quickstart (`https://p05.dev`)

Interactive OpenAPI docs live at `/docs` (`/openapi.json`).

```bash
# Health & metadata
curl -sS https://p05.dev/healthz
curl -sS https://p05.dev/about

# Evaluate Standard Normal α = 0.05 two-tailed region
curl -sS -X POST https://p05.dev/api/v2/dist/evaluate \
  -H "Content-Type: application/json" \
  -d '{"dist":"normal","params":{"mu":0,"sigma":1},"region":"two_tailed","a":-1.96,"b":1.96}'

# Two-proportion A/B power analysis
curl -sS -X POST https://p05.dev/api/v2/inference/power \
  -H "Content-Type: application/json" \
  -d '{"mode":"two_prop","solve_for":"sample_size","p1":0.12,"p2":0.16,"target_power":0.80}'
```

### Preserved v1 Legacy Compatibility
Every v1 endpoint (`/api/norm/*`, `/api/binom/*`, `/api/pois/*`, `/api/geom/*`, `/api/exp/*`, `/api/unif/*`, `/api/clt`, `/api/ineq/*`, `/api/joint`, `/plot/png/*`, and `/plot/{pdf,pmf,cdf,sim,clt,heat}/*`) remains 100% backwards-compatible under the `v1 Legacy` OpenAPI tag.

## Local Development & Testing

```bash
bash scripts/install.sh
.venv/bin/pip install --upgrade-strategy only-if-needed -r requirements-dev.txt
bash scripts/run-dev.sh   # binds 127.0.0.1:5009
```

Run lint and full verification suite:

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest -v
```
