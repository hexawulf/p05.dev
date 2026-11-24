"""Thread-safe headless PNG plot generators using the 0xWulf teal palette."""

import io
import math

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from scipy import stats
from scipy.stats import binom, expon, norm, poisson

MAX_SIM_N = 200_000
MAX_DISCRETE_N = 2_000
MAX_KMAX = 2_000
MAX_BINS = 200

_THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#ffffff",
        "axes_bg": "#f8fafc",
        "fg": "#0f172a",
        "muted": "#475569",
        "grid": "#cbd5e1",
        "spine": "#cbd5e1",
        "accent": "#0f766e",
        "accent_soft": "#14b8a6",
        "accent_fill": "#14b8a6",
        "bar_muted": "#94a3b8",
        "hist_fill": "#99f6e4",
        "hist_edge": "#0d9488",
        "marker": "#0d9488",
        "ref_line": "#64748b",
    },
    "dark": {
        "bg": "#1e293b",
        "axes_bg": "#0f172a",
        "fg": "#f8fafc",
        "muted": "#94a3b8",
        "grid": "#334155",
        "spine": "#475569",
        "accent": "#2dd4bf",
        "accent_soft": "#5eead4",
        "accent_fill": "#14b8a6",
        "bar_muted": "#475569",
        "hist_fill": "#134e4a",
        "hist_edge": "#2dd4bf",
        "marker": "#5eead4",
        "ref_line": "#94a3b8",
    },
}

_CMAP_LIGHT = LinearSegmentedColormap.from_list(
    "wulf_teal_light", ["#f0fdfa", "#99f6e4", "#2dd4bf", "#0d9488", "#115e59"]
)
_CMAP_DARK = LinearSegmentedColormap.from_list(
    "wulf_teal_dark", ["#0f172a", "#134e4a", "#0d9488", "#2dd4bf", "#99f6e4"]
)


def _palette(theme: str) -> dict[str, str]:
    return _THEMES["dark"] if theme == "dark" else _THEMES["light"]


