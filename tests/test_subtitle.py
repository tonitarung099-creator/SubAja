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


def test_srt_rejects_malformed_block_instead_of_silently_dropping_it():
    src = """1
00:00:01,000 --> 00:00:02,000
aman

2
TIMING RUSAK
jangan hilang diam-diam

3
00:00:03,000 --> 00:00:04,000
aman lagi
"""
    try:
        parse_srt(src)
    except ValueError as exc:
        assert "Blok SRT #2" in str(exc)
    else:
        raise AssertionError("Malformed SRT block harus ditolak.")
