"""Integration tests for FastAPI endpoints, PNG plots, security headers, and error handling."""

import io
import math

from fastapi.testclient import TestClient
from PIL import Image

from app.api import APP_VERSION, app

client = TestClient(app)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _assert_valid_png(resp):
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content.startswith(PNG_SIGNATURE)
    img = Image.open(io.BytesIO(resp.content))
    assert img.width > 100 and img.height > 100


def test_health_about_and_root():
    for method in ("get", "head"):
        r_root = getattr(client, method)("/")
        assert r_root.status_code == 200
        assert r_root.headers["x-content-type-options"] == "nosniff"
        assert r_root.headers["x-frame-options"] == "DENY"
        assert r_root.headers["referrer-policy"] == "no-referrer"
        assert "default-src 'self'" in r_root.headers["content-security-policy"]

        r_hz = getattr(client, method)("/healthz")
        assert r_hz.status_code == 200

    r_about = client.get("/about")
    assert r_about.status_code == 200
    assert r_about.json()["version"] == APP_VERSION


def test_numeric_endpoints():
    assert math.isclose(client.get("/api/norm/cdf?x=1.96&mu=0&sigma=1").json()["value"], 0.97500210485, rel_tol=1e-6)
    assert math.isclose(client.get("/api/norm/inv?p=0.975&mu=0&sigma=1").json()["value"], 1.95996398, rel_tol=1e-6)
    assert math.isclose(client.get("/api/norm/pdf?x=0&mu=0&sigma=1").json()["value"], 0.39894228, rel_tol=1e-6)
    assert math.isclose(
        client.get("/api/norm/interval?lower=-1.96&upper=1.96&mu=0&sigma=1").json()["value"], 0.9500042, rel_tol=1e-5
    )

    assert math.isclose(client.get("/api/binom/pmf?n=20&p=0.5&k=10").json()["value"], 0.17619705, rel_tol=1e-6)
    assert math.isclose(client.get("/api/binom/cdf?n=20&p=0.5&k=12").json()["value"], 0.868412, rel_tol=1e-5)
    assert math.isclose(client.get("/api/binom/cdf-range?n=20&p=0.5&kmin=8&kmax=12").json()["value"], 0.736824, rel_tol=1e-5)
    assert math.isclose(client.get("/api/binom/atmost?n=20&p=0.5&k=12").json()["value"], 0.868412, rel_tol=1e-5)
    assert math.isclose(client.get("/api/binom/atleast?n=20&p=0.5&k=8").json()["value"], 0.868412, rel_tol=1e-5)
    assert math.isclose(client.get("/api/binom/between?n=20&p=0.5&kmin=8&kmax=12").json()["value"], 0.736824, rel_tol=1e-5)

    assert math.isclose(client.get("/api/pois/pmf?lam=3&k=2").json()["value"], 0.2240418, rel_tol=1e-6)
    assert math.isclose(client.get("/api/pois/cdf?lam=3&k=2").json()["value"], 0.42319008, rel_tol=1e-6)
    assert math.isclose(client.get("/api/pois/atleast?lam=3&k=3").json()["value"], 1.0 - 0.42319008, rel_tol=1e-5)
    assert math.isclose(client.get("/api/pois/between?lam=3&kmin=1&kmax=3").json()["value"], 12.0 * math.exp(-3.0), rel_tol=1e-9)

    assert math.isclose(client.get("/api/geom/pmf?p=0.3&k=2").json()["value"], 0.147, rel_tol=1e-9)
    assert math.isclose(client.get("/api/geom/cdf?p=0.3&k=2").json()["value"], 0.657, rel_tol=1e-9)
    assert math.isclose(client.get("/api/exp/pdf?lam=0.5&x=2").json()["value"], 0.18393972, rel_tol=1e-6)
    assert math.isclose(client.get("/api/exp/cdf?lam=0.5&x=2").json()["value"], 0.63212056, rel_tol=1e-6)
    assert math.isclose(client.get("/api/exp/inv?lam=0.5&p=0.5").json()["value"], 2.0 * math.log(2.0), rel_tol=1e-6)
    assert math.isclose(client.get("/api/unif/pdf?a=0&b=10&x=4").json()["value"], 0.1, rel_tol=1e-9)
    assert math.isclose(client.get("/api/unif/cdf?a=0&b=10&x=4").json()["value"], 0.4, rel_tol=1e-9)

    assert math.isclose(client.get("/api/clt?mu=50&sigma=10&n=36&lower=48&upper=54").json()["value"], 0.87673279, rel_tol=1e-6)
    assert math.isclose(client.get("/api/ineq/markov?mean=40&t=240").json()["bound"], 40.0 / 240.0, rel_tol=1e-9)
    assert math.isclose(client.get("/api/ineq/chebyshev?sigma=2&t=6").json()["inner_bound"], 8.0 / 9.0, rel_tol=1e-9)


