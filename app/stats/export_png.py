"""CSP-safe 2x Retina PNG exporter using thread-safe Matplotlib Agg and 0xWulf Teal Palette."""

from __future__ import annotations

import io
from typing import Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

from .schemas import PngExportRequest

_PALETTES = {
    "light": {
        "bg": "#FFFFFF",
        "axes_bg": "#FAFAFA",
        "fg": "#0F172A",
        "muted": "#475569",
        "grid": "#E2E8F0",
        "spine": "#CBD5E1",
        "primary": "#0D9488",
        "fill": "#14B8A6",
        "marker": "#0F766E",
        "secondary": ["#475569", "#B45309", "#4338CA"],
    },
    "dark": {
        "bg": "#13151A",
        "axes_bg": "#0B0C0E",
        "fg": "#F8FAFC",
        "muted": "#94A3B8",
        "grid": "#1E293B",
        "spine": "#475569",
        "primary": "#2DD4BF",
        "fill": "#14B8A6",
        "marker": "#5EEAD4",
        "secondary": ["#CBD5E1", "#F59E0B", "#818CF8"],
    },
}

_CMAP_LIGHT = LinearSegmentedColormap.from_list(
    "p05_teal_light", ["#FAFAFA", "#CCFBF1", "#5EEAD4", "#14B8A6", "#0F766E"]
)
_CMAP_DARK = LinearSegmentedColormap.from_list(
    "p05_teal_dark", ["#0B0C0E", "#134E4A", "#0D9488", "#14B8A6", "#5EEAD4"]
)


def _setup_fig(theme: str, figsize: tuple[float, float] = (9.0, 4.8)) -> tuple[Figure, Any, dict[str, Any]]:
    pal = _PALETTES["dark"] if theme == "dark" else _PALETTES["light"]
    fig = Figure(figsize=figsize, dpi=220, facecolor=pal["bg"])
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_facecolor(pal["axes_bg"])
    ax.tick_params(colors=pal["muted"], labelsize=9)
    ax.xaxis.label.set_color(pal["muted"])
    ax.yaxis.label.set_color(pal["muted"])
    ax.title.set_color(pal["fg"])
    ax.title.set_fontsize(11)
    ax.title.set_fontweight("bold")
    for name in ("top", "right"):
        ax.spines[name].set_visible(False)
    for name in ("left", "bottom"):
        ax.spines[name].set_color(pal["spine"])
    ax.grid(True, color=pal["grid"], linewidth=0.7, alpha=0.8)
    ax.set_axisbelow(True)
    return fig, ax, pal


