/* Custom zero-dependency SVG chart engine (strictly CSP-safe: zero inline style attributes) */

const SVG_NS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, cls = "") {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== null && v !== undefined) node.setAttribute(k, String(v));
  }
  if (cls) node.setAttribute("class", cls);
  return node;
}

function niceTicks(min, max, count = 6) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return [0];
  const span = max - min;
  const rawStep = span / Math.max(1, count);
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  let step = mag;
  if (norm > 5) step = 10 * mag;
  else if (norm > 2) step = 5 * mag;
  else if (norm > 1) step = 2 * mag;
  const start = Math.ceil(min / step) * step;
  const ticks = [];
  for (let v = start; v <= max + step * 1e-6; v += step) {
    ticks.push(Math.abs(v) < step * 1e-9 ? 0 : v);
    if (ticks.length > 15) break;
  }
  return ticks;
}

function fmtTick(v) {
  if (Math.abs(v) < 1e-12) return "0";
  if (Math.abs(v) >= 1000 || Math.abs(v) < 0.01) return v.toExponential(1);
  return Number(v.toPrecision(4)).toString();
}

function makeMapper(W, H, pad, xMin, xMax, yMin, yMax) {
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;
  const sx = (x) => pad.l + ((x - xMin) / (xMax - xMin || 1)) * plotW;
  const sy = (y) => pad.t + plotH - ((y - yMin) / (yMax - yMin || 1)) * plotH;
  const ix = (px) => xMin + ((px - pad.l) / (plotW || 1)) * (xMax - xMin);
  return { sx, sy, ix, plotW, plotH };
}

function drawGridAndAxes(svg, W, H, pad, xMin, xMax, yMin, yMax, xlabel, ylabel) {
  const { sx, sy } = makeMapper(W, H, pad, xMin, xMax, yMin, yMax);
  svg.appendChild(el("rect", { x: 0, y: 0, width: W, height: H, rx: 4 }, "svg-bg"));

  const xTicks = niceTicks(xMin, xMax, 6);
  const yTicks = niceTicks(yMin, yMax, 5);

  for (const yt of yTicks) {
    const py = sy(yt);
    svg.appendChild(el("line", { x1: pad.l, y1: py, x2: W - pad.r, y2: py }, "svg-grid"));
    const t = el("text", { x: pad.l - 7, y: py + 4, "text-anchor": "end" }, "svg-tick-text");
    t.textContent = fmtTick(yt);
    svg.appendChild(t);
  }
  for (const xt of xTicks) {
    const px = sx(xt);
    svg.appendChild(el("line", { x1: px, y1: pad.t, x2: px, y2: H - pad.b }, "svg-grid"));
    const t = el("text", { x: px, y: H - pad.b + 16, "text-anchor": "middle" }, "svg-tick-text");
    t.textContent = fmtTick(xt);
    svg.appendChild(t);
  }

  svg.appendChild(el("line", { x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b }, "svg-axis"));
  svg.appendChild(el("line", { x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b }, "svg-axis"));

  if (xlabel) {
    const xl = el("text", { x: pad.l + (W - pad.l - pad.r) / 2, y: H - 6, "text-anchor": "middle" }, "svg-axis-label");
    xl.textContent = xlabel;
    svg.appendChild(xl);
  }
  if (ylabel) {
    const yl = el(
      "text",
      { x: 14, y: pad.t + (H - pad.t - pad.b) / 2, "text-anchor": "middle", transform: `rotate(-90 14 ${pad.t + (H - pad.t - pad.b) / 2})` },
      "svg-axis-label"
    );
    yl.textContent = ylabel;
    svg.appendChild(yl);
  }
  return { sx, sy };
}

function buildLinePath(xs, ys, sx, sy, step = false) {
  if (!xs.length) return "";
  const parts = [`M ${sx(xs[0]).toFixed(2)} ${sy(ys[0]).toFixed(2)}`];
  for (let i = 1; i < xs.length; i += 1) {
    if (step) {
      parts.push(`H ${sx(xs[i]).toFixed(2)} V ${sy(ys[i]).toFixed(2)}`);
    } else {
      parts.push(`L ${sx(xs[i]).toFixed(2)} ${sy(ys[i]).toFixed(2)}`);
    }
  }
  return parts.join(" ");
}

