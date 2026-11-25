"""Tests for empirical data fitting (MLE/AIC/KS/Q-Q), CLT simulator & discrete joint matrix."""

import math

import numpy as np
import pytest

from app.stats.fitting import analyze_empirical_data
from app.stats.schemas import CltSimRequest, FitAnalyzeRequest, JointMatrixRequest
from app.stats.simulators import analyze_joint_matrix, simulate_clt


def test_empirical_fitter_normal_mle_and_outliers():
    rng = np.random.default_rng(12345)
    vals = rng.normal(loc=50.0, scale=5.0, size=250).tolist()
    vals.append(95.0)  # clear high outlier
    raw = "\n".join(f"{v:.4f}" for v in vals)

    res = analyze_empirical_data(FitAnalyzeRequest(raw_text=raw, bin_rule="fd"))
    assert res["n"] == 251
    assert res["descriptives"]["outliers_iqr"]["count"] >= 1
    assert 95.0 in res["descriptives"]["outliers_iqr"]["values"]
    assert res["histogram"]["bin_count"] >= 3
    assert len(res["kde_y"]) == len(res["x_grid"])

    # Fits ranked ascending by AIC
    aics = [f["aic"] for f in res["fits"]]
    assert aics == sorted(aics)
    # Q-Q theoretical quantiles strictly non-decreasing
    qq_theo = res["fits"][0]["qq"]["theoretical"]
    assert all(qq_theo[i] <= qq_theo[i + 1] for i in range(len(qq_theo) - 1))


def test_empirical_fitter_skips_positive_models_when_nonpositive():
    res = analyze_empirical_data(
        FitAnalyzeRequest(raw_text="-2.5, -1.0, 0.0, 1.2, 2.3, 3.1, 0.5, -0.4", bin_rule="sturges")
    )
    skipped_ids = {m["id"] for m in res["skipped_models"]}
    assert {"lognormal", "gamma", "exponential"} <= skipped_ids
    fitted_ids = {m["id"] for m in res["fits"]}
    assert {"normal", "uniform"} <= fitted_ids


@pytest.mark.parametrize(
    "pop",
    ["uniform", "exponential", "skewed_beta", "bimodal", "bernoulli", "poisson"],
)
def test_clt_simulator_se_convergence(pop):
    res = simulate_clt(CltSimRequest(population=pop, n=40, trials=4000, bins=30, seed=7))
    theo_se = res["theoretical"]["se"]
    emp_sd = res["empirical"]["sd"]
    assert math.isclose(emp_sd, theo_se, rel_tol=0.08)
    assert math.isclose(res["empirical"]["mean"], res["theoretical"]["pop_mean"], abs_tol=0.15)


def test_joint_matrix_v2_moments_independence_and_normalize():
    res = analyze_joint_matrix(
        JointMatrixRequest(
            x_values=[0, 1],
            y_values=[0, 1],
            matrix=[[0.1, 0.2], [0.3, 0.4]],
            auto_normalize=False,
        )
    )
    assert res["independent"] is False
    assert math.isclose(res["marginal_x"][0], 0.3, rel_tol=1e-12)
    assert math.isclose(res["marginal_y"][1], 0.6, rel_tol=1e-12)
    assert math.isclose(res["cov"], -0.02, rel_tol=1e-12)
    assert math.isclose(res["x_given_y"]["1"]["0"], 1.0 / 3.0, rel_tol=1e-12)
    assert res["mutual_information"] > 0.0

    # Auto-normalize unnormalized weights
    res_norm = analyze_joint_matrix(
        JointMatrixRequest(
            x_values=[0, 1],
            y_values=[0, 1],
            matrix=[[1.0, 1.0], [1.0, 1.0]],
            auto_normalize=True,
        )
    )
    assert res_norm["independent"] is True
    assert math.isclose(res_norm["sum_p"], 1.0, rel_tol=1e-12)

    # Reject sum != 1 when auto_normalize=False
    with pytest.raises(ValueError):
        analyze_joint_matrix(
            JointMatrixRequest(
                x_values=[0, 1],
                y_values=[0, 1],
                matrix=[[0.2, 0.2], [0.2, 0.2]],
                auto_normalize=False,
            )
        )
