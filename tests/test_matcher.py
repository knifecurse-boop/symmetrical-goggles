from audio_clipper.matcher import match_all
from audio_clipper.models import Segment, Token


def _tokens_from_text(text: str, start: float = 0.0, step: float = 0.2) -> list[Token]:
    """把一串文字拆成逐字 token，每個字佔 `step` 秒，模擬語音辨識輸出。"""
    tokens = []
    t = start
    for ch in text:
        tokens.append(Token(text=ch, start=t, end=t + step))
        t += step
    return tokens


def test_matches_exact_substring():
    full_text = "大家好歡迎收看今天的節目我們要分享三個技巧謝謝大家收看"
    tokens = _tokens_from_text(full_text)

    segments = [Segment(output_name="a.mp3", text="我們要分享三個技巧")]
    results = match_all(tokens, segments)

    assert len(results) == 1
    r = results[0]
    assert r.score > 95

    expected_start_idx = full_text.index("我們要分享三個技巧")
    expected_end_idx = expected_start_idx + len("我們要分享三個技巧") - 1
    assert abs(r.start - tokens[expected_start_idx].start) < 1e-6
    assert abs(r.end - tokens[expected_end_idx].end) < 1e-6


def test_tolerates_minor_asr_errors():
    # 模擬語音辨識把「三」誤認成「山」的情況，比對仍應找到合理範圍且分數不會太低。
    full_text = "大家好歡迎收看今天的節目我們要分享山個技巧謝謝大家收看"
    tokens = _tokens_from_text(full_text)

    segments = [Segment(output_name="a.mp3", text="我們要分享三個技巧")]
    results = match_all(tokens, segments)

    r = results[0]
    assert r.score > 70
    assert r.start < r.end


def test_multiple_segments_in_order():
    full_text = "第一段的內容在這裡第二段的內容在這裡第三段的內容在這裡"
    tokens = _tokens_from_text(full_text)

    segments = [
        Segment(output_name="1.mp3", text="第一段的內容在這裡"),
        Segment(output_name="2.mp3", text="第二段的內容在這裡"),
        Segment(output_name="3.mp3", text="第三段的內容在這裡"),
    ]
    results = match_all(tokens, segments)

    assert len(results) == 3
    assert results[0].start < results[1].start < results[2].start
    for r in results:
        assert r.score > 95