function buildShadePolygon(xs, ys, lo, hi, sx, sy, yZero) {
  const pts = [];
  for (let i = 0; i < xs.length; i += 1) {
    if (xs[i] >= lo && xs[i] <= hi) {
      pts.push([xs[i], ys[i]]);
    }
  }
  if (pts.length < 2) return null;
  const startX = sx(pts[0][0]).toFixed(2);
  const endX = sx(pts[pts.length - 1][0]).toFixed(2);
  const d = [`M ${startX} ${yZero.toFixed(2)}`];
  for (const [xv, yv] of pts) {
    d.push(`L ${sx(xv).toFixed(2)} ${sy(yv).toFixed(2)}`);
  }
  d.push(`L ${endX} ${yZero.toFixed(2)} Z`);
  return { d: d.join(" "), x: pts.map((p) => p[0]), y: pts.map((p) => p[1]) };
}

function drawLegend(svg, items, xStart, yStart) {
  let y = yStart;
  items.forEach((item, idx) => {
    const cls = `svg-curve-${Math.min(2, idx)}`;
    svg.appendChild(el("line", { x1: xStart, y1: y, x2: xStart + 22, y2: y }, cls));
    const t = el("text", { x: xStart + 28, y: y + 4 }, "svg-legend-text");
    t.textContent = item;
    svg.appendChild(t);
    y += 18;
  });
}

