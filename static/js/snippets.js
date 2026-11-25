/* Dynamic Python (scipy.stats), R, LaTeX, and curl snippet generator */

function _scipyCall(dist, p) {
  switch (dist) {
    case "normal":
      return `stats.norm(loc=${p.mu}, scale=${p.sigma})`;
    case "student_t":
      return `stats.t(df=${p.df}, loc=${p.mu}, scale=${p.sigma})`;
    case "chi2":
      return `stats.chi2(df=${p.df})`;
    case "f":
      return `stats.f(dfn=${p.dfn}, dfd=${p.dfd})`;
    case "exponential":
      return `stats.expon(scale=1.0 / ${p.lam})`;
    case "uniform":
      return `stats.uniform(loc=${p.a}, scale=${p.b} - ${p.a})`;
    case "gamma":
      return `stats.gamma(a=${p.alpha}, scale=1.0 / ${p.beta})`;
    case "beta":
      return `stats.beta(a=${p.alpha}, b=${p.beta})`;
    case "lognormal":
      return `stats.lognorm(s=${p.sigma}, scale=math.exp(${p.mu}))`;
    case "binomial":
      return `stats.binom(n=${p.n}, p=${p.p})`;
    case "poisson":
      return `stats.poisson(mu=${p.lam})`;
    case "geometric":
      return `stats.geom(p=${p.p}, loc=-1)  # 0-indexed failures`;
    case "negbinom":
      return `stats.nbinom(n=${p.r}, p=${p.p})`;
    case "hypergeom":
      return `stats.hypergeom(M=${p.M}, n=${p.K}, N=${p.n})`;
    default:
      return "stats.norm()";
  }
}

function _rExpr(dist, p, region, a, b) {
  const map = {
    normal: ["norm", `mean = ${p.mu}, sd = ${p.sigma}`],
    student_t: ["t", `df = ${p.df}`],
    chi2: ["chisq", `df = ${p.df}`],
    f: ["f", `df1 = ${p.dfn}, df2 = ${p.dfd}`],
    exponential: ["exp", `rate = ${p.lam}`],
    uniform: ["unif", `min = ${p.a}, max = ${p.b}`],
    gamma: ["gamma", `shape = ${p.alpha}, rate = ${p.beta}`],
    beta: ["beta", `shape1 = ${p.alpha}, shape2 = ${p.beta}`],
    lognormal: ["lnorm", `meanlog = ${p.mu}, sdlog = ${p.sigma}`],
    binomial: ["binom", `size = ${p.n}, prob = ${p.p}`],
    poisson: ["pois", `lambda = ${p.lam}`],
    geometric: ["geom", `prob = ${p.p}`],
    negbinom: ["nbinom", `size = ${p.r}, prob = ${p.p}`],
    hypergeom: ["hyper", `m = ${p.K}, n = ${p.M - p.K}, k = ${p.n}`],
  };
  const [fn, args] = map[dist] || ["norm", "mean = 0, sd = 1"];
  if (region === "left") return `p${fn}(${a}, ${args})`;
  if (region === "right") return `p${fn}(${b}, ${args}, lower.tail = FALSE)`;
  if (region === "interval") return `p${fn}(${b}, ${args}) - p${fn}(${a}, ${args})`;
  return `p${fn}(${a}, ${args}) + p${fn}(${b}, ${args}, lower.tail = FALSE)`;
}

export function buildSnippets(ctx, lang) {
  const baseUrl = window.location.origin || "https://p05.dev";
  const payload = ctx?.payload;

  if (!payload || !payload.endpoint) {
    return `# Run a calculation in any workspace to generate ${lang.toUpperCase()} code.`;
  }

  if (lang === "curl") {
    const jsonStr = JSON.stringify(payload.body, null, 2);
    return `curl -sS -X POST "${baseUrl}${payload.endpoint}" \\\n  -H "Content-Type: application/json" \\\n  -d '${jsonStr}'`;
  }

  if (ctx.workspace === "explorer" && payload.meta) {
    const { dist, params, region, a, b, formulaLatex } = payload.meta;
    if (lang === "latex") {
      return `%% ${dist} density / mass\n${formulaLatex || "f(x)"}\n\n%% Evaluated region: ${payload.meta.expression || region}`;
    }
    if (lang === "r") {
      return `# R (${dist}, ${region})\nprob <- ${_rExpr(dist, params, region, a ?? 0, b ?? 0)}\nprint(prob)`;
    }
    const call = _scipyCall(dist, params);
    let probExpr = "dist.cdf(a)";
    if (region === "left") probExpr = `dist.cdf(${a})`;
    else if (region === "right") probExpr = `dist.sf(${b})`;
    else if (region === "interval") probExpr = `dist.cdf(${b}) - dist.cdf(${a})`;
    else if (region === "two_tailed") probExpr = `dist.cdf(${a}) + dist.sf(${b})`;
    return `import math\nfrom scipy import stats\n\ndist = ${call}\nprob = float(${probExpr})\nprint(f"prob = {prob:.6g}")`;
  }

  if (lang === "latex") {
    return payload.latex || "% Run Distribution Explorer or Inference for LaTeX output";
  }
  if (lang === "r") {
    return payload.r || `# Equivalent R call for ${payload.endpoint}\n# See curl tab for exact JSON payload`;
  }
  return payload.python || `import requests\n\nres = requests.post("${baseUrl}${payload.endpoint}", json=${JSON.stringify(payload.body)})\nprint(res.json())`;
}
