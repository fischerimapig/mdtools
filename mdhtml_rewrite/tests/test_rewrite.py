from pathlib import Path

from tools.mdhtml_rewrite.rewrite import rewrite_file


def test_rewrite_prefers_png_for_eps_with_sibling_png(tmp_path):
    input_path = tmp_path / "combined.md"
    output_path = tmp_path / "combined.rewritten.qmd"

    input_path.write_text(
        "\n".join([
            '<figure id="fig:test">',
            '<embed src="sample.eps" style="width:50.0%" />',
            "<figcaption>Sample Figure</figcaption>",
            "</figure>",
            "",
        ]),
        encoding="utf-8",
    )
    (tmp_path / "sample.eps").write_text("%!PS-Adobe-3.0 EPSF-3.0\n", encoding="ascii")
    (tmp_path / "sample.png").write_bytes(b"png")

    rewrite_file(input_path, output_path, prefer_png=True)
    output = output_path.read_text(encoding="utf-8")

    assert "sample.png" in output
    assert "sample.eps" not in output
