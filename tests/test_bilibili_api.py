import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from spider.bilibili_api import parse_duration


@pytest.mark.parametrize(
    "duration, expected",
    [
        ("05:30", 330),
        ("1:02:03", 3723),
        ("90", 90),
        (0, 0),
    ],
)
def test_parse_duration_handles_common_formats(duration, expected):
    assert parse_duration(duration) == expected


def test_parse_duration_returns_zero_for_invalid_input():
    assert parse_duration("not-a-time") == 0
