"""Pydantic v2 request/response schemas and finite-number validators for /api/v2/*."""

import math
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def _ensure_finite(val: float) -> float:
    if isinstance(val, bool) or not math.isfinite(float(val)):
        raise ValueError("Value must be a finite real number (not NaN or Inf)")
    return 0.0 if val == 0.0 else float(val)


FiniteFloat = Annotated[float, AfterValidator(_ensure_finite)]


def clean_float(val: float | None) -> float | None:
    """Convert non-finite floats (NaN/Inf) to None for strict JSON compliance."""
    if val is None:
        return None
    fval = float(val)
    if not math.isfinite(fval):
        return None
    return 0.0 if fval == 0.0 else fval


class StrictRequestModel(BaseModel):
    """Base request model rejecting unknown fields."""

    model_config = ConfigDict(extra="forbid")


# ---- 1. Distributions ----

DistributionId = Literal[
    "normal",
    "student_t",
    "chi2",
    "f",
    "exponential",
    "uniform",
    "gamma",
    "beta",
    "lognormal",
    "binomial",
    "poisson",
    "geometric",
    "negbinom",
    "hypergeom",
]

RegionType = Literal["left", "right", "interval", "two_tailed", "none"]


class CurveOverlaySpec(StrictRequestModel):
    dist: DistributionId
    params: dict[str, FiniteFloat] = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=80)


class DistEvaluateRequest(StrictRequestModel):
    dist: DistributionId = "normal"
    params: dict[str, FiniteFloat] = Field(default_factory=lambda: {"mu": 0.0, "sigma": 1.0})
    region: RegionType = "two_tailed"
    a: FiniteFloat | None = -1.959963984540054
    b: FiniteFloat | None = 1.959963984540054
    view: Literal["pdf", "cdf"] = "pdf"
    points: int = Field(default=280, ge=60, le=600)
    overlays: list[CurveOverlaySpec] = Field(default_factory=list, max_length=2)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "dist": "normal",
                    "params": {"mu": 0.0, "sigma": 1.0},
                    "region": "two_tailed",
                    "a": -1.959963984540054,
                    "b": 1.959963984540054,
                    "view": "pdf",
                    "overlays": [],
                }
            ]
        },
    )


class DistQuantileRequest(StrictRequestModel):
    dist: DistributionId = "normal"
    params: dict[str, FiniteFloat] = Field(default_factory=lambda: {"mu": 0.0, "sigma": 1.0})
    target_p: FiniteFloat = Field(..., gt=0.0, lt=1.0, description="Target probability strictly in (0, 1)")
    region: Literal["left", "right", "interval", "two_tailed"] = "two_tailed"

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "dist": "normal",
                    "params": {"mu": 0.0, "sigma": 1.0},
                    "target_p": 0.05,
                    "region": "two_tailed",
                }
            ]
        },
    )


# ---- 2. Hypothesis Testing, CIs & Power ----


class MeansTestRequest(StrictRequestModel):
    test_type: Literal["one_sample_z", "one_sample_t", "two_sample_t_equal", "two_sample_t_welch"] = "one_sample_t"
    input_mode: Literal["summary", "raw"] = "summary"
    alternative: Literal["two-sided", "less", "greater"] = "two-sided"
    alpha: FiniteFloat = Field(default=0.05, gt=0.0, lt=0.5)
    mu0: FiniteFloat = 0.0
    pop_sigma: FiniteFloat | None = Field(default=None, gt=0.0)
    mean1: FiniteFloat | None = None
    sd1: FiniteFloat | None = Field(default=None, ge=0.0)
    n1: int | None = Field(default=None, ge=2, le=1_000_000)
    mean2: FiniteFloat | None = None
    sd2: FiniteFloat | None = Field(default=None, ge=0.0)
    n2: int | None = Field(default=None, ge=2, le=1_000_000)
    raw1: str | None = Field(default=None, max_length=200_000)
    raw2: str | None = Field(default=None, max_length=200_000)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "test_type": "two_sample_t_welch",
                    "input_mode": "summary",
                    "alternative": "two-sided",
                    "alpha": 0.05,
                    "mean1": 102.4,
                    "sd1": 14.2,
                    "n1": 32,
                    "mean2": 95.1,
                    "sd2": 11.8,
                    "n2": 29,
                }
            ]
        },
    )


class ProportionsTestRequest(StrictRequestModel):
    test_type: Literal["one_prop", "two_prop"] = "two_prop"
    alternative: Literal["two-sided", "less", "greater"] = "two-sided"
    alpha: FiniteFloat = Field(default=0.05, gt=0.0, lt=0.5)
    x1: int = Field(..., ge=0, le=10_000_000)
    n1: int = Field(..., ge=1, le=10_000_000)
    p0: FiniteFloat = Field(default=0.5, gt=0.0, lt=1.0)
    x2: int | None = Field(default=None, ge=0, le=10_000_000)
    n2: int | None = Field(default=None, ge=1, le=10_000_000)

    @model_validator(mode="after")
    def _check_counts(self) -> "ProportionsTestRequest":
        if self.x1 > self.n1:
            raise ValueError("x1 must satisfy 0 <= x1 <= n1")
        if self.test_type == "two_prop":
            if self.x2 is None or self.n2 is None:
                raise ValueError("x2 and n2 are required for two_prop test")
            if self.x2 > self.n2:
                raise ValueError("x2 must satisfy 0 <= x2 <= n2")
        return self

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "test_type": "two_prop",
                    "alternative": "two-sided",
                    "alpha": 0.05,
                    "x1": 120,
                    "n1": 1000,
                    "x2": 156,
                    "n2": 1000,
                }
            ]
        },
    )