def test_joint_endpoint_and_conditionals():
    r = client.get("/api/joint?pairs=0,0,0.1;0,1,0.2;1,0,0.3;1,1,0.4")
    assert r.status_code == 200
    data = r.json()
    assert data["independent"] is False
    assert math.isclose(data["Corr"], -0.08908708063747488, rel_tol=1e-6)
    assert "conditionals" in data
    assert math.isclose(data["conditionals"]["X_given_Y"]["0"]["1"], 0.75, rel_tol=1e-9)

    # Independent distribution
    r_ind = client.get("/api/joint?pairs=0,0,0.25;0,1,0.25;1,0,0.25;1,1,0.25")
    assert r_ind.status_code == 200
    assert r_ind.json()["independent"] is True

    # Invalid sum != 1
    assert client.get("/api/joint?pairs=0,0,0.5;1,1,0.2").status_code == 400
    # Negative probability
    assert client.get("/api/joint?pairs=0,0,-0.1;1,1,1.1").status_code == 400


def test_all_png_plot_endpoints_light_and_dark():
    urls = [
        "/plot/pdf/normal?mu=0&sigma=1",
        "/plot/png/normal?mu=0&sigma=1&shade_low=-1.96&shade_high=1.96",
        "/plot/sim/poisson?n=1000&lam=3&bins=20",
        "/plot/png/poisson_sim?n=1000&lam=3&bins=20",
        "/plot/sim/binom?n=1000&N=20&p=0.5&bins=20",
        "/plot/png/binomial_sim?n=1000&N=20&p=0.5&bins=20",
        "/plot/pmf/poisson?lam=3&highlight_k=2",
        "/plot/png/poisson_pmf?lam=3&highlight_min=1&highlight_max=4",
        "/plot/png/poisson_cdf?lam=3&highlight_k=2",
        "/plot/pmf/binom?n=20&p=0.5&highlight_k=10",
        "/plot/png/binomial_pmf?n=20&p=0.5&highlight_min=8&highlight_max=12",
        "/plot/cdf/binom?n=20&p=0.5&highlight_k=12",
        "/plot/png/binomial_cdf?n=20&p=0.5",
        "/plot/png/geometric_pmf?p=0.3&kmax=15&highlight_k=2",
        "/plot/png/exponential_pdf?lam=0.5&highlight_x=2",
        "/plot/png/exponential_cdf?lam=0.5&highlight_x=2",
        "/plot/png/uniform_pdf?a=0&b=10&highlight_x=4",
        "/plot/png/uniform_cdf?a=0&b=10&highlight_x=4",
        "/plot/clt?mu=50&sigma=10&n=36&lower=48&upper=54",
        "/plot/png/clt?mu=50&sigma=10&n=36&lower=48&upper=54",
        "/plot/heat/joint?pairs=0,0,0.1;0,1,0.2;1,0,0.3;1,1,0.4",
        "/plot/png/joint_discrete?pairs=0,0,0.1;0,1,0.2;1,0,0.3;1,1,0.4",
    ]
    for url in urls:
        _assert_valid_png(client.get(f"{url}&theme=light"))
        _assert_valid_png(client.get(f"{url}&theme=dark"))


def test_plot_validation_and_dos_caps():
    assert client.get("/plot/png/normal?mu=0&sigma=-1").status_code == 400
    assert client.get("/plot/png/uniform_pdf?a=5&b=5").status_code == 400
    assert client.get("/plot/png/uniform_cdf?a=10&b=2").status_code == 400
    assert client.get("/plot/png/poisson_sim?n=9999999&lam=3").status_code == 400
    assert client.get("/plot/png/binomial_sim?n=9999999&N=20&p=0.5").status_code == 400
    assert client.get("/plot/png/binomial_pmf?n=999999&p=0.5").status_code == 400
    assert client.get("/plot/png/geometric_pmf?p=0&kmax=10").status_code == 422
    assert client.get("/plot/png/joint_discrete?pairs=0,0,0.3;1,1,0.3").status_code == 400
    assert client.get("/plot/png/clt?mu=50&sigma=-2&n=36&lower=48&upper=54").status_code == 400
