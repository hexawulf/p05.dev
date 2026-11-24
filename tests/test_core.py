"""Unit tests for pure probability & inequality functions in app.dlbdss_core."""

import math

import pytest

from app import dlbdss_core as core


def test_normal_functions():
    assert math.isclose(core.norm_cdf(1.96, 0.0, 1.0), 0.9750021048517795, rel_tol=1e-9)
    assert math.isclose(core.norm_inv(0.975, 0.0, 1.0), 1.959963984540054, rel_tol=1e-9)
    assert math.isclose(core.norm_pdf(0.0, 0.0, 1.0), 1.0 / math.sqrt(2.0 * math.pi), rel_tol=1e-9)
    assert math.isclose(core.norm_interval(-1.96, 1.96, 0.0, 1.0), 0.950004209703559, rel_tol=1e-9)
    # reversed bounds swap automatically
    assert math.isclose(core.norm_interval(1.96, -1.96, 0.0, 1.0), core.norm_interval(-1.96, 1.96, 0.0, 1.0))

    with pytest.raises(ValueError):
        core.norm_cdf(0.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        core.norm_inv(1.0, 0.0, 1.0)
    with pytest.raises(ValueError):
        core.norm_cdf(float("nan"), 0.0, 1.0)


def test_binomial_functions():
    assert math.isclose(core.binom_pmf(20, 0.5, 10), 0.17619705200195307, rel_tol=1e-9)
    assert math.isclose(core.binom_cdf(20, 0.5, 10), 0.5880985260009766, rel_tol=1e-9)
    assert math.isclose(core.binom_cdf_range(20, 0.5, 8, 12), 0.7368240356445312, rel_tol=1e-9)
    assert math.isclose(core.binom_atmost(20, 0.5, 12), core.binom_cdf(20, 0.5, 12), rel_tol=1e-9)
    assert math.isclose(core.binom_atleast(20, 0.5, 0), 1.0)
    assert math.isclose(
        core.binom_atmost(20, 0.5, 7) + core.binom_atleast(20, 0.5, 8), 1.0, rel_tol=1e-12
    )
    assert math.isclose(core.binom_between(20, 0.5, 8, 12), core.binom_cdf_range(20, 0.5, 8, 12), rel_tol=1e-9)

    with pytest.raises(ValueError):
        core.binom_pmf(0, 0.5, 0)
    with pytest.raises(ValueError):
        core.binom_between(10, 0.5, 8, 3)


def test_poisson_functions():
    assert math.isclose(core.pois_pmf(3.0, 2), math.exp(-3.0) * 9.0 / 2.0, rel_tol=1e-9)
    assert math.isclose(core.pois_cdf(3.0, 2), sum(core.pois_pmf(3.0, k) for k in range(3)), rel_tol=1e-9)
    assert math.isclose(core.pois_atleast(3.0, 0), 1.0)
    assert math.isclose(core.pois_cdf(3.0, 2) + core.pois_atleast(3.0, 3), 1.0, rel_tol=1e-12)
    assert math.isclose(core.pois_between(3.0, 1, 3), sum(core.pois_pmf(3.0, k) for k in range(1, 4)), rel_tol=1e-9)

    with pytest.raises(ValueError):
        core.pois_pmf(0.0, 1)


def test_geometric_exponential_uniform():
    # Geometric: k = failures before 1st success (0-indexed)
    assert math.isclose(core.geom_pmf(0.3, 0), 0.3, rel_tol=1e-12)
    assert math.isclose(core.geom_pmf(0.3, 2), 0.7**2 * 0.3, rel_tol=1e-12)
    assert math.isclose(core.geom_cdf(0.3, 2), sum(core.geom_pmf(0.3, k) for k in range(3)), rel_tol=1e-12)

    # Exponential
    assert math.isclose(core.exp_pdf(0.5, 2.0), 0.5 * math.exp(-1.0), rel_tol=1e-12)
    assert math.isclose(core.exp_cdf(0.5, 2.0), 1.0 - math.exp(-1.0), rel_tol=1e-12)
    q = core.exp_inv(0.5, 0.5)
    assert math.isclose(core.exp_cdf(0.5, q), 0.5, rel_tol=1e-12)

    # Uniform
    assert math.isclose(core.unif_pdf(0.0, 10.0, 4.0), 0.1, rel_tol=1e-12)
    assert core.unif_pdf(0.0, 10.0, 12.0) == 0.0
    assert math.isclose(core.unif_cdf(0.0, 10.0, 4.0), 0.4, rel_tol=1e-12)

    with pytest.raises(ValueError):
        core.unif_cdf(5.0, 5.0, 5.0)
    with pytest.raises(ValueError):
        core.exp_cdf(0.5, -1.0)


def test_clt_and_inequalities():
    assert math.isclose(core.clt(50.0, 10.0, 36, 48.0, 54.0), 0.8767327938536956, rel_tol=1e-9)
    mk = core.markov_bound(40.0, 240.0)
    assert math.isclose(mk["bound"], 40.0 / 240.0, rel_tol=1e-12)
    assert mk["trivial"] is False

    ch = core.chebyshev_bound(2.0, 6.0)
    assert math.isclose(ch["outer_bound"], 1.0 / 9.0, rel_tol=1e-12)
    assert math.isclose(ch["inner_bound"], 8.0 / 9.0, rel_tol=1e-12)
    assert math.isclose(ch["k_sigmas"], 3.0, rel_tol=1e-12)
