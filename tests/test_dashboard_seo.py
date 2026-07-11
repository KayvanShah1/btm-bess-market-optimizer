from __future__ import annotations

from bess_dashboard.seo import SEO_DESCRIPTION, SEO_PAGE_TITLE, SeoMetadata, patch_index_html


def test_patch_index_html_adds_static_seo_metadata() -> None:
    index_html = "<!doctype html><html><head><title>Streamlit</title></head><body></body></html>"
    metadata = SeoMetadata(
        public_url="https://btm-bess-market-optimizer.onrender.com",
        image_url="https://btm-bess-market-optimizer.onrender.com/preview.png",
    )

    patched = patch_index_html(index_html, metadata)

    assert f"<title>{SEO_PAGE_TITLE}</title>" in patched
    assert f'<meta name="description" content="{SEO_DESCRIPTION}" />' in patched
    assert '<link rel="canonical" href="https://btm-bess-market-optimizer.onrender.com" />' in patched
    assert '<meta property="og:url" content="https://btm-bess-market-optimizer.onrender.com" />' in patched
    assert '<meta property="og:image" content="https://btm-bess-market-optimizer.onrender.com/preview.png" />' in patched
    assert '"@type":"WebApplication"' in patched


def test_patch_index_html_is_idempotent() -> None:
    index_html = "<!doctype html><html><head><title>Streamlit</title></head><body></body></html>"
    metadata = SeoMetadata(public_url="https://btm-bess-market-optimizer.onrender.com")

    patched_once = patch_index_html(index_html, metadata)
    patched_twice = patch_index_html(patched_once, metadata)

    assert patched_once == patched_twice
    assert patched_once.count("bess-dashboard-seo:start") == 1
