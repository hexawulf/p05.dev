"""Reference verification tests for hypothesis tests, CIs, power, chi-squared & ANOVA."""

import math

import numpy as np
from scipy import stats

from app.stats.inference import (
    run_anova_test,
    run_chisq_test,
    run_means_test,
    run_power_analysis,
    run_proportions_test,
)
from app.stats.schemas import (
    AnovaGroupSummary,
    AnovaTestRequest,
    ChiSqTestRequest,
    MeansTestRequest,
    PowerAnalysisRequest,
    ProportionsTestRequest,
)


def test_means_tests_raw_matches_summary_and_scipy():
    s1 = [102.0, 98.5, 105.2, 101.0, 99.3, 104.8, 100.1, 103.6]
    s2 = [94.0, 96.2, 91.8, 95.5, 93.4, 97.1, 92.9]

    raw_res = run_means_test(
        MeansTestRequest(
            test_type="two_sample_t_welch",
            input_mode="raw",
            raw1=", ".join(map(str, s1)),
            raw2=", ".join(map(str, s2)),
        )
    )
    sum_res = run_means_test(
        MeansTestRequest(
            test_type="two_sample_t_welch",
            input_mode="summary",
            mean1=float(np.mean(s1)),
            sd1=float(np.std(s1, ddof=1)),
            n1=len(s1),
            mean2=float(np.mean(s2)),
            sd2=float(np.std(s2, ddof=1)),
            n2=len(s2),
        )
    )
    ref = stats.ttest_ind(s1, s2, equal_var=False)
    assert math.isclose(raw_res["statistic"], float(ref.statistic), rel_tol=1e-11)
    assert math.isclose(raw_res["p_value"], float(ref.pvalue), rel_tol=1e-11)
    assert math.isclose(raw_res["statistic"], sum_res["statistic"], rel_tol=1e-12)
    assert math.isclose(raw_res["df"], sum_res["df"], rel_tol=1e-12)
    assert raw_res["cohens_d"] > 2.0

    # One-sample z-test exact check
    z_res = run_means_test(
        MeansTestRequest(
            test_type="one_sample_z",
            input_mode="summary",
            mu0=100.0,
            pop_sigma=15.0,
            mean1=106.0,
            n1=25,
            alternative="greater",
        )
    )
    assert math.isclose(z_res["statistic"], 2.0, rel_tol=1e-12)
    assert math.isclose(z_res["p_value"], float(stats.norm.sf(2.0)), rel_tol=1e-12)


def test_proportions_and_wilson_ci():
    res = run_proportions_test(
        ProportionsTestRequest(test_type="two_prop", x1=120, n1=1000, x2=160, n2=1000)
    )
    assert math.isclose(res["p1"], 0.12, rel_tol=1e-12)
    assert math.isclose(res["p2"], 0.16, rel_tol=1e-12)
    assert math.isclose(res["lift_abs"], 0.04, rel_tol=1e-12)
    assert math.isclose(res["lift_rel"], 1.0 / 3.0, rel_tol=1e-12)
    assert res["wilson_ci_1"][0] < 0.12 < res["wilson_ci_1"][1]
    assert res["p_value"] < 0.05
    assert res["reject_h0"] is True


def test_power_analysis_monotonicity_and_round_trip():
    req_n = PowerAnalysisRequest(
        mode="two_prop", solve_for="sample_size", p1=0.10, p2=0.14, target_power=0.80, alpha=0.05
    )
    res_n = run_power_analysis(req_n)
    assert res_n["achieved_power"] >= 0.80
    assert res_n["total_n"] == 2 * res_n["n_per_group"]

    # Plugging solved n back in should match achieved_power
    res_p = run_power_analysis(
        PowerAnalysisRequest(
            mode="two_prop", solve_for="power", p1=0.10, p2=0.14, n_per_group=res_n["n_per_group"], alpha=0.05
        )
    )
    assert math.isclose(res_p["achieved_power"], res_n["achieved_power"], rel_tol=1e-12)

    # Power vs n must be monotonically non-decreasing
    pows = [pt["power"] for pt in res_n["power_vs_n"]]
    assert all(pows[i] <= pows[i + 1] + 1e-12 for i in range(len(pows) - 1))

    # Means power check
    res_m = run_power_analysis(
        PowerAnalysisRequest(mode="two_mean", solve_for="sample_size", mean_diff=0.5, sd=1.0, target_power=0.80)
    )
    assert 60 <= res_m["n_per_group"] <= 68  # classic d=0.5 -> ~64 per group


def test_chisq_gof_and_independence():
    gof = run_chisq_test(
        ChiSqTestRequest(mode="gof", observed_1d=[25, 20, 15, 40], expected_1d=[0.25, 0.25, 0.25, 0.25])
    )
    ref_gof = stats.chisquare([25, 20, 15, 40], [25, 25, 25, 25])
    assert math.isclose(gof["statistic"], float(ref_gof.statistic), rel_tol=1e-12)
    assert math.isclose(gof["p_value"], float(ref_gof.pvalue), rel_tol=1e-12)

    table = [[42, 18], [28, 32]]
    ind = run_chisq_test(ChiSqTestRequest(mode="independence", table=table, yates=False))
    ref_ind = stats.chi2_contingency(table, correction=False)
    assert math.isclose(ind["statistic"], float(ref_ind.statistic), rel_tol=1e-12)
    assert math.isclose(ind["p_value"], float(ref_ind.pvalue), rel_tol=1e-12)
    assert math.isclose(ind["effect_size"], math.sqrt(float(ref_ind.statistic) / 120.0), rel_tol=1e-12)


def test_one_way_anova_raw_matches_summary_and_scipy():
    g1 = [12.1, 13.0, 11.4, 12.8, 13.2]
    g2 = [14.5, 15.1, 13.9, 14.8, 15.6]
    g3 = [16.2, 17.0, 15.8, 16.5, 17.4]

    raw_res = run_anova_test(
        AnovaTestRequest(
            input_mode="raw",
            groups_raw=[
                {"label": "A", "values": " ".join(map(str, g1))},
                {"label": "B", "values": " ".join(map(str, g2))},
                {"label": "C", "values": " ".join(map(str, g3))},
            ],
        )
    )
    sum_res = run_anova_test(
        AnovaTestRequest(
            input_mode="summary",
            groups_summary=[
                AnovaGroupSummary(label="A", n=len(g1), mean=float(np.mean(g1)), sd=float(np.std(g1, ddof=1))),
                AnovaGroupSummary(label="B", n=len(g2), mean=float(np.mean(g2)), sd=float(np.std(g2, ddof=1))),
                AnovaGroupSummary(label="C", n=len(g3), mean=float(np.mean(g3)), sd=float(np.std(g3, ddof=1))),
            ],
        )
    )
    ref = stats.f_oneway(g1, g2, g3)
    assert math.isclose(raw_res["f_stat"], float(ref.statistic), rel_tol=1e-11)
    assert math.isclose(raw_res["p_value"], float(ref.pvalue), rel_tol=1e-11)
    assert math.isclose(raw_res["f_stat"], sum_res["f_stat"], rel_tol=1e-12)
    assert 0.0 < raw_res["eta_squared"] <= 1.0
