import json
from pathlib import Path

from mdhtml_rewrite import convert as convert_mod
from mdhtml_rewrite.model import ConversionResult


def _write_eps(path: Path, creator: str) -> None:
    path.write_text(
        "\n".join([
            "%!PS-Adobe-3.0 EPSF-3.0",
            f"%%Creator: {creator}",
            "%%BoundingBox: 0 0 10 10",
            "%%EndComments",
            "showpage",
            "",
        ]),
        encoding="ascii",
    )


def test_convert_single_auto_vector_uses_svg_when_available(tmp_path, monkeypatch):
    eps_path = tmp_path / "vector.eps"
    _write_eps(eps_path, "Tgif-4.1.45-QPL")

    def fake_vector_to_svg(src, dst, tools):
        dst.write_text("<svg/>", encoding="utf-8")
        return None

    def fail_if_called(*args, **kwargs):
        raise AssertionError("PNG fallback should not run when SVG conversion succeeds")

    monkeypatch.setattr(convert_mod, "_convert_vector_to_svg", fake_vector_to_svg)
    monkeypatch.setattr(convert_mod, "_convert_raster_to_png", fail_if_called)

    result = convert_mod.convert_single(
        eps_path,
        force=True,
        target_format="auto",
        tools={"dvisvgm": "dvisvgm", "gs": "gs"},
    )

    assert result == ConversionResult(
        source=str(eps_path),
        target=str(eps_path.with_suffix(".svg")),
        eps_type="vector",
        target_format="svg",
        status="converted",
    )


def test_convert_single_auto_vector_falls_back_to_png(tmp_path, monkeypatch):
    eps_path = tmp_path / "vector.eps"
    _write_eps(eps_path, "Tgif-4.1.45-QPL")

    def fake_vector_to_svg(src, dst, tools):
        return "dvisvgm failed (rc=254): missing tex.pro"

    def fake_raster_to_png(src, dst, tools, dpi=150):
        dst.write_bytes(b"png")
        return None

    monkeypatch.setattr(convert_mod, "_convert_vector_to_svg", fake_vector_to_svg)
    monkeypatch.setattr(convert_mod, "_convert_raster_to_png", fake_raster_to_png)

    result = convert_mod.convert_single(
        eps_path,
        force=True,
        target_format="auto",
        tools={"dvisvgm": "dvisvgm", "gs": "gs"},
    )

    assert result.status == "converted"
    assert result.target == str(eps_path.with_suffix(".png"))
    assert result.target_format == "png"
    assert result.fallback_from == "svg"
    assert result.warning == "dvisvgm failed (rc=254): missing tex.pro"
    assert result.error is None


def test_convert_single_svg_format_stays_strict(tmp_path, monkeypatch):
    eps_path = tmp_path / "vector.eps"
    _write_eps(eps_path, "Tgif-4.1.45-QPL")

    def fake_vector_to_svg(src, dst, tools):
        return "dvisvgm failed (rc=254): missing tex.pro"

    def fail_if_called(*args, **kwargs):
        raise AssertionError("PNG fallback should not run for --format svg")

    monkeypatch.setattr(convert_mod, "_convert_vector_to_svg", fake_vector_to_svg)
    monkeypatch.setattr(convert_mod, "_convert_raster_to_png", fail_if_called)

    result = convert_mod.convert_single(
        eps_path,
        force=True,
        target_format="svg",
        tools={"dvisvgm": "dvisvgm", "gs": "gs"},
    )

    assert result.status == "failed"
    assert result.target == str(eps_path.with_suffix(".svg"))
    assert result.target_format == "svg"
    assert result.error == "dvisvgm failed (rc=254): missing tex.pro"
    assert result.fallback_from is None
    assert result.warning is None


def test_convert_single_raster_still_uses_png(tmp_path, monkeypatch):
    eps_path = tmp_path / "raster.eps"
    _write_eps(eps_path, "pnmtops")

    def fake_raster_to_png(src, dst, tools, dpi=150):
        dst.write_bytes(b"png")
        return None

    monkeypatch.setattr(convert_mod, "_convert_raster_to_png", fake_raster_to_png)

    result = convert_mod.convert_single(
        eps_path,
        force=True,
        target_format="auto",
        tools={"dvisvgm": "dvisvgm", "gs": "gs"},
    )

    assert result.status == "converted"
    assert result.target == str(eps_path.with_suffix(".png"))
    assert result.target_format == "png"
    assert result.fallback_from is None


def test_write_report_includes_fallback_metadata(tmp_path):
    report_path = tmp_path / "report.json"
    results = [
        ConversionResult(
            source="vector.eps",
            target="vector.png",
            eps_type="vector",
            target_format="png",
            status="converted",
            fallback_from="svg",
            warning="dvisvgm failed (rc=254): missing tex.pro",
        )
    ]

    convert_mod.write_report(results, str(report_path))
    data = json.loads(report_path.read_text(encoding="utf-8"))

    assert data["summary"]["converted"] == 1
    assert data["results"][0]["fallback_from"] == "svg"
    assert data["results"][0]["warning"] == "dvisvgm failed (rc=254): missing tex.pro"


def test_convert_directory_uses_check_tools_and_returns_fallback_result(tmp_path, monkeypatch):
    eps_path = tmp_path / "vector.eps"
    _write_eps(eps_path, "Tgif-4.1.45-QPL")

    monkeypatch.setattr(convert_mod, "check_tools", lambda: {"dvisvgm": "dvisvgm", "gs": "gs"})

    def fake_convert_single(path, *, force=False, target_format="auto", dpi=150, tools=None):
        assert path == eps_path
        assert target_format == "auto"
        assert tools == {"dvisvgm": "dvisvgm", "gs": "gs"}
        return ConversionResult(
            source=str(path),
            target=str(path.with_suffix(".png")),
            eps_type="vector",
            target_format="png",
            status="converted",
            fallback_from="svg",
            warning="dvisvgm failed (rc=254): missing tex.pro",
        )

    monkeypatch.setattr(convert_mod, "convert_single", fake_convert_single)

    results = convert_mod.convert_directory(tmp_path, target_format="auto")

    assert len(results) == 1
    assert results[0].fallback_from == "svg"
    assert results[0].target_format == "png"