def _chk(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _chk_finite(val: float, name: str) -> None:
    _chk(math.isfinite(val), f"{name} must be finite")


def _new_figure(figsize: tuple[float, float], theme: str):
    pal = _palette(theme)
    fig = Figure(figsize=figsize, dpi=140, facecolor=pal["bg"])
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_facecolor(pal["axes_bg"])
    ax.tick_params(colors=pal["muted"], labelsize=9)
    ax.xaxis.label.set_color(pal["muted"])
    ax.yaxis.label.set_color(pal["muted"])
    ax.title.set_color(pal["fg"])
    ax.title.set_fontsize(11)
    ax.title.set_fontweight("bold")
    for spine in ax.spines.values():
        spine.set_color(pal["spine"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color=pal["grid"], alpha=0.55, linewidth=0.7)
    ax.set_axisbelow(True)
    return fig, ax, pal


def _png_bytes(fig: Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=140, facecolor=fig.get_facecolor())
    return buf.getvalue()


def plot_normal_pdf(
    mu: float,
    sigma: float,
    w: int = 960,
    h: int = 480,
    shade_low: float | None = None,
    shade_high: float | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(mu, "mu")
    _chk_finite(sigma, "sigma")
    _chk(sigma > 0.0, "sigma must be > 0")
    x_min = mu - 4.0 * sigma
    x_max = mu + 4.0 * sigma
    if shade_low is not None and math.isfinite(shade_low):
        x_min = min(x_min, shade_low - 0.5 * sigma)
    if shade_high is not None and math.isfinite(shade_high):
        x_max = max(x_max, shade_high + 0.5 * sigma)

    x = np.linspace(x_min, x_max, 500)
    y = stats.norm.pdf(x, loc=mu, scale=sigma)
    fig, ax, pal = _new_figure((w / 140, h / 140), theme)
    ax.plot(x, y, linewidth=2.2, color=pal["accent"])
    ax.axvline(mu, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.75)

    if shade_low is not None or shade_high is not None:
        lo = x_min if shade_low is None else shade_low
        hi = x_max if shade_high is None else shade_high
        if lo > hi:
            lo, hi = hi, lo
        mask = (x >= lo) & (x <= hi)
        if np.any(mask):
            ax.fill_between(x[mask], 0, y[mask], color=pal["accent_fill"], alpha=0.28)
        cdf_hi = 1.0 if shade_high is None else float(norm.cdf(hi, loc=mu, scale=sigma))
        cdf_lo = 0.0 if shade_low is None else float(norm.cdf(lo, loc=mu, scale=sigma))
        area = max(0.0, cdf_hi - cdf_lo)
        ax.set_title(f"N(μ={mu:g}, σ={sigma:g}) PDF · Shaded area ≈ {area:.4f}")
    else:
        ax.fill_between(x, 0, y, color=pal["accent_fill"], alpha=0.10)
        ax.set_title(f"N(μ={mu:g}, σ={sigma:g}) PDF")

    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    ax.set_ylim(bottom=0)
    return _png_bytes(fig)


def plot_sim_poisson(
    n: int,
    lam: float,
    bins: int = 50,
    w: int = 960,
    h: int = 480,
    theme: str = "light",
) -> bytes:
    _chk(isinstance(n, int) and 1 <= n <= MAX_SIM_N, f"n must be integer in [1, {MAX_SIM_N}]")
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(isinstance(bins, int) and 1 <= bins <= MAX_BINS, f"bins must be integer in [1, {MAX_BINS}]")

    rng = np.random.default_rng()
    data = rng.poisson(lam, size=n)
    max_k = max(10, int(data.max()))
    fig, ax, pal = _new_figure((w / 140, h / 140), theme)
    if max_k <= 60:
        edges = np.arange(-0.5, max_k + 1.5, 1.0)
        ax.hist(data, bins=edges, density=True, color=pal["hist_fill"], edgecolor=pal["hist_edge"], alpha=0.8, label="Simulated")
    else:
        ax.hist(data, bins=bins, density=True, color=pal["hist_fill"], edgecolor=pal["hist_edge"], alpha=0.8, label="Simulated")

    xs = np.arange(0, max_k + 1)
    ax.plot(xs, stats.poisson.pmf(xs, lam), "o-", linewidth=2.0, markersize=4, color=pal["accent"], label="Exact PMF")
    ax.set_title(f"Poisson(λ={lam:g}) simulation (n={n:,})")
    ax.set_xlabel("k")
    ax.set_ylabel("Probability / Density")
    ax.legend(frameon=False, labelcolor=pal["fg"], fontsize=9)
    return _png_bytes(fig)


def plot_sim_binom(
    n: int,
    N: int,
    p: float,
    bins: int = 50,
    w: int = 960,
    h: int = 480,
    theme: str = "light",
) -> bytes:
    _chk(isinstance(n, int) and 1 <= n <= MAX_SIM_N, f"n must be integer in [1, {MAX_SIM_N}]")
    _chk(isinstance(N, int) and 0 <= N <= MAX_DISCRETE_N, f"N must be integer in [0, {MAX_DISCRETE_N}]")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    _chk(isinstance(bins, int) and 1 <= bins <= MAX_BINS, f"bins must be integer in [1, {MAX_BINS}]")

    rng = np.random.default_rng()
    data = rng.binomial(N, p, size=n)
    fig, ax, pal = _new_figure((w / 140, h / 140), theme)
    if N <= 60:
        edges = np.arange(-0.5, N + 1.5, 1.0)
        ax.hist(data, bins=edges, density=True, color=pal["hist_fill"], edgecolor=pal["hist_edge"], alpha=0.8, label="Simulated")
    else:
        ax.hist(data, bins=bins, density=True, color=pal["hist_fill"], edgecolor=pal["hist_edge"], alpha=0.8, label="Simulated")

    xs = np.arange(0, N + 1)
    ax.plot(xs, stats.binom.pmf(xs, N, p), "o-", linewidth=2.0, markersize=4, color=pal["accent"], label="Exact PMF")
    ax.set_title(f"Binomial(N={N}, p={p:g}) simulation (n={n:,})")
    ax.set_xlabel("k")
    ax.set_ylabel("Probability / Density")
    ax.legend(frameon=False, labelcolor=pal["fg"], fontsize=9)
    return _png_bytes(fig)


def _plot_discrete_bars(
    ks: np.ndarray,
    vals: np.ndarray,
    title: str,
    xlabel: str,
    ylabel: str,
    theme: str,
    highlight_k: int | None = None,
    highlight_min: int | None = None,
    highlight_max: int | None = None,
) -> bytes:
    fig, ax, pal = _new_figure((6.4, 3.3), theme)
    has_hl = highlight_k is not None or (highlight_min is not None and highlight_max is not None)
    if len(ks) <= 60:
        colors = []
        for k in ks:
            if not has_hl:
                colors.append(pal["accent"])
            elif highlight_k is not None and int(k) == highlight_k:
                colors.append(pal["accent"])
            elif highlight_min is not None and highlight_max is not None and highlight_min <= int(k) <= highlight_max:
                colors.append(pal["accent"])
            else:
                colors.append(pal["bar_muted"])
        ax.bar(ks, vals, width=0.72, color=colors, edgecolor="none", alpha=0.92)
    else:
        ax.plot(ks, vals, linewidth=1.8, color=pal["accent"])
        ax.fill_between(ks, 0, vals, color=pal["accent_fill"], alpha=0.18)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    return _png_bytes(fig)


def plot_pmf_poisson(
    lam: float,
    kmax: int | None = None,
    highlight_k: int | None = None,
    highlight_min: int | None = None,
    highlight_max: int | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    if kmax is None:
        kmax = int(max(10, min(MAX_KMAX, math.ceil(lam + 4.0 * math.sqrt(lam)))))
    else:
        _chk(isinstance(kmax, int) and 0 <= kmax <= MAX_KMAX, f"kmax must be integer in [0, {MAX_KMAX}]")
    ks = np.arange(0, kmax + 1)
    pmf = poisson.pmf(ks, lam)
    return _plot_discrete_bars(
        ks,
        pmf,
        title=f"Poisson PMF (λ={lam:g})",
        xlabel="k",
        ylabel="P(X = k)",
        theme=theme,
        highlight_k=highlight_k,
        highlight_min=highlight_min,
        highlight_max=highlight_max,
    )


def plot_poisson_cdf(
    lam: float,
    kmax: int | None = None,
    highlight_k: int | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    if kmax is None:
        kmax = int(max(10, min(MAX_KMAX, math.ceil(lam + 4.0 * math.sqrt(lam)))))
    else:
        _chk(isinstance(kmax, int) and 0 <= kmax <= MAX_KMAX, f"kmax must be integer in [0, {MAX_KMAX}]")
    ks = np.arange(0, kmax + 1)
    cdf = poisson.cdf(ks, lam)

    fig, ax, pal = _new_figure((6.4, 3.3), theme)
    ax.step(ks, cdf, where="post", linewidth=2.0, color=pal["accent"])
    if highlight_k is not None and 0 <= highlight_k <= kmax:
        val = float(poisson.cdf(highlight_k, lam))
        ax.plot([highlight_k], [val], "o", color=pal["marker"], markersize=7, zorder=5)
        ax.axvline(highlight_k, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.7)
    ax.set_title(f"Poisson CDF (λ={lam:g})")
    ax.set_xlabel("k")
    ax.set_ylabel("P(X ≤ k)")
    ax.set_ylim(-0.02, 1.04)
    return _png_bytes(fig)


def plot_pmf_binom(
    n: int,
    p: float,
    highlight_k: int | None = None,
    highlight_min: int | None = None,
    highlight_max: int | None = None,
    theme: str = "light",
) -> bytes:
    _chk(isinstance(n, int) and 0 <= n <= MAX_DISCRETE_N, f"n must be integer in [0, {MAX_DISCRETE_N}]")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    ks = np.arange(0, n + 1)
    pmf = binom.pmf(ks, n, p)
    return _plot_discrete_bars(
        ks,
        pmf,
        title=f"Binomial PMF (n={n}, p={p:g})",
        xlabel="k",
        ylabel="P(X = k)",
        theme=theme,
        highlight_k=highlight_k,
        highlight_min=highlight_min,
        highlight_max=highlight_max,
    )


def plot_cdf_binom(
    n: int,
    p: float,
    highlight_k: int | None = None,
    theme: str = "light",
) -> bytes:
    _chk(isinstance(n, int) and 0 <= n <= MAX_DISCRETE_N, f"n must be integer in [0, {MAX_DISCRETE_N}]")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    ks = np.arange(0, n + 1)
    cdf = binom.cdf(ks, n, p)

    fig, ax, pal = _new_figure((6.4, 3.3), theme)
    ax.step(ks, cdf, where="post", linewidth=2.0, color=pal["accent"])
    if highlight_k is not None and 0 <= highlight_k <= n:
        val = float(binom.cdf(highlight_k, n, p))
        ax.plot([highlight_k], [val], "o", color=pal["marker"], markersize=7, zorder=5)
        ax.axvline(highlight_k, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.7)
    ax.set_title(f"Binomial CDF (n={n}, p={p:g})")
    ax.set_xlabel("k")
    ax.set_ylabel("P(X ≤ k)")
    ax.set_ylim(-0.02, 1.04)
    return _png_bytes(fig)


def plot_heat_joint(pairs: dict[tuple[float, float], float], theme: str = "light") -> bytes:
    _chk(bool(pairs), "pairs must not be empty")
    xs = sorted({x for (x, _) in pairs})
    ys = sorted({y for (_, y) in pairs})
    x_idx = {x: i for i, x in enumerate(xs)}
    y_idx = {y: i for i, y in enumerate(ys)}
    mat = np.zeros((len(ys), len(xs)))
    for (x, y), p in pairs.items():
        _chk(p >= 0.0, "probabilities must be >= 0")
        mat[y_idx[y], x_idx[x]] += p

    fig, ax, pal = _new_figure((5.4, 4.2), theme)
    ax.grid(False)
    cmap = _CMAP_DARK if theme == "dark" else _CMAP_LIGHT
    vmin = 0.0
    vmax = float(mat.max()) if float(mat.max()) > 0 else 1.0
    im = ax.imshow(mat, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_title("Joint Distribution Heatmap  p(x, y)")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_xticks(range(len(xs)), [f"{v:g}" for v in xs])
    ax.set_yticks(range(len(ys)), [f"{v:g}" for v in ys])

    if len(xs) <= 10 and len(ys) <= 10:
        mid = vmax * 0.52
        for yi in range(len(ys)):
            for xi in range(len(xs)):
                val = mat[yi, xi]
                if theme == "dark":
                    txt_col = "#0f172a" if val >= mid else "#f8fafc"
                else:
                    txt_col = "#ffffff" if val >= mid else "#0f172a"
                ax.text(xi, yi, f"{val:.4g}", ha="center", va="center", color=txt_col, fontsize=10, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, shrink=0.85, label="p(x, y)")
    cbar.ax.yaxis.label.set_color(pal["muted"])
    cbar.ax.tick_params(colors=pal["muted"], labelsize=8)
    return _png_bytes(fig)


def plot_clt(
    mu: float,
    sigma: float,
    n: int,
    lower: float,
    upper: float,
    theme: str = "light",
) -> bytes:
    _chk_finite(mu, "mu")
    _chk_finite(sigma, "sigma")
    _chk_finite(lower, "lower")
    _chk_finite(upper, "upper")
    _chk(sigma > 0.0, "sigma must be > 0")
    _chk(isinstance(n, int) and n >= 1, "n must be integer >= 1")

    mu_bar = mu
    sigma_bar = sigma / math.sqrt(n)
    lo, hi = min(lower, upper), max(lower, upper)
    x_min = min(mu_bar - 4.0 * sigma_bar, lo - 0.5 * sigma_bar)
    x_max = max(mu_bar + 4.0 * sigma_bar, hi + 0.5 * sigma_bar)
    xs = np.linspace(x_min, x_max, 600)
    pdf = norm.pdf(xs, loc=mu_bar, scale=sigma_bar)
    prob = float(norm.cdf(hi, loc=mu_bar, scale=sigma_bar) - norm.cdf(lo, loc=mu_bar, scale=sigma_bar))

    fig, ax, pal = _new_figure((6.4, 3.5), theme)
    ax.plot(xs, pdf, linewidth=2.2, color=pal["accent"])
    ax.axvline(mu_bar, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.75)
    mask = (xs >= lo) & (xs <= hi)
    ax.fill_between(xs[mask], 0, pdf[mask], color=pal["accent_fill"], alpha=0.30)
    ax.set_title(f"CLT: X̄ ~ N(μ={mu_bar:g}, σ/√n={sigma_bar:.4g}) · P = {prob:.4f}")
    ax.set_xlabel("x̄")
    ax.set_ylabel("density")
    ax.set_ylim(bottom=0)
    return _png_bytes(fig)


def plot_geometric_pmf(
    p: float,
    kmax: int = 20,
    highlight_k: int | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(p, "p")
    _chk(0.0 < p <= 1.0, "p must be in (0,1]")
    _chk(isinstance(kmax, int) and 0 <= kmax <= MAX_KMAX, f"kmax must be integer in [0, {MAX_KMAX}]")
    ks = np.arange(0, kmax + 1)
    # 0-indexed support: k = failures before first success -> P(X=k) = (1-p)^k * p
    pmf = ((1.0 - p) ** ks) * p
    return _plot_discrete_bars(
        ks,
        pmf,
        title=f"Geometric PMF (p={p:g}, failures before 1st success)",
        xlabel="k (failures before first success)",
        ylabel="P(X = k)",
        theme=theme,
        highlight_k=highlight_k,
    )


def plot_exponential_pdf(
    lam: float,
    xmax: float | None = None,
    highlight_x: float | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    if xmax is None:
        xmax = max(5.0 / lam, (highlight_x * 1.4) if (highlight_x is not None and highlight_x > 0) else 0.0)
    else:
        _chk_finite(xmax, "xmax")
        _chk(xmax > 0.0, "xmax must be > 0")
    xs = np.linspace(0.0, xmax, 400)
    pdf = expon.pdf(xs, scale=1.0 / lam)

    fig, ax, pal = _new_figure((6.4, 3.3), theme)
    ax.plot(xs, pdf, linewidth=2.2, color=pal["accent"])
    if highlight_x is not None and math.isfinite(highlight_x) and highlight_x >= 0:
        mask = xs <= highlight_x
        ax.fill_between(xs[mask], 0, pdf[mask], color=pal["accent_fill"], alpha=0.28)
        ax.axvline(highlight_x, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.75)
    else:
        ax.fill_between(xs, 0, pdf, color=pal["accent_fill"], alpha=0.10)
    ax.set_title(f"Exponential PDF (λ={lam:g})")
    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    ax.set_ylim(bottom=0)
    return _png_bytes(fig)


def plot_exponential_cdf(
    lam: float,
    xmax: float | None = None,
    highlight_x: float | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    if xmax is None:
        xmax = max(5.0 / lam, (highlight_x * 1.4) if (highlight_x is not None and highlight_x > 0) else 0.0)
    else:
        _chk_finite(xmax, "xmax")
        _chk(xmax > 0.0, "xmax must be > 0")
    xs = np.linspace(0.0, xmax, 400)
    cdf = expon.cdf(xs, scale=1.0 / lam)

    fig, ax, pal = _new_figure((6.4, 3.3), theme)
    ax.plot(xs, cdf, linewidth=2.2, color=pal["accent"])
    if highlight_x is not None and math.isfinite(highlight_x) and highlight_x >= 0:
        val = float(expon.cdf(highlight_x, scale=1.0 / lam))
        ax.plot([highlight_x], [val], "o", color=pal["marker"], markersize=7, zorder=5)
        ax.axvline(highlight_x, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.75)
    ax.set_title(f"Exponential CDF (λ={lam:g})")
    ax.set_xlabel("x")
    ax.set_ylabel("F(x)")
    ax.set_ylim(-0.02, 1.04)
    return _png_bytes(fig)


def plot_uniform_pdf(
    a: float,
    b: float,
    highlight_x: float | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(a, "a")
    _chk_finite(b, "b")
    _chk(b > a, "require b > a")
    pad = (b - a) * 0.2
    xs = np.linspace(a - pad, b + pad, 500)
    ys = np.where((xs >= a) & (xs <= b), 1.0 / (b - a), 0.0)

    fig, ax, pal = _new_figure((6.4, 3.3), theme)
    ax.plot(xs, ys, linewidth=2.2, color=pal["accent"])
    if highlight_x is not None and math.isfinite(highlight_x):
        mask = (xs >= a) & (xs <= min(b, highlight_x))
        if np.any(mask):
            ax.fill_between(xs[mask], 0, ys[mask], color=pal["accent_fill"], alpha=0.28)
        ax.axvline(highlight_x, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.75)
    else:
        ax.fill_between(xs, 0, ys, color=pal["accent_fill"], alpha=0.12)
    ax.set_title(f"Uniform PDF [a={a:g}, b={b:g}]")
    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    ax.set_ylim(bottom=0, top=(1.0 / (b - a)) * 1.25)
    return _png_bytes(fig)


def plot_uniform_cdf(
    a: float,
    b: float,
    highlight_x: float | None = None,
    theme: str = "light",
) -> bytes:
    _chk_finite(a, "a")
    _chk_finite(b, "b")
    _chk(b > a, "require b > a")
    pad = (b - a) * 0.2
    xs = np.linspace(a - pad, b + pad, 500)
    ys = np.zeros_like(xs)
    ys[xs > b] = 1.0
    mask = (xs >= a) & (xs <= b)
    ys[mask] = (xs[mask] - a) / (b - a)

    fig, ax, pal = _new_figure((6.4, 3.3), theme)
    ax.plot(xs, ys, linewidth=2.2, color=pal["accent"])
    if highlight_x is not None and math.isfinite(highlight_x):
        val = 0.0 if highlight_x < a else (1.0 if highlight_x > b else (highlight_x - a) / (b - a))
        ax.plot([highlight_x], [val], "o", color=pal["marker"], markersize=7, zorder=5)
        ax.axvline(highlight_x, color=pal["ref_line"], linestyle="--", linewidth=1.0, alpha=0.75)
    ax.set_title(f"Uniform CDF [a={a:g}, b={b:g}]")
    ax.set_xlabel("x")
    ax.set_ylabel("F(x)")
    ax.set_ylim(-0.02, 1.04)
    return _png_bytes(fig)
