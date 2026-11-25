"""FastAPI application for p05.dev (probplots-web v2 + backwards-compatible v1 routes)."""

import math
import os
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api_v2 import router as api_v2_router
from .dlbdss_core import (
    binom_atleast,
    binom_atmost,
    binom_between,
    binom_cdf,
    binom_cdf_range,
    binom_pmf,
    chebyshev_bound,
    clt,
    exp_cdf,
    exp_inv,
    exp_pdf,
    geom_cdf,
    geom_pmf,
    markov_bound,
    norm_cdf,
    norm_interval,
    norm_inv,
    norm_pdf,
    pois_atleast,
    pois_between,
    pois_cdf,
    pois_pmf,
    unif_cdf,
    unif_pdf,
)
from .plotting import (
    plot_cdf_binom,
    plot_clt,
    plot_exponential_cdf,
    plot_exponential_pdf,
    plot_geometric_pmf,
    plot_heat_joint,
    plot_normal_pdf,
    plot_pmf_binom,
    plot_pmf_poisson,
    plot_poisson_cdf,
    plot_sim_binom,
    plot_sim_poisson,
    plot_uniform_cdf,
    plot_uniform_pdf,
)

APP_VERSION = "1.0.0"
REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"
INDEX_HTML = STATIC_DIR / "index.html"

ThemeName = Literal["light", "dark"]

OPENAPI_TAGS = [
    {"name": "v2 Distributions", "description": "14 continuous & discrete distributions, sf/isf tails, quantiles & overlays."},
    {"name": "v2 Hypothesis Tests", "description": "z/t/Welch means, Wilson proportions, power/sample size, chi-squared & ANOVA."},
    {"name": "v2 Data & Fitting", "description": "Empirical descriptives, Hist+KDE, MLE fitting (AIC/KS) & Q-Q plots."},
    {"name": "v2 Simulators", "description": "CLT sampling distribution lab & discrete joint (X, Y) matrix analyzer."},
    {"name": "v1 Legacy", "description": "100% backwards-compatible probplots v1 /api/* & /plot/* routes."},
    {"name": "System", "description": "Health, metadata, UI shell & high-res PNG export."},
]

# ===== Local helper import with configurable path + sandbox stub =====
_helper_candidates = [
    os.environ.get("PROBPLOTS_HELPER_DIR"),
    str(REPO_ROOT.parent / "probplots"),
    "/home/zk/projects/probplots",
]
for _cand in _helper_candidates:
    if _cand and Path(_cand).is_dir() and _cand not in sys.path:
        sys.path.insert(0, _cand)

_stats_helper_error: Exception | None = None
try:
    from stats_helper import compute_joint_stats  # type: ignore[import-not-found]
except ImportError as _exc:
    _stats_helper_error = _exc

    def compute_joint_stats(joint: dict[tuple[float, float], float]) -> dict:
        if os.environ.get("PROBPLOTS_STUB") == "1":
            xs = sorted({x for (x, _) in joint})
            ys = sorted({y for (_, y) in joint})
            return {
                "support_X": xs,
                "support_Y": ys,
                "joint": [{"x": x, "y": y, "p": p} for (x, y), p in sorted(joint.items())],
                "marginal_X": {},
                "marginal_Y": {},
                "independent": False,
                "E": {"EX": 0.0, "EY": 0.0},
                "Var": {"VarX": 0.0, "VarY": 0.0},
                "Cov": 0.0,
                "Corr": None,
                "stub": True,
            }
        raise RuntimeError(
            "stats_helper package not available; install probplots or set PROBPLOTS_STUB=1"
        ) from _stats_helper_error


app = FastAPI(
    title="p05.dev — Interactive Probability & Statistics Workbench",
    description=(
        "Self-hosted statistical computing workbench backed by SciPy & NumPy "
        "(formerly probplots-web; 100% backwards-compatible with v1 /api/* and /plot/* routes). "
        "Canonical domain: https://p05.dev · Source: https://github.com/hexawulf/p05.dev"
    ),
    contact={
        "name": "Erling Wulf Weinreich (0xWulf)",
        "url": "https://0xwulf.dev",
        "email": "dev@0xwulf.dev",
    },
    version=APP_VERSION,
    openapi_tags=OPENAPI_TAGS,
)
app.include_router(api_v2_router)
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path == "/":
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; "
            "connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
    return response