def render_export_png(req: PngExportRequest) -> bytes:
    """Render a high-resolution 2x Retina PNG matching the active workbench plot."""
    p = req.payload
    if req.kind == "heatmap":
        mat = np.asarray(p.get("matrix", [[0.25, 0.25], [0.25, 0.25]]), dtype=float)
        xs = p.get("x_values", list(range(mat.shape[0])))
        ys = p.get("y_values", list(range(mat.shape[1])))
        fig, ax, pal = _setup_fig(req.theme, figsize=(6.8, 5.2))
        ax.grid(False)
        cmap = _CMAP_DARK if req.theme == "dark" else _CMAP_LIGHT
        vmax = float(mat.max()) if mat.size and float(mat.max()) > 0 else 1.0
        # Rows = X, Cols = Y -> plot X horizontal, Y vertical by transposing
        disp = mat.T
        im = ax.imshow(disp, origin="lower", cmap=cmap, vmin=0.0, vmax=vmax, aspect="auto")
        ax.set_xticks(range(len(xs)), [f"{float(v):g}" for v in xs])
        ax.set_yticks(range(len(ys)), [f"{float(v):g}" for v in ys])
        mid = vmax * 0.5
        if len(xs) <= 10 and len(ys) <= 10:
            for yi in range(len(ys)):
                for xi in range(len(xs)):
                    val = float(disp[yi, xi])
                    txt_col = ("#0B0C0E" if val >= mid else "#F8FAFC") if req.theme == "dark" else ("#FFFFFF" if val >= mid else "#0F172A")
                    ax.text(xi, yi, f"{val:.4g}", ha="center", va="center", color=txt_col, fontsize=9.5, fontweight="bold")
        cbar = fig.colorbar(im, ax=ax, shrink=0.86, label="P(X=x, Y=y)")
        cbar.ax.yaxis.label.set_color(pal["muted"])
        cbar.ax.tick_params(colors=pal["muted"], labelsize=8)
    elif req.kind == "scatter":
        fig, ax, pal = _setup_fig(req.theme)
        xs = np.asarray(p.get("x", []), dtype=float)
        ys = np.asarray(p.get("y", []), dtype=float)
        if xs.size and ys.size:
            ax.scatter(xs, ys, s=22, color=pal["primary"], alpha=0.85, edgecolors="none")
        line = p.get("ref_line")
        if isinstance(line, dict) and line.get("x") and line.get("y"):
            ax.plot(line["x"], line["y"], linestyle="--", linewidth=1.6, color=pal["marker"])
    elif req.kind == "histogram":
        fig, ax, pal = _setup_fig(req.theme)
        edges = np.asarray(p.get("edges", []), dtype=float)
        densities = np.asarray(p.get("densities", []), dtype=float)
        if edges.size >= 2 and densities.size == edges.size - 1:
            widths = np.diff(edges)
            ax.bar(edges[:-1], densities, width=widths * 0.94, align="edge", color=pal["fill"], alpha=0.25, edgecolor=pal["primary"], linewidth=0.9)
        for idx, curve in enumerate(p.get("curves", [])):
            cx = curve.get("x", [])
            cy = curve.get("y", [])
            if cx and cy:
                col = pal["primary"] if idx == 0 else pal["secondary"][(idx - 1) % len(pal["secondary"])]
                ls = "-" if idx == 0 else ("--" if idx == 1 else ":")
                ax.plot(cx, cy, color=col, linestyle=ls, linewidth=2.0, label=curve.get("label"))
        if any(c.get("label") for c in p.get("curves", [])):
            ax.legend(frameon=False, labelcolor=pal["fg"], fontsize=8.5)
        ax.set_ylim(bottom=0)
    else:  # curve (continuous or discrete)
        fig, ax, pal = _setup_fig(req.theme)
        curves = p.get("curves", [])
        family = p.get("family", "continuous")
        shade_polys = p.get("shade", [])
        for poly in shade_polys:
            px = poly.get("x", [])
            py = poly.get("y", [])
            if px and py:
                ax.fill_between(px, 0, py, color=pal["fill"], alpha=0.28)
        for idx, curve in enumerate(curves):
            cx = np.asarray(curve.get("x", []), dtype=float)
            cy = np.asarray(curve.get("y", []), dtype=float)
            if not cx.size:
                continue
            if idx == 0 and family == "discrete" and not p.get("is_cdf", False):
                hl = set(p.get("highlight_x", []))
                cols = [pal["primary"] if (not hl or float(xv) in hl) else pal["spine"] for xv in cx]
                ax.bar(cx, cy, width=0.68, color=cols, alpha=0.9, label=curve.get("label"))
            else:
                col = pal["primary"] if idx == 0 else pal["secondary"][(idx - 1) % len(pal["secondary"])]
                ls = "-" if idx == 0 else ("--" if idx == 1 else ":")
                ax.plot(cx, cy, color=col, linestyle=ls, linewidth=2.2 if idx == 0 else 1.7, label=curve.get("label"))
        for marker in p.get("markers", []):
            mx = marker.get("x")
            if mx is not None:
                ax.axvline(float(mx), color=pal["marker"], linestyle="--" if marker.get("dashed", True) else "-", linewidth=1.3, label=marker.get("label"))
        if any(c.get("label") for c in curves) or any(m.get("label") for m in p.get("markers", [])):
            ax.legend(frameon=False, labelcolor=pal["fg"], fontsize=8.5)
        ax.set_ylim(bottom=0)

    ax.set_title(req.title)
    ax.set_xlabel(req.xlabel)
    ax.set_ylabel(req.ylabel)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=220, facecolor=fig.get_facecolor())
    return buf.getvalue()
