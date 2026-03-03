import re

from link_garden.web.sanitize import sanitize_html


def test_sanitizer_blocks_common_xss_payloads() -> None:
    payload = """
    <img src=x onerror=alert(1)>
    <svg onload=alert(1)><foreignObject><script>alert(1)</script></foreignObject></svg>
    <a href="data:text/html,<script>alert(1)</script>">data-link</a>
    <a href="JaVaScRiPt:alert(1)">js-link</a>
    <a href="jav&#x61;script:alert(1)">entity-js-link</a>
    <p style="background:url(javascript:alert(1))" onclick="alert(1)">styled</p>
    """
    sanitized = sanitize_html(payload).lower()

    assert "<script" not in sanitized
    assert "<svg" not in sanitized
    assert "<foreignobject" not in sanitized
    assert "javascript:" not in sanitized
    assert "data:text/html" not in sanitized
    assert "style=" not in sanitized
    assert not re.search(r"\son[a-z]+=", sanitized)


def test_sanitizer_keeps_safe_https_anchor() -> None:
    sanitized = sanitize_html('<a href="https://example.com/docs" title="Doc">docs</a>').lower()
    assert 'href="https://example.com/docs"' in sanitized
    assert 'title="doc"' in sanitized
    assert "rel=" in sanitized
    assert "target=" in sanitized

