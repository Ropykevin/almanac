"""HTML sanitization tests for the rich text editor."""

from app.utils.html_sanitize import sanitize_article_html


def test_strips_scripts_and_keeps_semantic_tags():
    dirty = (
        '<h2>Hello</h2><p>Safe <strong>text</strong></p>'
        '<script>alert(1)</script>'
        '<p onclick="evil()">Click</p>'
    )
    clean = sanitize_article_html(dirty)
    assert clean is not None
    assert "<h2>Hello</h2>" in clean
    assert "<strong>text</strong>" in clean
    assert "<script>" not in clean
    assert "onclick" not in clean
    assert "<p>Click</p>" in clean


def test_allows_trusted_video_iframe_only():
    good = sanitize_article_html(
        '<iframe src="https://www.youtube-nocookie.com/embed/abc123"></iframe>'
    )
    bad = sanitize_article_html('<iframe src="https://evil.example/embed"></iframe>')
    assert good is not None
    assert "youtube-nocookie.com" in good
    assert bad is None or "iframe" not in bad


def test_empty_editor_html_becomes_none():
    assert sanitize_article_html("<p><br></p>") is None
    assert sanitize_article_html("   ") is None


def test_preserves_footnotes_and_code():
    html = (
        '<p>Note<sup class="footnote-ref" id="fn-1-ref">'
        '<a href="#fn-1" role="doc-noteref">1</a></sup></p>'
        '<pre><code>print("hi")</code></pre>'
        '<aside class="footnotes" role="doc-endnotes"><ol>'
        '<li id="fn-1" role="doc-endnote">Source</li></ol></aside>'
    )
    clean = sanitize_article_html(html)
    assert clean is not None
    assert 'role="doc-noteref"' in clean
    assert "<aside" in clean
    assert "<code>" in clean
