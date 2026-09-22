# tests/test_articles.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import articles


@pytest.mark.parametrize(
    "num,slug",
    [("306", "306"), ("308_2", "308-2"), ("117_2_2", "117-2-2")],
)
def test_article_slug(num, slug):
    assert articles.article_slug(num) == slug


def test_article_slug_rejects_a_range_num():
    # 753:754 is e-Gov's element id for "第七百五十三条及び第七百五十四条", not an
    # article number. Nobody searches for it, and it must never become a URL.
    with pytest.raises(ValueError):
        articles.article_slug("753:754")


@pytest.mark.parametrize(
    "num,shown",
    [("306", "第306条"), ("308_2", "第308条の2"), ("117_2_2", "第117条の2の2")],
)
def test_display_num(num, shown):
    assert articles.display_num(num) == shown


def test_range_members():
    assert articles.range_members("753:754") == ["753", "754"]


def test_range_members_rejects_a_non_numeric_endpoint():
    with pytest.raises(ValueError):
        articles.range_members("753:754_2")
