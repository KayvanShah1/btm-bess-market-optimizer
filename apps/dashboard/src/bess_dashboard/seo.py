from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

SEO_SITE_NAME = "BESS Market Optimizer"
SEO_PAGE_TITLE = "BESS Market Optimizer | Battery Revenue Dashboard"
SEO_DESCRIPTION = (
    "Analyze behind-the-meter battery dispatch, FCR-N, mFRR, PV, load, and break-even revenue "
    "scenarios for a representative Swedish SE3 site."
)
SEO_KEYWORDS = (
    "BESS optimizer, behind-the-meter battery, battery dispatch, FCR-N, mFRR, "
    "battery revenue, Swedish electricity market, SE3"
)

SEO_START_MARKER = "<!-- bess-dashboard-seo:start -->"
SEO_END_MARKER = "<!-- bess-dashboard-seo:end -->"

_SEO_BLOCK_RE = re.compile(
    rf"\s*{re.escape(SEO_START_MARKER)}.*?{re.escape(SEO_END_MARKER)}\s*",
    re.DOTALL,
)
_TITLE_RE = re.compile(r"<title>.*?</title>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class SeoMetadata:
    title: str = SEO_PAGE_TITLE
    description: str = SEO_DESCRIPTION
    site_name: str = SEO_SITE_NAME
    keywords: str = SEO_KEYWORDS
    public_url: str | None = None
    image_url: str | None = None


def metadata_from_env(environ: Mapping[str, str] | None = None) -> SeoMetadata:
    env = os.environ if environ is None else environ
    return SeoMetadata(
        title=env.get("BESS_DASHBOARD_SEO_TITLE", SEO_PAGE_TITLE).strip() or SEO_PAGE_TITLE,
        description=env.get("BESS_DASHBOARD_SEO_DESCRIPTION", SEO_DESCRIPTION).strip() or SEO_DESCRIPTION,
        site_name=env.get("BESS_DASHBOARD_SEO_SITE_NAME", SEO_SITE_NAME).strip() or SEO_SITE_NAME,
        keywords=env.get("BESS_DASHBOARD_SEO_KEYWORDS", SEO_KEYWORDS).strip() or SEO_KEYWORDS,
        public_url=_clean_url(env.get("BESS_DASHBOARD_PUBLIC_URL")),
        image_url=_clean_url(env.get("BESS_DASHBOARD_IMAGE_URL")),
    )


def streamlit_index_path() -> Path:
    import streamlit

    return Path(streamlit.__file__).resolve().parent / "static" / "index.html"


def patch_streamlit_static_index(metadata: SeoMetadata | None = None) -> bool:
    index_path = streamlit_index_path()
    original_html = index_path.read_text(encoding="utf-8")
    patched_html = patch_index_html(original_html, metadata or metadata_from_env())

    if patched_html == original_html:
        return False

    index_path.write_text(patched_html, encoding="utf-8")
    return True


def patch_index_html(index_html: str, metadata: SeoMetadata) -> str:
    index_html = _SEO_BLOCK_RE.sub("", index_html)
    title_tag = f"<title>{_escape(metadata.title)}</title>"

    if _TITLE_RE.search(index_html):
        patched = _TITLE_RE.sub(title_tag, index_html, count=1)
    else:
        patched = index_html.replace("</head>", f"    {title_tag}\n  </head>", 1)

    seo_block = build_seo_head_block(metadata)
    return patched.replace(title_tag, f"{title_tag}\n\n{seo_block}\n", 1)


def build_seo_head_block(metadata: SeoMetadata) -> str:
    tags = [
        SEO_START_MARKER,
        f'<meta name="description" content="{_escape(metadata.description)}" />',
        f'<meta name="keywords" content="{_escape(metadata.keywords)}" />',
        '<meta name="robots" content="index, follow" />',
        '<meta property="og:type" content="website" />',
        f'<meta property="og:site_name" content="{_escape(metadata.site_name)}" />',
        f'<meta property="og:title" content="{_escape(metadata.title)}" />',
        f'<meta property="og:description" content="{_escape(metadata.description)}" />',
        '<meta name="twitter:card" content="summary" />',
        f'<meta name="twitter:title" content="{_escape(metadata.title)}" />',
        f'<meta name="twitter:description" content="{_escape(metadata.description)}" />',
    ]

    if metadata.public_url:
        tags.extend(
            [
                f'<link rel="canonical" href="{_escape(metadata.public_url)}" />',
                f'<meta property="og:url" content="{_escape(metadata.public_url)}" />',
            ]
        )

    if metadata.image_url:
        tags.extend(
            [
                f'<meta property="og:image" content="{_escape(metadata.image_url)}" />',
                f'<meta name="twitter:image" content="{_escape(metadata.image_url)}" />',
            ]
        )

    tags.append(_structured_data_script(metadata))
    tags.append(SEO_END_MARKER)
    return "\n".join(f"    {tag}" for tag in tags)


def _structured_data_script(metadata: SeoMetadata) -> str:
    structured_data: dict[str, str] = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": metadata.site_name,
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "description": metadata.description,
    }

    if metadata.public_url:
        structured_data["url"] = metadata.public_url

    payload = json.dumps(structured_data, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


def _clean_url(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value.strip()
    return cleaned or None


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def main() -> None:
    patch_streamlit_static_index()


if __name__ == "__main__":
    main()
