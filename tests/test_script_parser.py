import pytest

from audio_clipper.script_parser import ScriptParseError, parse_script_text


def test_parses_multiple_segments():
    text = """
=== 01_intro.mp3 ===
這是第一段
還有第二行

=== 02_body.wav | padding=0.3 ===
這是第二段的內容
"""
    segments = parse_script_text(text)
    assert len(segments) == 2

    seg1 = segments[0]
    assert seg1.output_name == "01_intro.mp3"
    assert "這是第一段" in seg1.text
    assert seg1.padding is None

    seg2 = segments[1]
    assert seg2.output_name == "02_body.wav"
    assert seg2.padding == 0.3


def test_missing_extension_raises():
    text = "=== 01_intro ===\n內容\n"
    with pytest.raises(ScriptParseError):
        parse_script_text(text)


def test_duplicate_output_name_raises():
    text = """
=== a.mp3 ===
內容一

=== a.mp3 ===
內容二
"""
    with pytest.raises(ScriptParseError):
        parse_script_text(text)


def test_empty_body_raises():
    text = "=== a.mp3 ===\n\n=== b.mp3 ===\n有內容\n"
    with pytest.raises(ScriptParseError):
        parse_script_text(text)


def test_no_segments_raises():
    with pytest.raises(ScriptParseError):
        parse_script_text("隨便寫點東西，沒有任何標頭")


def test_text_before_first_header_raises():
    text = "亂入的文字\n=== a.mp3 ===\n內容\n"
    with pytest.raises(ScriptParseError):
        parse_script_text(text)


def test_invalid_option_raises():
    text = "=== a.mp3 | foo=1 ===\n內容\n"
    with pytest.raises(ScriptParseError):
        parse_script_text(text)
