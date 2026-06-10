from pathlib import Path

import pytest

from photo_flow.converter import ConversionError, build_conversion_command, build_conversion_plans
from photo_flow.models import ConversionPlan, OutputFormat


def test_build_conversion_plans_uses_exact_basename_and_extension(tmp_path):
    source = tmp_path / "tiff" / "DSC0001.tif"
    source.parent.mkdir()
    source.write_bytes(b"tiff")
    output_dir = tmp_path / "converted"
    output_dir.mkdir()

    plans = build_conversion_plans(
        (source,),
        output_dir=output_dir,
        output_format=OutputFormat.HEIC,
        quality=90,
        overwrite=False,
    )

    assert plans == (
        ConversionPlan(source, output_dir / "DSC0001.heic", OutputFormat.HEIC, 90),
    )


def test_build_conversion_plans_refuses_existing_output_without_overwrite(tmp_path):
    source = tmp_path / "DSC0001.tif"
    output = tmp_path / "converted" / "DSC0001.jpg"
    source.write_bytes(b"tiff")
    output.parent.mkdir()
    output.write_bytes(b"existing")

    with pytest.raises(ConversionError, match="Output file already exists"):
        build_conversion_plans(
            (source,),
            output_dir=output.parent,
            output_format=OutputFormat.JPG,
            quality=85,
            overwrite=False,
        )


def test_build_heic_command_uses_magick_quality():
    plan = ConversionPlan(Path("in.tif"), Path("out.heic"), OutputFormat.HEIC, 90)

    assert build_conversion_command(plan) == (
        "magick",
        "in.tif",
        "-quality",
        "90",
        "out.heic",
    )


def test_build_jpg_command_uses_magick_quality():
    plan = ConversionPlan(Path("in.tif"), Path("out.jpg"), OutputFormat.JPG, 85)

    assert build_conversion_command(plan) == (
        "magick",
        "in.tif",
        "-quality",
        "85",
        "out.jpg",
    )


def test_build_png_command_ignores_quality():
    plan = ConversionPlan(Path("in.tif"), Path("out.png"), OutputFormat.PNG, 50)

    assert build_conversion_command(plan) == ("magick", "in.tif", "out.png")


def test_build_jxl_command_uses_cjxl():
    plan = ConversionPlan(Path("in.tif"), Path("out.jxl"), OutputFormat.JXL, 80)

    assert build_conversion_command(plan) == (
        "cjxl",
        "in.tif",
        "out.jxl",
        "-q",
        "80",
    )