export function renderDistributionChart(svg, data, { onDragBounds, onCommitBounds } = {}) {
  svg.replaceChildren();
  const W = 760;
  const H = 360;
  const pad = { l: 56, r: 22, t: 22, b: 42 };
  const isCdf = data.view === "cdf";
  const primary = data.primary;
  const overlays = data.overlays || [];
  const yField = isCdf ? "cdf" : "density";

  const xMin = data.x_domain[0];
  const xMax = data.x_domain[1];
  let yMax = isCdf ? 1.05 : 0.01;
  if (!isCdf) {
    for (const c of [primary, ...overlays]) {
      for (const v of c[yField]) {
        if (Number.isFinite(v) && v > yMax) yMax = v;
      }
    }
    yMax *= 1.15;
  }

  const { sx, sy, ix } = makeMapper(W, H, pad, xMin, xMax, 0, yMax);
  drawGridAndAxes(svg, W, H, pad, xMin, xMax, 0, yMax, "x", isCdf ? "F(x)" : data.family === "discrete" ? "P(X = k)" : "f(x)");

  const shadeGroup = el("g");
  svg.appendChild(shadeGroup);

  const exportShade = [];
  const highlightXs = [];

  function drawShading(boundA, boundB) {
    shadeGroup.replaceChildren();
    exportShade.length = 0;
    highlightXs.length = 0;

    if (data.family === "discrete" && !isCdf) {
      const xs = primary.x;
      const ys = primary.density;
      const nBars = xs.length;
      const barW = Math.max(3, Math.min(26, ((W - pad.l - pad.r) / Math.max(1, nBars)) * 0.66));
      const y0 = sy(0);
      for (let i = 0; i < xs.length; i += 1) {
        const k = xs[i];
        let active = false;
        if (data.region === "left" && boundA !== null) active = k <= boundA;
        else if (data.region === "right" && boundB !== null) active = k >= Math.ceil(boundB);
        else if (data.region === "interval" && boundA !== null && boundB !== null) {
          active = k >= Math.ceil(Math.min(boundA, boundB)) && k <= Math.floor(Math.max(boundA, boundB));
        } else if (data.region === "two_tailed" && boundA !== null && boundB !== null) {
          active = k <= Math.floor(boundA) || k >= Math.ceil(boundB);
        }
        if (active) highlightXs.push(k);
        const px = sx(k) - barW / 2;
        const py = sy(ys[i]);
        shadeGroup.appendChild(
          el("rect", { x: px.toFixed(2), y: py.toFixed(2), width: barW.toFixed(2), height: Math.max(0, y0 - py).toFixed(2), rx: 2 }, active ? "svg-bar-active" : "svg-bar")
        );
      }
      return;
    }

    if (isCdf) return;
    const xs = primary.x;
    const ys = primary.density;
    const y0 = sy(0);
    const regions = [];
    if (data.region === "left" && boundA !== null) regions.push([xMin, boundA]);
    else if (data.region === "right" && boundB !== null) regions.push([boundB, xMax]);
    else if (data.region === "interval" && boundA !== null && boundB !== null) {
      regions.push([Math.min(boundA, boundB), Math.max(boundA, boundB)]);
    } else if (data.region === "two_tailed" && boundA !== null && boundB !== null) {
      regions.push([xMin, Math.min(boundA, boundB)], [Math.max(boundA, boundB), xMax]);
    }
    for (const [lo, hi] of regions) {
      const poly = buildShadePolygon(xs, ys, lo, hi, sx, sy, y0);
      if (poly) {
        shadeGroup.appendChild(el("path", { d: poly.d }, "svg-shade"));
        exportShade.push({ x: poly.x, y: poly.y });
      }
    }
  }

  let curA = data.a;
  let curB = data.b;
  drawShading(curA, curB);

  // Curves (primary + up to 2 overlays)
  const allCurves = [primary, ...overlays];
  allCurves.forEach((curve, idx) => {
    if (idx === 0 && data.family === "discrete" && !isCdf) return;
    const d = buildLinePath(curve.x, curve[yField], sx, sy, data.family === "discrete" && isCdf);
    if (d) svg.appendChild(el("path", { d }, `svg-curve-${Math.min(2, idx)}`));
  });

  if (allCurves.length > 1) {
    drawLegend(svg, allCurves.map((c) => c.label), pad.l + 12, pad.t + 10);
  }

  // Draggable vertical handles for a / b
  const handles = [];
  if (data.region === "left" && curA !== null) handles.push({ which: "a", label: "a" });
  else if (data.region === "right" && curB !== null) handles.push({ which: "b", label: "b" });
  else if ((data.region === "interval" || data.region === "two_tailed") && curA !== null && curB !== null) {
    handles.push({ which: "a", label: "a" }, { which: "b", label: "b" });
  }

  for (const h of handles) {
    const val = h.which === "a" ? curA : curB;
    const clampedX = Math.max(xMin, Math.min(xMax, val));
    const px = sx(clampedX);
    const g = el("g");
    const vline = el("line", { x1: px, y1: pad.t, x2: px, y2: H - pad.b }, "svg-handle-line");
    const hit = el("rect", { x: px - 10, y: pad.t, width: 20, height: H - pad.t - pad.b }, "svg-handle-hit");
    const knob = el("circle", { cx: px, cy: pad.t + 16, r: 6.5 }, "svg-handle-knob");
    const lbl = el("text", { x: px, y: pad.t + 34, "text-anchor": "middle" }, "svg-handle-label");
    lbl.textContent = `${h.label}=${fmtTick(val)}`;
    g.append(vline, hit, knob, lbl);
    svg.appendChild(g);

    const startDrag = (ev) => {
      ev.preventDefault();
      knob.classList.add("dragging");
      try {
        knob.setPointerCapture(ev.pointerId);
      } catch {
        // ignore if unsupported
      }
      const onMove = (mv) => {
        const rect = svg.getBoundingClientRect();
        const svgX = ((mv.clientX - rect.left) / (rect.width || 1)) * W;
        let nextVal = Math.max(xMin, Math.min(xMax, ix(svgX)));
        if (data.family === "discrete") nextVal = Math.round(nextVal);
        if (h.which === "a") curA = nextVal;
        else curB = nextVal;
        if (handles.length === 2 && curA > curB) {
          if (h.which === "a") curA = curB;
          else curB = curA;
        }
        const nx = sx(h.which === "a" ? curA : curB);
        vline.setAttribute("x1", nx);
        vline.setAttribute("x2", nx);
        hit.setAttribute("x", nx - 10);
        knob.setAttribute("cx", nx);
        lbl.setAttribute("x", nx);
        lbl.textContent = `${h.label}=${fmtTick(h.which === "a" ? curA : curB)}`;
        drawShading(curA, curB);
        if (onDragBounds) onDragBounds(curA, curB);
      };
      const onUp = () => {
        knob.classList.remove("dragging");
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        if (onCommitBounds) onCommitBounds(curA, curB);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    };

    knob.addEventListener("pointerdown", startDrag);
    hit.addEventListener("pointerdown", startDrag);
  }

  return {
    kind: "curve",
    theme: document.documentElement.getAttribute("data-theme") || "light",
    title: `${data.name} · ${data.expression}`,
    xlabel: "x",
    ylabel: isCdf ? "F(x)" : "f(x)",
    payload: {
      family: data.family,
      is_cdf: isCdf,
      curves: allCurves.map((c) => ({ label: c.label, x: c.x, y: c[yField] })),
      shade: exportShade,
      highlight_x: highlightXs,
      markers: handles.map((h) => ({ x: h.which === "a" ? curA : curB, label: `${h.label}=${fmtTick(h.which === "a" ? curA : curB)}`, dashed: true })),
    },
  };
}

export function renderNullTailChart(svg, plot, title = "Null Distribution & Test Statistic") {
  svg.replaceChildren();
  const W = 760;
  const H = 340;
  const pad = { l: 56, r: 22, t: 22, b: 42 };
  const xs = plot.x || [];
  const ys = plot.y || [];
  const xMin = xs[0] ?? -4;
  const xMax = xs[xs.length - 1] ?? 4;
  const yMax = Math.max(0.05, ...ys) * 1.15;

  const { sx, sy } = drawGridAndAxes(svg, W, H, pad, xMin, xMax, 0, yMax, "Test Statistic", "Density");
  const y0 = sy(0);
  const crits = plot.critical_values || [];
  const shadePolys = [];

  if (plot.tail_mode === "two_tailed" && crits.length === 2) {
    for (const [lo, hi] of [[xMin, crits[0]], [crits[1], xMax]]) {
      const poly = buildShadePolygon(xs, ys, lo, hi, sx, sy, y0);
      if (poly) {
        svg.appendChild(el("path", { d: poly.d }, "svg-shade"));
        shadePolys.push({ x: poly.x, y: poly.y });
      }
    }
  } else if (plot.tail_mode === "right" && crits.length >= 1) {
    const poly = buildShadePolygon(xs, ys, crits[0], xMax, sx, sy, y0);
    if (poly) {
      svg.appendChild(el("path", { d: poly.d }, "svg-shade"));
      shadePolys.push({ x: poly.x, y: poly.y });
    }
  } else if (plot.tail_mode === "left" && crits.length >= 1) {
    const poly = buildShadePolygon(xs, ys, xMin, crits[0], sx, sy, y0);
    if (poly) {
      svg.appendChild(el("path", { d: poly.d }, "svg-shade"));
      shadePolys.push({ x: poly.x, y: poly.y });
    }
  }

  svg.appendChild(el("path", { d: buildLinePath(xs, ys, sx, sy) }, "svg-curve-0"));

  const markers = [];
  for (const c of crits) {
    if (c >= xMin && c <= xMax) {
      const px = sx(c);
      svg.appendChild(el("line", { x1: px, y1: pad.t, x2: px, y2: H - pad.b }, "svg-handle-line"));
      const lbl = el("text", { x: px, y: pad.t + 14, "text-anchor": "middle" }, "svg-tick-text");
      lbl.textContent = `crit=${fmtTick(c)}`;
      svg.appendChild(lbl);
      markers.push({ x: c, label: `crit=${fmtTick(c)}`, dashed: true });
    }
  }

  if (plot.stat !== null && plot.stat !== undefined) {
    const clamped = Math.max(xMin, Math.min(xMax, plot.stat));
    const px = sx(clamped);
    svg.appendChild(el("line", { x1: px, y1: pad.t + 18, x2: px, y2: H - pad.b }, "svg-ref-line"));
    const lbl = el("text", { x: px, y: pad.t + 30, "text-anchor": "middle" }, "svg-handle-label");
    lbl.textContent = `stat=${fmtTick(plot.stat)}`;
    svg.appendChild(lbl);
    markers.push({ x: plot.stat, label: `stat=${fmtTick(plot.stat)}`, dashed: false });
  }

  return {
    kind: "curve",
    theme: document.documentElement.getAttribute("data-theme") || "light",
    title,
    xlabel: "Test Statistic",
    ylabel: "Density",
    payload: {
      family: "continuous",
      curves: [{ label: plot.label || "Null", x: xs, y: ys }],
      shade: shadePolys,
      markers,
    },
  };
}

export function renderLineCurveChart(svg, xs, ys, { title, xlabel, ylabel, refX = null, refY = null } = {}) {
  svg.replaceChildren();
  const W = 760;
  const H = 340;
  const pad = { l: 58, r: 22, t: 22, b: 42 };
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const { sx, sy } = drawGridAndAxes(svg, W, H, pad, xMin, xMax, 0, 1.04, xlabel, ylabel);
  svg.appendChild(el("path", { d: buildLinePath(xs, ys, sx, sy) }, "svg-curve-0"));

  const markers = [];
  if (refX !== null && refY !== null) {
    const px = sx(refX);
    const py = sy(refY);
    svg.appendChild(el("line", { x1: px, y1: pad.t, x2: px, y2: H - pad.b }, "svg-handle-line"));
    svg.appendChild(el("circle", { cx: px, cy: py, r: 5 }, "svg-handle-knob"));
    const lbl = el("text", { x: px + 8, y: Math.max(pad.t + 14, py - 8) }, "svg-handle-label");
    lbl.textContent = `(${fmtTick(refX)}, ${fmtTick(refY)})`;
    svg.appendChild(lbl);
    markers.push({ x: refX, label: `n=${refX}`, dashed: true });
  }

  return {
    kind: "curve",
    theme: document.documentElement.getAttribute("data-theme") || "light",
    title: title || "Power Curve",
    xlabel: xlabel || "x",
    ylabel: ylabel || "Power",
    payload: {
      family: "continuous",
      curves: [{ label: title || "Power", x: xs, y: ys }],
      markers,
    },
  };
}

export function renderHistogramChart(svg, edges, densities, curves = [], { title = "Histogram", xlabel = "x", ylabel = "Density" } = {}) {
  svg.replaceChildren();
  const W = 760;
  const H = 320;
  const pad = { l: 56, r: 22, t: 22, b: 42 };
  let xMin = edges[0] ?? 0;
  let xMax = edges[edges.length - 1] ?? 1;
  let yMax = Math.max(0.01, ...densities);
  for (const c of curves) {
    if (c.x?.length) {
      xMin = Math.min(xMin, c.x[0]);
      xMax = Math.max(xMax, c.x[c.x.length - 1]);
    }
    if (c.y?.length) {
      for (const yv of c.y) {
        if (Number.isFinite(yv) && yv > yMax) yMax = yv;
      }
    }
  }
  yMax *= 1.14;

  const { sx, sy } = drawGridAndAxes(svg, W, H, pad, xMin, xMax, 0, yMax, xlabel, ylabel);
  const y0 = sy(0);

  for (let i = 0; i < densities.length; i += 1) {
    const x0 = sx(edges[i]);
    const x1 = sx(edges[i + 1]);
    const py = sy(densities[i]);
    svg.appendChild(
      el("rect", { x: x0.toFixed(2), y: py.toFixed(2), width: Math.max(1, x1 - x0 - 1).toFixed(2), height: Math.max(0, y0 - py).toFixed(2) }, "svg-hist-bar")
    );
  }

  curves.forEach((c, idx) => {
    if (c.x?.length && c.y?.length) {
      svg.appendChild(el("path", { d: buildLinePath(c.x, c.y, sx, sy) }, `svg-curve-${Math.min(2, idx)}`));
    }
  });
  if (curves.length > 0) {
    drawLegend(svg, curves.map((c) => c.label || `Curve ${c}`), pad.l + 12, pad.t + 10);
  }

  return {
    kind: "histogram",
    theme: document.documentElement.getAttribute("data-theme") || "light",
    title,
    xlabel,
    ylabel,
    payload: { edges, densities, curves },
  };
}

export function renderQQChart(svg, theoretical, sample, modelName) {
  svg.replaceChildren();
  const W = 760;
  const H = 260;
  const pad = { l: 58, r: 22, t: 22, b: 42 };
  const validPairs = [];
  for (let i = 0; i < theoretical.length; i += 1) {
    if (Number.isFinite(theoretical[i]) && Number.isFinite(sample[i])) {
      validPairs.push([theoretical[i], sample[i]]);
    }
  }
  if (!validPairs.length) return null;
  const xs = validPairs.map((p) => p[0]);
  const ys = validPairs.map((p) => p[1]);
  const lo = Math.min(...xs, ...ys);
  const hi = Math.max(...xs, ...ys);
  const span = (hi - lo) || 1;
  const minV = lo - 0.06 * span;
  const maxV = hi + 0.06 * span;

  const { sx, sy } = drawGridAndAxes(svg, W, H, pad, minV, maxV, minV, maxV, `Theoretical (${modelName})`, "Sample Quantiles");
  svg.appendChild(el("line", { x1: sx(lo), y1: sy(lo), x2: sx(hi), y2: sy(hi) }, "svg-ref-line"));
  for (const [xv, yv] of validPairs) {
    svg.appendChild(el("circle", { cx: sx(xv).toFixed(2), cy: sy(yv).toFixed(2), r: 3.4 }, "svg-qq-dot"));
  }

  return {
    kind: "scatter",
    theme: document.documentElement.getAttribute("data-theme") || "light",
    title: `Q-Q Plot (${modelName})`,
    xlabel: `Theoretical Quantiles (${modelName})`,
    ylabel: "Sample Quantiles",
    payload: { x: xs, y: ys, ref_line: { x: [lo, hi], y: [lo, hi] } },
  };
}

export function renderJointHeatmapChart(svg, data) {
  svg.replaceChildren();
  const W = 760;
  const H = 340;
  const pad = { l: 64, r: 190, t: 36, b: 50 };
  const xs = data.x_values;
  const ys = data.y_values;
  const mat = data.matrix;
  const nx = xs.length;
  const ny = ys.length;
  const gridW = W - pad.l - pad.r;
  const gridH = H - pad.t - pad.b;
  const cellW = gridW / Math.max(1, nx);
  const cellH = gridH / Math.max(1, ny);
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  svg.appendChild(el("rect", { x: 0, y: 0, width: W, height: H, rx: 4 }, "svg-bg"));

  const vmax = Math.max(1e-9, ...mat.flat());
  for (let i = 0; i < nx; i += 1) {
    for (let j = 0; j < ny; j += 1) {
      const val = mat[i][j];
      const norm = val / vmax;
      const py = pad.t + (ny - 1 - j) * cellH;
      const px = pad.l + i * cellW;
      const alpha = (0.08 + 0.86 * norm).toFixed(3);
      svg.appendChild(
        el("rect", {
          x: px + 1,
          y: py + 1,
          width: Math.max(2, cellW - 2),
          height: Math.max(2, cellH - 2),
          rx: 4,
          fill: isDark ? "#14B8A6" : "#0D9488",
          "fill-opacity": alpha,
        })
      );
      const txtCls = norm >= 0.55 ? (isDark ? "svg-heat-text-dark" : "svg-heat-text-light") : (isDark ? "svg-heat-text-light" : "svg-heat-text-dark");
      const t = el("text", { x: px + cellW / 2, y: py + cellH / 2 + 4, "text-anchor": "middle" }, txtCls);
      t.textContent = val.toFixed(3);
      svg.appendChild(t);
    }
  }

  // Axis labels
  xs.forEach((xv, i) => {
    const t = el("text", { x: pad.l + (i + 0.5) * cellW, y: H - pad.b + 18, "text-anchor": "middle" }, "svg-tick-text");
    t.textContent = `X=${xv}`;
    svg.appendChild(t);
  });
  ys.forEach((yv, j) => {
    const py = pad.t + (ny - 1 - j + 0.5) * cellH + 4;
    const t = el("text", { x: pad.l - 10, y: py, "text-anchor": "end" }, "svg-tick-text");
    t.textContent = `Y=${yv}`;
    svg.appendChild(t);
  });

  // Marginal mini bar charts on right
  const barX = W - pad.r + 24;
  const barMaxW = 130;
  const mHead = el("text", { x: barX, y: pad.t - 10 }, "svg-axis-label");
  mHead.textContent = "Marginals P(X), P(Y)";
  svg.appendChild(mHead);

  let curY = pad.t + 6;
  data.marginal_x.forEach((px, i) => {
    const lbl = el("text", { x: barX, y: curY + 11 }, "svg-tick-text");
    lbl.textContent = `P(X=${xs[i]})=${px.toFixed(3)}`;
    svg.appendChild(lbl);
    svg.appendChild(el("rect", { x: barX, y: curY + 15, width: Math.max(2, px * barMaxW), height: 7, rx: 2 }, "svg-bar-active"));
    curY += 27;
  });
  curY += 8;
  data.marginal_y.forEach((py, j) => {
    const lbl = el("text", { x: barX, y: curY + 11 }, "svg-tick-text");
    lbl.textContent = `P(Y=${ys[j]})=${py.toFixed(3)}`;
    svg.appendChild(lbl);
    svg.appendChild(el("rect", { x: barX, y: curY + 15, width: Math.max(2, py * barMaxW), height: 7, rx: 2 }, "svg-bar-active"));
    curY += 27;
  });

  return {
    kind: "heatmap",
    theme: isDark ? "dark" : "light",
    title: "Joint Distribution P(X = x, Y = y)",
    xlabel: "X",
    ylabel: "Y",
    payload: { x_values: xs, y_values: ys, matrix: mat },
  };
}

export function downloadSvgElement(svgEl, filename = "p05-chart.svg") {
  if (!svgEl) return;
  const clone = svgEl.cloneNode(true);
  clone.setAttribute("xmlns", SVG_NS);
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  // Embed theme-resolved palette stylesheet inside exported standalone SVG file (not active DOM!)
  const styleNode = document.createElementNS(SVG_NS, "style");
  styleNode.textContent = isDark
    ? `.svg-bg{fill:#0B0C0E}.svg-grid{stroke:#1E293B;stroke-width:1}.svg-axis{stroke:#475569;stroke-width:1.2}.svg-tick-text,.svg-axis-label{fill:#94A3B8;font-family:monospace;font-size:11px}.svg-curve-0{fill:none;stroke:#2DD4BF;stroke-width:2.4}.svg-curve-1{fill:none;stroke:#CBD5E1;stroke-width:1.9;stroke-dasharray:6 4}.svg-curve-2{fill:none;stroke:#F59E0B;stroke-width:1.9;stroke-dasharray:2 4}.svg-shade{fill:#14B8A6;fill-opacity:0.28}.svg-bar{fill:#334155}.svg-bar-active{fill:#2DD4BF}.svg-hist-bar{fill:#14B8A6;fill-opacity:0.22;stroke:#2DD4BF;stroke-width:1}.svg-qq-dot{fill:#2DD4BF}.svg-ref-line{stroke:#5EEAD4;stroke-width:1.5;stroke-dasharray:5 4}.svg-handle-line{stroke:#2DD4BF;stroke-width:1.7;stroke-dasharray:4 3}.svg-handle-knob{fill:#13151A;stroke:#5EEAD4;stroke-width:2.2}.svg-handle-label,.svg-legend-text{fill:#F8FAFC;font-family:monospace;font-size:11px}`
    : `.svg-bg{fill:#FAFAFA}.svg-grid{stroke:#E2E8F0;stroke-width:1}.svg-axis{stroke:#CBD5E1;stroke-width:1.2}.svg-tick-text,.svg-axis-label{fill:#475569;font-family:monospace;font-size:11px}.svg-curve-0{fill:none;stroke:#0D9488;stroke-width:2.4}.svg-curve-1{fill:none;stroke:#475569;stroke-width:1.9;stroke-dasharray:6 4}.svg-curve-2{fill:none;stroke:#B45309;stroke-width:1.9;stroke-dasharray:2 4}.svg-shade{fill:#14B8A6;fill-opacity:0.24}.svg-bar{fill:#CBD5E1}.svg-bar-active{fill:#0D9488}.svg-hist-bar{fill:#14B8A6;fill-opacity:0.22;stroke:#0D9488;stroke-width:1}.svg-qq-dot{fill:#0D9488}.svg-ref-line{stroke:#0F766E;stroke-width:1.5;stroke-dasharray:5 4}.svg-handle-line{stroke:#0F766E;stroke-width:1.7;stroke-dasharray:4 3}.svg-handle-knob{fill:#FFFFFF;stroke:#0F766E;stroke-width:2.2}.svg-handle-label,.svg-legend-text{fill:#0F172A;font-family:monospace;font-size:11px}`;
  clone.insertBefore(styleNode, clone.firstChild);
  const xml = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
