"""API v2 integration tests, OpenAPI tag checks, PNG export, CSP hygiene, and WCAG contrast gate."""

import io
import re
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.api import APP_VERSION, app

client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parent.parent
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _srgb_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _srgb_luminance(fg)
    l2 = _srgb_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def test_wcag_aa_contrast_all_theme_pairs():
    pairs = [
        ("#0F172A", "#FFFFFF"),
        ("#0F172A", "#FAFAFA"),
        ("#475569", "#FFFFFF"),
        ("#475569", "#FAFAFA"),
        ("#0F766E", "#FFFFFF"),
        ("#0F766E", "#FAFAFA"),
        ("#FFFFFF", "#0F766E"),
        ("#FFFFFF", "#115E59"),
        ("#F8FAFC", "#13151A"),
        ("#F8FAFC", "#0B0C0E"),
        ("#94A3B8", "#13151A"),
        ("#94A3B8", "#0B0C0E"),
        ("#2DD4BF", "#13151A"),
        ("#2DD4BF", "#0B0C0E"),
        ("#5EEAD4", "#13151A"),
    ]
    for fg, bg in pairs:
        ratio = _contrast_ratio(fg, bg)
        assert ratio >= 4.5, f"Contrast {fg} on {bg} is {ratio:.2f} < 4.5"


def test_static_csp_hygiene():
    html = (REPO_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'\sstyle\s*=', html, re.IGNORECASE), "Inline style= attribute forbidden by CSP"
    assert "<style" not in html.lower(), "Inline <style> block forbidden by CSP"
    assert "data:image/" not in html.lower(), "data:image URI forbidden by CSP"
    for m in re.finditer(r"<script([^>]*)>(.*?)</script>", html, re.IGNORECASE | re.DOTALL):
        attrs, body = m.group(1), m.group(2)
        assert "src=" in attrs.lower(), "Inline <script> without src forbidden by CSP"
        assert body.strip() == "", "Script tag with src must not contain inline code"

    for js_file in (REPO_ROOT / "static" / "js").rglob("*.js"):
        src = js_file.read_text(encoding="utf-8")
        assert ".style." not in src, f"DOM .style mutation forbidden in {js_file}"
        assert 'setAttribute("style"' not in src and "setAttribute('style'" not in src
        assert "cssText" not in src
        assert "data:image/" not in src


def test_openapi_tags_docs_and_favicon():
    r_docs = client.get("/docs")
    assert r_docs.status_code == 200
    r_schema = client.get("/openapi.json")
    assert r_schema.status_code == 200
    schema = r_schema.json()
    assert schema["info"]["version"] == APP_VERSION
    assert "p05.dev" in schema["info"]["title"]
    tag_names = {t["name"] for t in schema.get("tags", [])}
    assert {
        "v2 Distributions",
        "v2 Hypothesis Tests",
        "v2 Data & Fitting",
        "v2 Simulators",
        "v1 Legacy",
        "System",
    } <= tag_names

    r_fav = client.get("/favicon.ico", follow_redirects=False)
    assert r_fav.status_code == 302
    assert r_fav.headers["location"] == "/static/favicon.svg"
    assert client.get("/static/favicon.svg").status_code == 200
    assert client.get("/static/css/workbench.css").status_code == 200
    assert client.get("/static/js/main.js").status_code == 200


def test_v2_http_endpoints_and_png_export():
    assert client.get("/api/v2/dist/catalog").status_code == 200
    r_eval = client.post(
        "/api/v2/dist/evaluate",
        json={"dist": "normal", "params": {"mu": 0, "sigma": 1}, "region": "two_tailed", "a": -1.96, "b": 1.96},
    )
    assert r_eval.status_code == 200
    assert 0.049 < r_eval.json()["probability"] < 0.051

    # Invalid domain returns clean 400
    r_bad = client.post(
        "/api/v2/dist/evaluate",
        json={"dist": "normal", "params": {"mu": 0, "sigma": -1}, "region": "left", "a": 0},
    )
    assert r_bad.status_code == 400

    # Extra unknown field returns 422
    r_extra = client.post("/api/v2/dist/evaluate", json={"dist": "normal", "unknown_field": 1})
    assert r_extra.status_code == 422

    # Export 2x Retina PNG across curve, histogram, scatter, and heatmap in light & dark
    specs = [
        {
            "kind": "curve",
            "title": "Normal",
            "payload": {"family": "continuous", "curves": [{"label": "N(0,1)", "x": [-2, 0, 2], "y": [0.05, 0.4, 0.05]}]},
        },
        {
            "kind": "histogram",
            "title": "Hist",
            "payload": {"edges": [0, 1, 2, 3], "densities": [0.2, 0.5, 0.3], "curves": []},
        },
        {
            "kind": "scatter",
            "title": "Q-Q",
            "payload": {"x": [-1, 0, 1], "y": [-1.1, 0.1, 0.9], "ref_line": {"x": [-1, 1], "y": [-1, 1]}},
        },
        {
            "kind": "heatmap",
            "title": "Joint",
            "payload": {"x_values": [0, 1], "y_values": [0, 1], "matrix": [[0.1, 0.2], [0.3, 0.4]]},
        },
    ]
    for theme in ("light", "dark"):
        for spec in specs:
            resp = client.post("/api/v2/export/png", json={**spec, "theme": theme})
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/png"
            assert resp.content.startswith(PNG_SIGNATURE)
            img = Image.open(io.BytesIO(resp.content))
            assert img.width > 800 and img.height > 600
