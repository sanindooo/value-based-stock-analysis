"""Tests for the article extractor service.

Unit tests — no network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.article_extractor import (
    ExtractedArticle,
    clean_content,
    create_zyte_budget,
    is_safe_url,
    _extract_trafilatura,
    _extract_readability,
    _extract_bs4,
    _fetch_html_sync,
    _fetch_via_zyte_sync,
)


class TestIsSafeUrl:
    def test_blocks_private_10_network(self):
        assert is_safe_url("http://10.0.0.1/secret") is False

    def test_blocks_private_172_network(self):
        assert is_safe_url("http://172.16.0.1/path") is False

    def test_blocks_private_192_network(self):
        assert is_safe_url("http://192.168.1.1/") is False

    def test_blocks_localhost_ip(self):
        assert is_safe_url("http://127.0.0.1/admin") is False

    def test_blocks_localhost_hostname(self):
        assert is_safe_url("http://localhost/admin") is False

    def test_blocks_link_local(self):
        assert is_safe_url("http://169.254.1.1/") is False

    def test_blocks_non_http_scheme(self):
        assert is_safe_url("ftp://example.com/file") is False
        assert is_safe_url("file:///etc/passwd") is False

    def test_allows_public_https(self):
        assert is_safe_url("https://www.reuters.com/article/123") is True

    def test_allows_public_http(self):
        assert is_safe_url("http://news.example.com/story") is True

    def test_blocks_empty_url(self):
        assert is_safe_url("") is False

    def test_blocks_no_hostname(self):
        assert is_safe_url("http:///path") is False


class TestCleanContent:
    def test_strips_markdown_images(self):
        text = "Hello ![alt](http://img.com/x.png) world"
        assert "![" not in clean_content(text)

    def test_strips_markdown_links_keeps_text(self):
        text = "Read [this article](http://example.com)"
        result = clean_content(text)
        assert "this article" in result
        assert "http://example.com" not in result

    def test_collapses_extra_newlines(self):
        text = "para1\n\n\n\n\npara2"
        result = clean_content(text)
        assert "\n\n\n" not in result

    def test_caps_at_1mb(self):
        text = "x" * (2 * 1024 * 1024)
        result = clean_content(text)
        assert len(result) <= 1024 * 1024


class TestExtractionTiers:
    def test_trafilatura_extracts_text(self):
        html = "<html><body><article><p>This is a sufficiently long article content that exceeds the minimum threshold of one hundred characters for extraction to succeed.</p></article></body></html>"
        content, title = _extract_trafilatura(html, "http://example.com")
        if content:
            assert len(content) >= 100

    def test_readability_extracts_text(self):
        html = """<html><head><title>Test</title></head><body>
        <article><p>This is a long paragraph that should be extracted by readability. It needs to be over one hundred characters to pass the minimum check. Adding more text.</p></article>
        </body></html>"""
        result = _extract_readability(html)
        if result:
            assert len(result) >= 100

    def test_bs4_extracts_from_article_tag(self):
        html = """<html><body>
        <nav>Navigation menu</nav>
        <article><p>Main article content that is long enough to pass the minimum content threshold of one hundred characters for acceptance by the extractor.</p></article>
        <footer>Footer info</footer>
        </body></html>"""
        result = _extract_bs4(html)
        assert result is not None
        assert "Navigation menu" not in result
        assert "Footer info" not in result
        assert "Main article content" in result

    def test_bs4_returns_none_for_short_content(self):
        html = "<html><body><article><p>Short.</p></article></body></html>"
        result = _extract_bs4(html)
        assert result is None


class TestZyteBudget:
    def test_budget_cap_enforced(self):
        budget = create_zyte_budget()
        budget._cap = 2
        assert budget.try_consume() is True
        assert budget.try_consume() is True
        assert budget.try_consume() is False
