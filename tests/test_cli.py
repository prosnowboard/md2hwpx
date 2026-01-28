"""Tests for the CLI module."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from md2hwpx.cli import main

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MD = FIXTURE_DIR / "sample.md"


class TestCLIMain:
    """Test the main() entry point."""

    def test_list_styles(self, capsys):
        ret = main(["--list-styles"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "default" in out
        assert "academic" in out

    def test_missing_input(self):
        with pytest.raises(SystemExit):
            main([])

    def test_file_not_found(self, capsys):
        ret = main(["nonexistent.md"])
        assert ret == 1
        err = capsys.readouterr().err
        assert "not found" in err

    def test_convert_sample(self, tmp_path, capsys):
        if not SAMPLE_MD.exists():
            pytest.skip("sample.md fixture not found")
        out = tmp_path / "output.hwpx"
        ret = main([str(SAMPLE_MD), "-o", str(out)])
        assert ret == 0
        assert out.exists()
        assert out.stat().st_size > 0

    def test_verbose_flag(self, tmp_path, capsys):
        if not SAMPLE_MD.exists():
            pytest.skip("sample.md fixture not found")
        out = tmp_path / "output.hwpx"
        ret = main([str(SAMPLE_MD), "-o", str(out), "-v"])
        assert ret == 0
        stdout = capsys.readouterr().out
        assert "Input:" in stdout
        assert "Output:" in stdout
        assert "Done." in stdout

    def test_default_output_name(self, tmp_path, capsys):
        md_file = tmp_path / "myfile.md"
        md_file.write_text("# Test", encoding="utf-8")
        ret = main([str(md_file)])
        assert ret == 0
        expected = tmp_path / "myfile.hwpx"
        assert expected.exists()

    def test_style_presets(self, tmp_path, capsys):
        if not SAMPLE_MD.exists():
            pytest.skip("sample.md fixture not found")
        for preset in ["default", "academic", "business", "minimal"]:
            out = tmp_path / f"output_{preset}.hwpx"
            ret = main([str(SAMPLE_MD), "-o", str(out), "-s", preset])
            assert ret == 0, f"Failed for preset: {preset}"
            assert out.exists()