def _bad(exc: Exception) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _parse_joint_pairs(pairs: str) -> dict[tuple[float, float], float]:
    items = [t.strip() for t in pairs.strip().split(";") if t.strip()]
    if not items:
        raise ValueError("pairs must contain at least one x,y,p triple")
    joint: dict[tuple[float, float], float] = {}
    total = 0.0
    for item in items:
        parts = [part.strip() for part in item.split(",")]
        if len(parts) != 3:
            raise ValueError(f"invalid triple '{item}' — expected 'x,y,p'")
        x, y, p = float(parts[0]), float(parts[1]), float(parts[2])
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(p)):
            raise ValueError("x, y, and p must be finite numbers")
        if p < 0.0:
            raise ValueError("probabilities must be >= 0")
        joint[(x, y)] = joint.get((x, y), 0.0) + p
        total += p
    if abs(total - 1.0) > 1e-10:
        raise ValueError(f"probabilities must sum to 1 (got {total:.12g})")
    return joint


def _compute_conditionals(
    joint: dict[tuple[float, float], float],
    xs: list[float],
    ys: list[float],
    marginal_x: dict,
    marginal_y: dict,
) -> dict[str, dict[str, dict[str, float]]]:
    x_given_y: dict[str, dict[str, float]] = {}
    for y in ys:
        py = float(marginal_y.get(y, marginal_y.get(str(y), 0.0)))
        if py > 1e-12:
            x_given_y[f"{y:g}"] = {f"{x:g}": joint.get((x, y), 0.0) / py for x in xs}
    y_given_x: dict[str, dict[str, float]] = {}
    for x in xs:
        px = float(marginal_x.get(x, marginal_x.get(str(x), 0.0)))
        if px > 1e-12:
            y_given_x[f"{x:g}"] = {f"{y:g}": joint.get((x, y), 0.0) / px for y in ys}
    return {"X_given_Y": x_given_y, "Y_given_X": y_given_x}


@app.get("/about", tags=["System"])
def about(request: Request):
    return {
        "app": "p05.dev",
        "legacy_app": "probplots-web",
        "version": APP_VERSION,
        "repo": "https://github.com/hexawulf/p05.dev",
        "bind": "127.0.0.1:5009",
        "base_url": str(request.base_url).rstrip("/"),
    }


@app.api_route("/healthz", methods=["GET", "HEAD"], tags=["System"])
def healthz():
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon_redirect():
    return RedirectResponse(url="/static/favicon.svg", status_code=302)


# ---- Normal endpoints ----


