from app.core.subtitle import parse_srt, dump_srt, timestamp_to_ms, ms_to_timestamp


def test_timestamp_roundtrip():
    assert timestamp_to_ms("01:02:03,456") == 3723456
    assert ms_to_timestamp(3723456) == "01:02:03,456"


def test_srt_parse_dump():
    src = """1\n00:00:01,000 --> 00:00:03,000\naku nggak mau\n\n2\n00:00:03,100 --> 00:00:05,000\nkenapa kamu pergi\n"""
    items = parse_srt(src)
    assert len(items) == 2
    assert items[0].text == "aku nggak mau"
    out = dump_srt(items)
    assert "aku nggak mau" in out
    assert "00:00:03,100" in out