class PowerAnalysisRequest(StrictRequestModel):
    mode: Literal["two_prop", "two_mean", "one_mean"] = "two_prop"
    solve_for: Literal["sample_size", "power"] = "sample_size"
    alternative: Literal["two-sided", "less", "greater"] = "two-sided"
    alpha: FiniteFloat = Field(default=0.05, gt=0.0, lt=0.5)
    target_power: FiniteFloat = Field(default=0.80, gt=0.05, lt=0.9999)
    n_per_group: int = Field(default=100, ge=2, le=10_000_000)
    p1: FiniteFloat = Field(default=0.10, gt=0.0, lt=1.0)
    p2: FiniteFloat = Field(default=0.14, gt=0.0, lt=1.0)
    mean_diff: FiniteFloat = 0.5
    sd: FiniteFloat = Field(default=1.0, gt=0.0)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "mode": "two_prop",
                    "solve_for": "sample_size",
                    "alternative": "two-sided",
                    "alpha": 0.05,
                    "target_power": 0.80,
                    "p1": 0.12,
                    "p2": 0.16,
                }
            ]
        },
    )


class ChiSqTestRequest(StrictRequestModel):
    mode: Literal["gof", "independence"] = "independence"
    alpha: FiniteFloat = Field(default=0.05, gt=0.0, lt=0.5)
    observed_1d: list[FiniteFloat] | None = Field(default=None, min_length=2, max_length=100)
    expected_1d: list[FiniteFloat] | None = Field(default=None, min_length=2, max_length=100)
    table: list[list[FiniteFloat]] | None = Field(default=None, min_length=2, max_length=20)
    row_labels: list[str] | None = None
    col_labels: list[str] | None = None
    yates: bool = False

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "mode": "independence",
                    "alpha": 0.05,
                    "table": [[42, 18], [28, 32]],
                    "row_labels": ["Control", "Variant"],
                    "col_labels": ["Converted", "Bounced"],
                }
            ]
        },
    )


class AnovaGroupSummary(StrictRequestModel):
    label: str = Field(default="Group", max_length=60)
    n: int = Field(..., ge=2, le=1_000_000)
    mean: FiniteFloat
    sd: FiniteFloat = Field(..., ge=0.0)


class AnovaTestRequest(StrictRequestModel):
    input_mode: Literal["raw", "summary"] = "raw"
    alpha: FiniteFloat = Field(default=0.05, gt=0.0, lt=0.5)
    groups_raw: list[dict[str, str]] | None = Field(default=None, min_length=2, max_length=12)
    groups_summary: list[AnovaGroupSummary] | None = Field(default=None, min_length=2, max_length=12)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "input_mode": "summary",
                    "alpha": 0.05,
                    "groups_summary": [
                        {"label": "Control", "n": 25, "mean": 12.1, "sd": 2.4},
                        {"label": "Dose A", "n": 25, "mean": 13.8, "sd": 2.6},
                        {"label": "Dose B", "n": 25, "mean": 15.2, "sd": 2.5},
                    ],
                }
            ]
        },
    )


# ---- 3. Empirical Data & Fitter ----


class FitAnalyzeRequest(StrictRequestModel):
    raw_text: str | None = Field(default=None, max_length=500_000)
    data: list[FiniteFloat] | None = Field(default=None, min_length=3, max_length=50_000)
    bin_rule: Literal["fd", "sturges", "scott", "manual"] = "fd"
    bins: int = Field(default=20, ge=3, le=150)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "raw_text": "12.4, 14.1, 13.8, 15.2, 11.9, 13.5, 16.0, 14.7, 13.1, 14.9, 12.8, 15.6",
                    "bin_rule": "fd",
                }
            ]
        },
    )


# ---- 4. Simulators & Joint ----


class CltSimRequest(StrictRequestModel):
    population: Literal["uniform", "exponential", "skewed_beta", "bimodal", "bernoulli", "poisson"] = "exponential"
    n: int = Field(default=30, ge=1, le=200)
    trials: int = Field(default=5000, ge=100, le=50_000)
    bins: int = Field(default=36, ge=8, le=100)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"population": "exponential", "n": 30, "trials": 5000, "bins": 36, "seed": 42}
            ]
        },
    )


class JointMatrixRequest(StrictRequestModel):
    x_values: list[FiniteFloat] = Field(..., min_length=1, max_length=12)
    y_values: list[FiniteFloat] = Field(..., min_length=1, max_length=12)
    matrix: list[list[FiniteFloat]] = Field(..., min_length=1, max_length=12)
    auto_normalize: bool = False

    @model_validator(mode="after")
    def _check_shape(self) -> "JointMatrixRequest":
        if len(set(self.x_values)) != len(self.x_values):
            raise ValueError("x_values must be distinct")
        if len(set(self.y_values)) != len(self.y_values):
            raise ValueError("y_values must be distinct")
        if len(self.matrix) != len(self.x_values):
            raise ValueError("matrix row count must equal len(x_values)")
        for row in self.matrix:
            if len(row) != len(self.y_values):
                raise ValueError("each matrix row must have length equal to len(y_values)")
            if any(p < 0.0 for p in row):
                raise ValueError("all joint probabilities must be >= 0")
        return self

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "x_values": [0, 1],
                    "y_values": [0, 1],
                    "matrix": [[0.1, 0.2], [0.3, 0.4]],
                    "auto_normalize": False,
                }
            ]
        },
    )


# ---- 5. Backend 2x Retina PNG Export ----


class PngExportRequest(StrictRequestModel):
    kind: Literal["curve", "histogram", "scatter", "heatmap"] = "curve"
    theme: Literal["light", "dark"] = "light"
    title: str = Field(default="p05.dev Plot", max_length=160)
    xlabel: str = Field(default="x", max_length=80)
    ylabel: str = Field(default="f(x)", max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