@app.get("/api/norm/pdf", tags=["v1 Legacy"])
def api_norm_pdf(x: float, mu: float = 0.0, sigma: float = 1.0):
    try:
        return {"value": norm_pdf(x, mu, sigma)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/norm/cdf", tags=["v1 Legacy"])
def api_norm_cdf(x: float, mu: float = 0.0, sigma: float = 1.0):
    try:
        return {"value": norm_cdf(x, mu, sigma)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/norm/interval", tags=["v1 Legacy"])
def api_norm_interval(lower: float, upper: float, mu: float = 0.0, sigma: float = 1.0):
    try:
        return {"value": norm_interval(lower, upper, mu, sigma)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/norm/inv", tags=["v1 Legacy"])
def api_norm_inv(p: float, mu: float = 0.0, sigma: float = 1.0):
    try:
        return {"value": norm_inv(p, mu, sigma)}
    except ValueError as exc:
        _bad(exc)


# ---- Binomial endpoints ----


@app.get("/api/binom/pmf", tags=["v1 Legacy"])
def api_binom_pmf(n: int, p: float, k: int):
    try:
        return {"value": binom_pmf(n, p, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/binom/cdf", tags=["v1 Legacy"])
def api_binom_cdf(n: int, p: float, k: int):
    try:
        return {"value": binom_cdf(n, p, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/binom/cdf-range", tags=["v1 Legacy"])
def api_binom_cdf_range(n: int, p: float, kmin: int, kmax: int):
    try:
        return {"value": binom_cdf_range(n, p, kmin, kmax)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/binom/atmost", tags=["v1 Legacy"])
def api_binom_atmost(
    n: int = Query(..., ge=0),
    p: float = Query(..., description="0 <= p <= 1"),
    k: int = Query(..., ge=0),
):
    try:
        return {"value": binom_atmost(n, p, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/binom/atleast", tags=["v1 Legacy"])
def api_binom_atleast(
    n: int = Query(..., ge=0),
    p: float = Query(..., description="0 <= p <= 1"),
    k: int = Query(..., ge=0),
):
    try:
        return {"value": binom_atleast(n, p, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/binom/between", tags=["v1 Legacy"])
def api_binom_between(
    n: int = Query(..., ge=0),
    p: float = Query(..., description="0 <= p <= 1"),
    kmin: int = Query(..., ge=0),
    kmax: int = Query(..., ge=0),
):
    try:
        return {"value": binom_between(n, p, kmin, kmax)}
    except ValueError as exc:
        _bad(exc)


# ---- Poisson endpoints ----


@app.get("/api/pois/pmf", tags=["v1 Legacy"])
def api_pois_pmf(
    lam: float = Query(..., description="lambda > 0"),
    k: int = Query(..., ge=0, description="k >= 0"),
):
    try:
        return {"value": pois_pmf(lam, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/pois/cdf", tags=["v1 Legacy"])
def api_pois_cdf(lam: float, k: int):
    try:
        return {"value": pois_cdf(lam, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/pois/atleast", tags=["v1 Legacy"])
def api_pois_atleast(lam: float, k: int):
    try:
        return {"value": pois_atleast(lam, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/pois/between", tags=["v1 Legacy"])
def api_pois_between(lam: float, kmin: int, kmax: int):
    try:
        return {"value": pois_between(lam, kmin, kmax)}
    except ValueError as exc:
        _bad(exc)


# ---- Geometric / Exponential / Uniform endpoints ----


@app.get("/api/geom/pmf", tags=["v1 Legacy"])
def api_geom_pmf(p: float, k: int):
    try:
        return {"value": geom_pmf(p, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/geom/cdf", tags=["v1 Legacy"])
def api_geom_cdf(p: float, k: int):
    try:
        return {"value": geom_cdf(p, k)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/exp/pdf", tags=["v1 Legacy"])
def api_exp_pdf(lam: float, x: float):
    try:
        return {"value": exp_pdf(lam, x)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/exp/cdf", tags=["v1 Legacy"])
def api_exp_cdf(lam: float, x: float):
    try:
        return {"value": exp_cdf(lam, x)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/exp/inv", tags=["v1 Legacy"])
def api_exp_inv(lam: float, p: float):
    try:
        return {"value": exp_inv(lam, p)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/unif/pdf", tags=["v1 Legacy"])
def api_unif_pdf(a: float, b: float, x: float):
    try:
        return {"value": unif_pdf(a, b, x)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/unif/cdf", tags=["v1 Legacy"])
def api_unif_cdf(a: float, b: float, x: float):
    try:
        return {"value": unif_cdf(a, b, x)}
    except ValueError as exc:
        _bad(exc)


# ---- CLT & Inequalities ----


@app.get("/api/clt", tags=["v1 Legacy"])
def api_clt(mu: float, sigma: float, n: int, lower: float, upper: float):
    try:
        return {"value": clt(mu, sigma, n, lower, upper)}
    except ValueError as exc:
        _bad(exc)


@app.get("/api/ineq/markov", tags=["v1 Legacy"])
def api_markov(mean: float, t: float):
    try:
        return markov_bound(mean, t)
    except ValueError as exc:
        _bad(exc)


@app.get("/api/ineq/chebyshev", tags=["v1 Legacy"])
def api_chebyshev(sigma: float, t: float):
    try:
        return chebyshev_bound(sigma, t)
    except ValueError as exc:
        _bad(exc)


# ---- Joint endpoint ----


@app.get("/api/joint", tags=["v1 Legacy"])
def api_joint(pairs: str = Query(..., description="semicolon-separated triples x,y,p (e.g. '0,0,0.1;1,1,0.4')")):
    try:
        joint = _parse_joint_pairs(pairs)
        data = dict(compute_joint_stats(joint))
        if data.get("marginal_X") and data.get("marginal_Y"):
            data["conditionals"] = _compute_conditionals(
                joint,
                data.get("support_X", []),
                data.get("support_Y", []),
                data["marginal_X"],
                data["marginal_Y"],
            )
        return JSONResponse(data)
    except (ValueError, RuntimeError) as exc:
        _bad(exc)


# ---- Legacy + universal PNG plotting endpoints ----


def _png_response(data: bytes) -> Response:
    return Response(content=data, media_type="image/png")


@app.get("/plot/pdf/normal", tags=["v1 Legacy"])
@app.get("/plot/png/normal", tags=["v1 Legacy"])
def http_plot_normal(
    mu: float = 0.0,
    sigma: float = 1.0,
    shade_low: float | None = None,
    shade_high: float | None = None,
    theme: ThemeName = "light",
):
    try:
        return _png_response(
            plot_normal_pdf(mu, sigma, shade_low=shade_low, shade_high=shade_high, theme=theme)
        )
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/sim/poisson", tags=["v1 Legacy"])
@app.get("/plot/png/poisson_sim", tags=["v1 Legacy"])
def http_plot_sim_pois(n: int = 50000, lam: float = 3.0, bins: int = 50, theme: ThemeName = "light"):
    try:
        return _png_response(plot_sim_poisson(n, lam, bins=bins, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/sim/binom", tags=["v1 Legacy"])
@app.get("/plot/png/binomial_sim", tags=["v1 Legacy"])
def http_plot_sim_binom(
    n: int = 50000, N: int = 20, p: float = 0.3, bins: int = 50, theme: ThemeName = "light"
):
    try:
        return _png_response(plot_sim_binom(n, N, p, bins=bins, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/pmf/poisson", tags=["v1 Legacy"])
@app.get("/plot/png/poisson_pmf", tags=["v1 Legacy"])
def http_plot_pmf_poisson(
    lam: float = Query(..., gt=0),
    kmax: int | None = Query(None, ge=0),
    highlight_k: int | None = Query(None, ge=0),
    highlight_min: int | None = Query(None, ge=0),
    highlight_max: int | None = Query(None, ge=0),
    theme: ThemeName = "light",
):
    try:
        return _png_response(
            plot_pmf_poisson(
                lam,
                kmax,
                highlight_k=highlight_k,
                highlight_min=highlight_min,
                highlight_max=highlight_max,
                theme=theme,
            )
        )
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/png/poisson_cdf", tags=["v1 Legacy"])
def http_plot_cdf_poisson(
    lam: float = Query(..., gt=0),
    kmax: int | None = Query(None, ge=0),
    highlight_k: int | None = Query(None, ge=0),
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_poisson_cdf(lam, kmax, highlight_k=highlight_k, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/pmf/binom", tags=["v1 Legacy"])
@app.get("/plot/png/binomial_pmf", tags=["v1 Legacy"])
def http_plot_pmf_binom(
    n: int = Query(..., ge=0),
    p: float = Query(..., ge=0, le=1),
    highlight_k: int | None = Query(None, ge=0),
    highlight_min: int | None = Query(None, ge=0),
    highlight_max: int | None = Query(None, ge=0),
    theme: ThemeName = "light",
):
    try:
        return _png_response(
            plot_pmf_binom(
                n,
                p,
                highlight_k=highlight_k,
                highlight_min=highlight_min,
                highlight_max=highlight_max,
                theme=theme,
            )
        )
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/cdf/binom", tags=["v1 Legacy"])
@app.get("/plot/png/binomial_cdf", tags=["v1 Legacy"])
def http_plot_cdf_binom(
    n: int = Query(..., ge=0),
    p: float = Query(..., ge=0, le=1),
    highlight_k: int | None = Query(None, ge=0),
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_cdf_binom(n, p, highlight_k=highlight_k, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/png/geometric_pmf", tags=["v1 Legacy"])
def http_plot_geometric_pmf(
    p: float = Query(..., gt=0, le=1),
    kmax: int = Query(20, ge=0),
    highlight_k: int | None = Query(None, ge=0),
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_geometric_pmf(p, kmax, highlight_k=highlight_k, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/png/exponential_pdf", tags=["v1 Legacy"])
def http_plot_exponential_pdf(
    lam: float = Query(..., gt=0),
    xmax: float | None = None,
    highlight_x: float | None = None,
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_exponential_pdf(lam, xmax, highlight_x=highlight_x, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/png/exponential_cdf", tags=["v1 Legacy"])
def http_plot_exponential_cdf(
    lam: float = Query(..., gt=0),
    xmax: float | None = None,
    highlight_x: float | None = None,
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_exponential_cdf(lam, xmax, highlight_x=highlight_x, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/png/uniform_pdf", tags=["v1 Legacy"])
def http_plot_uniform_pdf(
    a: float = 0.0,
    b: float = 10.0,
    highlight_x: float | None = None,
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_uniform_pdf(a, b, highlight_x=highlight_x, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/png/uniform_cdf", tags=["v1 Legacy"])
def http_plot_uniform_cdf(
    a: float = 0.0,
    b: float = 10.0,
    highlight_x: float | None = None,
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_uniform_cdf(a, b, highlight_x=highlight_x, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/clt", tags=["v1 Legacy"])
@app.get("/plot/png/clt", tags=["v1 Legacy"])
def http_plot_clt(
    mu: float,
    sigma: float,
    n: int,
    lower: float,
    upper: float,
    theme: ThemeName = "light",
):
    try:
        return _png_response(plot_clt(mu, sigma, n, lower, upper, theme=theme))
    except ValueError as exc:
        _bad(exc)


@app.get("/plot/heat/joint", tags=["v1 Legacy"])
@app.get("/plot/png/joint_discrete", tags=["v1 Legacy"])
def http_plot_heat_joint(
    pairs: str = Query(..., description="x,y,p;..."),
    theme: ThemeName = "light",
):
    try:
        joint = _parse_joint_pairs(pairs)
        return _png_response(plot_heat_joint(joint, theme=theme))
    except ValueError as exc:
        _bad(exc)


# ---- root serves static index ----


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse, tags=["System"])
def root():
    return INDEX_HTML.read_text(encoding="utf-8")
