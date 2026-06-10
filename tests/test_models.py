import pytest

from photo_flow.models import OutputFormat, format_extension


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("heic", OutputFormat.HEIC),
        ("jpg", OutputFormat.JPG),
        ("jpeg", OutputFormat.JPG),
        ("png", OutputFormat.PNG),
        ("jxl", OutputFormat.JXL),
    ],
)
def test_output_format_accepts_supported_values(value, expected):
    assert OutputFormat.parse(value) == expected


def test_output_format_rejects_unknown_value():
    with pytest.raises(ValueError, match="Unsupported output format"):
        OutputFormat.parse("gif")


def test_format_extension_maps_to_expected_suffix():
    assert format_extension(OutputFormat.HEIC) == ".heic"
    assert format_extension(OutputFormat.JPG) == ".jpg"
    assert format_extension(OutputFormat.PNG) == ".png"
    assert format_extension(OutputFormat.JXL) == ".jxl"
