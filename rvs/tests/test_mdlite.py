from rvs_core.exporters.mdlite import Bullets, Para, parse, plain


def test_paragraphs_and_inline_styles():
    blocks = parse("The system **shall** use *italic* and `code`.\n\nSecond paragraph.")
    assert [type(b) for b in blocks] == [Para, Para]
    assert blocks[0].spans == (
        ("The system ", ""),
        ("shall", "b"),
        (" use ", ""),
        ("italic", "i"),
        (" and ", ""),
        ("code", "code"),
        (".", ""),
    )
    assert plain(blocks[1].spans) == "Second paragraph."


def test_bullet_and_numbered_lists():
    blocks = parse("Intro\n\n- one\n- two **b**\n\n1. first\n2. second")
    assert isinstance(blocks[1], Bullets) and not blocks[1].ordered and len(blocks[1].items) == 2
    assert isinstance(blocks[2], Bullets) and blocks[2].ordered and plain(blocks[2].items[1]) == "second"


def test_soft_line_breaks_join_and_text_is_never_dropped():
    blocks = parse("line one\nline two")
    assert plain(blocks[0].spans) == "line one line two"
    assert parse("") == []


def test_unbalanced_markers_stay_literal_and_html_is_plain_text():
    (p,) = parse("a ** b and <script>alert(1)</script> and * lone")
    assert plain(p.spans) == "a ** b and <script>alert(1)</script> and * lone"


def test_placeholders_in_angle_brackets_survive():
    (p,) = parse("The system shall <describe the required behaviour>.")
    assert plain(p.spans) == "The system shall <describe the required behaviour>."
