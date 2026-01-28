"""Integration tests for the Converter orchestrator."""

from __future__ import annotations

import zipfile
import io
import pytest
from pathlib import Path

from md2hwpx.converter import Converter
from md2hwpx.style_manager import StyleManager

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MD = FIXTURE_DIR / "sample.md"


class TestConverterInit:
    """Test Converter construction."""

    def test_default_preset(self):
        c = Converter()
        assert c.style_manager.preset == "default"

    def test_custom_preset(self):
        c = Converter(style_preset="academic")
        assert c.style_manager.preset == "academic"

    def test_invalid_preset_raises(self):
        with pytest.raises(ValueError):
            Converter(style_preset="nonexistent")

    def test_all_presets_valid(self):
        for preset in StyleManager.PRESETS:
            c = Converter(style_preset=preset)
            assert c.style_manager.preset == preset


class TestConvertText:
    """Test convert_text produces valid HWPX bytes."""

    def test_simple_heading(self):
        c = Converter()
        data = c.convert_text("# Hello World")
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_output_is_zip(self):
        c = Converter()
        data = c.convert_text("Some text")
        buf = io.BytesIO(data)
        assert zipfile.is_zipfile(buf)

    def test_zip_contains_required_files(self):
        c = Converter()
        data = c.convert_text("# Test\n\nParagraph text.")
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert "META-INF/container.xml" in names
            assert "Contents/content.hpf" in names
            assert "Contents/header.xml" in names
            assert "Contents/section0.xml" in names
            assert "Preview/PrvText.txt" in names

    def test_mimetype_content(self):
        c = Converter()
        data = c.convert_text("test")
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            assert zf.read("mimetype").decode() == "application/hwp+zip"

    def test_korean_text_preserved(self):
        c = Converter()
        data = c.convert_text("# 한글 제목\n\n한글 본문입니다.")
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            preview = zf.read("Preview/PrvText.txt").decode("utf-8")
            assert "한글 제목" in preview
            assert "한글 본문입니다" in preview

    def test_table_content_in_output(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        c = Converter()
        data = c.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            assert "tbl" in section
            assert "A" in section
            assert "B" in section

    def test_empty_markdown(self):
        c = Converter()
        data = c.convert_text("")
        assert isinstance(data, bytes)
        buf = io.BytesIO(data)
        assert zipfile.is_zipfile(buf)

    def test_all_presets_produce_output(self):
        md = "# Title\n\nBody text."
        for preset in StyleManager.PRESETS:
            c = Converter(style_preset=preset)
            data = c.convert_text(md)
            assert len(data) > 0, f"Preset {preset} produced empty output"


class TestConvertFile:
    """Test file-based conversion."""

    def test_convert_sample_fixture(self, tmp_path):
        if not SAMPLE_MD.exists():
            pytest.skip("sample.md fixture not found")
        out = tmp_path / "output.hwpx"
        c = Converter()
        c.convert_file(SAMPLE_MD, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_output_directory_created(self, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# Test", encoding="utf-8")
        out = tmp_path / "subdir" / "nested" / "output.hwpx"
        c = Converter()
        c.convert_file(md_file, out)
        assert out.exists()

    def test_different_presets(self, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_text("# Test\n\nBody.", encoding="utf-8")
        sizes = {}
        for preset in StyleManager.PRESETS:
            out = tmp_path / f"output_{preset}.hwpx"
            c = Converter(style_preset=preset)
            c.convert_file(md_file, out)
            sizes[preset] = out.stat().st_size
            assert sizes[preset] > 0

    def test_encoding_parameter(self, tmp_path):
        md_file = tmp_path / "input.md"
        md_file.write_bytes("# 한글 제목".encode("euc-kr"))
        out = tmp_path / "output.hwpx"
        c = Converter()
        c.convert_file(md_file, out, encoding="euc-kr")
        assert out.exists()
        assert out.stat().st_size > 0


class TestFullMarkdownFeatures:
    """Test that all Markdown features produce valid output."""

    @pytest.fixture
    def converter(self):
        return Converter()

    def test_headings(self, converter):
        md = "\n\n".join(f"{'#' * i} Heading {i}" for i in range(1, 7))
        data = converter.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            for i in range(1, 7):
                assert f"Heading {i}" in section

    def test_bold_italic_strikethrough(self, converter):
        md = "**bold** *italic* ~~strike~~"
        data = converter.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            assert "bold" in section

    def test_code_block(self, converter):
        md = "```python\nprint('hello')\n```"
        data = converter.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            assert "print" in section

    def test_lists(self, converter):
        md = "- item 1\n- item 2\n\n1. first\n2. second"
        data = converter.convert_text(md)
        assert len(data) > 0

    def test_blockquote(self, converter):
        md = "> This is a quote"
        data = converter.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            assert "quote" in section

    def test_link(self, converter):
        md = "[GitHub](https://github.com)"
        data = converter.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            assert "GitHub" in section

    def test_image(self, converter):
        md = "![alt text](https://example.com/img.png)"
        data = converter.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            assert "alt text" in section

    def test_horizontal_rule(self, converter):
        md = "Above\n\n---\n\nBelow"
        data = converter.convert_text(md)
        assert len(data) > 0

    def test_table_with_alignment(self, converter):
        md = "| Left | Center | Right |\n|:-----|:------:|------:|\n| a | b | c |"
        data = converter.convert_text(md)
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf) as zf:
            section = zf.read("Contents/section0.xml").decode("utf-8")
            assert "Left" in section
            assert "Center" in section
            assert "Right" in section
