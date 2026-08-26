"""Targeted tests for the deterministic Markdown -> Blogger HTML converter."""

from app.services.html_converter import markdown_to_blogger_html


def test_headings_demoted_to_h2_and_h3():
    html = markdown_to_blogger_html("# Title\n\n## Section\n\n### Sub")
    assert "<h2>Title</h2>" in html
    assert "<h3>Section</h3>" in html
    assert "<h3>Sub</h3>" in html


def test_paragraphs_and_hard_line_breaks():
    html = markdown_to_blogger_html("First paragraph.\n\nSecond paragraph with\nhard break.")
    assert "<p>First paragraph.</p>" in html
    assert "<p>Second paragraph with<br>hard break.</p>" in html


def test_bold_and_italic():
    html = markdown_to_blogger_html("This is **bold** and *italic* and __also bold__.")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<strong>also bold</strong>" in html


def test_bullet_and_numbered_lists():
    html = markdown_to_blogger_html("- one\n- two\n\n1. first\n2. second")
    assert "<ul><li>one</li><li>two</li></ul>" in html
    assert "<ol><li>first</li><li>second</li></ol>" in html


def test_horizontal_rule():
    html = markdown_to_blogger_html("before\n\n---\n\nafter")
    assert "<hr>" in html


def test_full_document_converts_to_expected_html():
    md = (
        "## Overview\n\n"
        "This is **bold** and *italic* text.\n\n"
        "- first\n- second\n\n"
        "1. one\n2. two\n\n"
        "---\n\n"
        "Final paragraph with\nline break.\n"
    )
    expected = (
        "<h3>Overview</h3>\n"
        "<p>This is <strong>bold</strong> and <em>italic</em> text.</p>\n"
        "<ul><li>first</li><li>second</li></ul>\n"
        "<ol><li>one</li><li>two</li></ol>\n"
        "<hr>\n"
        "<p>Final paragraph with<br>line break.</p>"
    )
    assert markdown_to_blogger_html(md) == expected


def test_raw_html_is_escaped():
    html = markdown_to_blogger_html("Use <script>alert(1)</script> with care.")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
