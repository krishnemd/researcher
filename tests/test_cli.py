import pytest

from researcher.cli import parse_time


@pytest.mark.parametrize(
    "text,expected",
    [
        ("90s", 90),
        ("30m", 1800),
        ("1h", 3600),
        ("5 min", 300),
        ("2hours", 7200),
    ],
)
def test_parse_time_valid(text: str, expected: int) -> None:
    assert parse_time(text) == expected


@pytest.mark.parametrize("text", ["", "tomorrow", "1d", "3", "2weeks"])
def test_parse_time_invalid(text: str) -> None:
    with pytest.raises(Exception):
        parse_time(text)
