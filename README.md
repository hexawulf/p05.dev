# probplots-web

Self-hosted FastAPI calculator and headless plotting web app for probability and statistics (DLBDSS course helper, paired with [hexawulf/probplots](https://github.com/hexawulf/probplots)).

## Features

- **Distributions:** Normal (PDF, CDF, interval, inverse quantile, Z-score), Binomial (PMF, CDF, at-most, at-least, between), Poisson (PMF, CDF, at-least, between), Geometric (0-indexed failures before 1st success: PMF & CDF), Exponential (PDF, CDF, survival, inverse), and Continuous Uniform (PDF, CDF).
- **CLT & Probability Bounds:** Central Limit Theorem interval calculator for sample means (`X̄ ~ N(μ, σ²/n)`) plus Markov and Chebyshev inequality bounds.
- **Interactive Discrete Joint Distribution `(X, Y)`:** Editable contingency table synced with `x,y,p;...` pairs, live `Σp` indicator with one-click Normalize, marginals, conditionals `P(X|Y)` & `P(Y|X)`, independence test, `E`, `Var`, `Cov`, `Corr`, and annotated heatmap PNG.
- **Headless Server-Side PNG Plots:** Thread-safe Matplotlib Agg figures styled in the 0xWulf teal palette (`light` and `dark` themes) with shaded regions, highlighted discrete bars, Monte Carlo simulations, and PNG downloads.
- **Self-Hosted Zero-CDN UI:** Responsive Light/Dark UI with strict `Content-Security-Policy: default-src 'self'`, precision selector (`2 / 4 / 6 / Full` d.p.), worked examples, and Casio FX-991EX keystroke cross-checks.

## API Endpoints (GET)

### System
- `GET /`, `HEAD /` — Web UI
- `GET /healthz`, `HEAD /healthz` — Health check (`{"status": "ok"}`)
- `GET /about` — App metadata & version
- `GET /docs` — OpenAPI / Swagger UI

### Numeric Calculations
- **Normal:** `/api/norm/pdf?x&mu&sigma`, `/api/norm/cdf?x&mu&sigma`, `/api/norm/interval?lower&upper&mu&sigma`, `/api/norm/inv?p&mu&sigma`
- **Binomial:** `/api/binom/pmf?n&p&k`, `/api/binom/cdf?n&p&k`, `/api/binom/cdf-range?n&p&kmin&kmax`, `/api/binom/atmost?n&p&k`, `/api/binom/atleast?n&p&k`, `/api/binom/between?n&p&kmin&kmax`
- **Poisson:** `/api/pois/pmf?lam&k`, `/api/pois/cdf?lam&k`, `/api/pois/atleast?lam&k`, `/api/pois/between?lam&kmin&kmax`
- **Geometric (0-indexed failures):** `/api/geom/pmf?p&k`, `/api/geom/cdf?p&k`
- **Exponential:** `/api/exp/pdf?lam&x`, `/api/exp/cdf?lam&x`, `/api/exp/inv?lam&p`
- **Uniform:** `/api/unif/pdf?a&b&x`, `/api/unif/cdf?a&b&x`
- **CLT & Inequalities:** `/api/clt?mu&sigma&n&lower&upper`, `/api/ineq/markov?mean&t`, `/api/ineq/chebyshev?sigma&t`
- **Joint (discrete):** `/api/joint?pairs=0,0,0.1;0,1,0.2;1,0,0.3;1,1,0.4` (`p >= 0`, `Σp = 1 ± 1e-10`; returns `support_X`, `support_Y`, `joint`, `marginal_X`, `marginal_Y`, `conditionals`, `independent`, `E`, `Var`, `Cov`, `Corr`)

### PNG Plots (optional `theme=light|dark`)
- `/plot/png/normal?mu&sigma&shade_low&shade_high` (alias `/plot/pdf/normal`)
- `/plot/png/binomial_pmf?n&p&highlight_k&highlight_min&highlight_max` (alias `/plot/pmf/binom`)
- `/plot/png/binomial_cdf?n&p&highlight_k` (alias `/plot/cdf/binom`)
- `/plot/png/binomial_sim?n&N&p&bins` (alias `/plot/sim/binom`)
- `/plot/png/poisson_pmf?lam&kmax&highlight_k&highlight_min&highlight_max` (alias `/plot/pmf/poisson`)
- `/plot/png/poisson_cdf?lam&kmax&highlight_k`
- `/plot/png/poisson_sim?n&lam&bins` (alias `/plot/sim/poisson`)
- `/plot/png/geometric_pmf?p&kmax&highlight_k`
- `/plot/png/exponential_pdf?lam&xmax&highlight_x`
- `/plot/png/exponential_cdf?lam&xmax&highlight_x`
- `/plot/png/uniform_pdf?a&b&highlight_x`
- `/plot/png/uniform_cdf?a&b&highlight_x`
- `/plot/png/clt?mu&sigma&n&lower&upper` (alias `/plot/clt`)
- `/plot/png/joint_discrete?pairs=...` (alias `/plot/heat/joint`)

## Local Development & Testing

```bash
bash scripts/install.sh
bash scripts/run-dev.sh  # binds 127.0.0.1:5009
```

For environments without the sibling `probplots` helper repo, set `PROBPLOTS_STUB=1` (or point `PROBPLOTS_HELPER_DIR` to your `probplots` checkout).

```bash
# Lint & tests (install pytest, httpx, ruff into .venv)
.venv/bin/ruff check app tests
.venv/bin/pytest
```
