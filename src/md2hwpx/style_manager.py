"""HWPX document style and formatting manager.

Manages style presets (default, academic, business, minimal) that map
semantic style names (heading_1, body, code_block, ...) to concrete
font and paragraph specifications used by the renderer.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FontSpec:
    """Font specification for a text run."""

    hangul: str = "\ub9d1\uc740 \uace0\ub515"          # 맑은 고딕
    latin: str = "Times New Roman"
    size_pt: float = 10.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    color: str = "#000000"
    background: str = ""

    # -- convenience helpers ------------------------------------------------

    def derive(self, **overrides) -> FontSpec:
        """Return a copy with selected fields overridden."""
        clone = deepcopy(self)
        for k, v in overrides.items():
            if hasattr(clone, k):
                setattr(clone, k, v)
        return clone

    @property
    def size_hwp(self) -> int:
        """Size in HWP internal units (1pt = 100 units)."""
        return int(self.size_pt * 100)


@dataclass
class ParaSpec:
    """Paragraph layout specification."""

    align: str = "both"  # left, center, right, both (justify)
    indent_pt: float = 0.0
    left_margin_pt: float = 0.0
    right_margin_pt: float = 0.0
    line_spacing_percent: int = 160
    space_before_pt: float = 0.0
    space_after_pt: float = 6.0

    def derive(self, **overrides) -> ParaSpec:
        clone = deepcopy(self)
        for k, v in overrides.items():
            if hasattr(clone, k):
                setattr(clone, k, v)
        return clone

    @property
    def left_margin_hwp(self) -> int:
        """Left margin in HWP internal units (1pt = 100 units)."""
        return int(self.left_margin_pt * 100)

    @property
    def right_margin_hwp(self) -> int:
        return int(self.right_margin_pt * 100)

    @property
    def indent_hwp(self) -> int:
        return int(self.indent_pt * 100)

    @property
    def space_before_hwp(self) -> int:
        return int(self.space_before_pt * 100)

    @property
    def space_after_hwp(self) -> int:
        return int(self.space_after_pt * 100)


@dataclass
class StyleDef:
    """Complete style definition combining font and paragraph specs."""

    name: str
    font: FontSpec
    para: ParaSpec


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

def _build_default_styles() -> dict[str, StyleDef]:
    """Build the **default** preset styles."""

    body_font = FontSpec(
        hangul="\ub9d1\uc740 \uace0\ub515",
        latin="Times New Roman",
        size_pt=10.0,
    )
    body_para = ParaSpec(
        align="both",
        line_spacing_percent=160,
        space_after_pt=6.0,
    )

    # Heading sizes: H1=22, H2=18, H3=14, H4=12, H5=11, H6=10
    heading_sizes = {1: 22.0, 2: 18.0, 3: 14.0, 4: 12.0, 5: 11.0, 6: 10.0}
    heading_space_before = {1: 16.0, 2: 14.0, 3: 12.0, 4: 10.0, 5: 8.0, 6: 6.0}
    heading_space_after = {1: 10.0, 2: 8.0, 3: 6.0, 4: 6.0, 5: 4.0, 6: 4.0}

    styles: dict[str, StyleDef] = {}

    for level in range(1, 7):
        styles[f"heading_{level}"] = StyleDef(
            name=f"heading_{level}",
            font=body_font.derive(
                size_pt=heading_sizes[level],
                bold=True,
            ),
            para=body_para.derive(
                align="left",
                space_before_pt=heading_space_before[level],
                space_after_pt=heading_space_after[level],
            ),
        )

    styles["body"] = StyleDef(name="body", font=body_font, para=body_para)

    styles["code_block"] = StyleDef(
        name="code_block",
        font=FontSpec(
            hangul="D2Coding",
            latin="Consolas",
            size_pt=9.0,
            color="#000000",
            background="#f5f5f5",
        ),
        para=ParaSpec(
            align="left",
            line_spacing_percent=150,
            space_before_pt=4.0,
            space_after_pt=4.0,
        ),
    )

    styles["inline_code"] = StyleDef(
        name="inline_code",
        font=FontSpec(
            hangul="D2Coding",
            latin="Consolas",
            size_pt=9.0,
            color="#333333",
            background="#f0f0f0",
        ),
        para=body_para,  # inherits paragraph style from surrounding context
    )

    styles["blockquote"] = StyleDef(
        name="blockquote",
        font=body_font.derive(italic=True),
        para=body_para.derive(
            left_margin_pt=20.0,
            space_before_pt=4.0,
            space_after_pt=4.0,
        ),
    )

    styles["table_header"] = StyleDef(
        name="table_header",
        font=body_font.derive(bold=True, size_pt=9.0),
        para=body_para.derive(align="center", space_after_pt=2.0, space_before_pt=2.0),
    )

    styles["table_body"] = StyleDef(
        name="table_body",
        font=body_font.derive(size_pt=9.0),
        para=body_para.derive(align="left", space_after_pt=2.0, space_before_pt=2.0),
    )

    styles["list_item"] = StyleDef(
        name="list_item",
        font=body_font,
        para=body_para.derive(left_margin_pt=20.0, indent_pt=-10.0),
    )

    styles["footnote"] = StyleDef(
        name="footnote",
        font=body_font.derive(size_pt=8.0),
        para=body_para.derive(
            line_spacing_percent=140,
            space_after_pt=2.0,
        ),
    )

    styles["horizontal_rule"] = StyleDef(
        name="horizontal_rule",
        font=body_font.derive(size_pt=2.0),
        para=body_para.derive(
            space_before_pt=8.0,
            space_after_pt=8.0,
        ),
    )

    return styles


def _build_academic_styles() -> dict[str, StyleDef]:
    """Build the **academic** preset -- serif-focused, wider spacing."""

    base = _build_default_styles()

    body_font = FontSpec(
        hangul="\ubc14\ud0d5",                          # 바탕
        latin="Times New Roman",
        size_pt=11.0,
    )
    body_para = ParaSpec(
        align="both",
        line_spacing_percent=200,
        space_after_pt=8.0,
    )

    heading_sizes = {1: 24.0, 2: 20.0, 3: 16.0, 4: 13.0, 5: 12.0, 6: 11.0}
    heading_space_before = {1: 20.0, 2: 16.0, 3: 14.0, 4: 12.0, 5: 10.0, 6: 8.0}
    heading_space_after = {1: 12.0, 2: 10.0, 3: 8.0, 4: 8.0, 5: 6.0, 6: 6.0}

    for level in range(1, 7):
        base[f"heading_{level}"] = StyleDef(
            name=f"heading_{level}",
            font=body_font.derive(size_pt=heading_sizes[level], bold=True),
            para=body_para.derive(
                align="left",
                space_before_pt=heading_space_before[level],
                space_after_pt=heading_space_after[level],
            ),
        )

    base["body"] = StyleDef(name="body", font=body_font, para=body_para)

    base["code_block"] = StyleDef(
        name="code_block",
        font=FontSpec(hangul="D2Coding", latin="Courier New", size_pt=9.5, background="#f5f5f5"),
        para=ParaSpec(align="left", line_spacing_percent=160, space_before_pt=6.0, space_after_pt=6.0),
    )
    base["inline_code"] = StyleDef(
        name="inline_code",
        font=FontSpec(hangul="D2Coding", latin="Courier New", size_pt=9.5, color="#333333", background="#f0f0f0"),
        para=body_para,
    )
    base["blockquote"] = StyleDef(
        name="blockquote",
        font=body_font.derive(italic=True),
        para=body_para.derive(left_margin_pt=24.0, space_before_pt=6.0, space_after_pt=6.0),
    )
    base["table_header"] = StyleDef(
        name="table_header",
        font=body_font.derive(bold=True, size_pt=10.0),
        para=body_para.derive(align="center", space_after_pt=3.0, space_before_pt=3.0),
    )
    base["table_body"] = StyleDef(
        name="table_body",
        font=body_font.derive(size_pt=10.0),
        para=body_para.derive(align="left", space_after_pt=3.0, space_before_pt=3.0),
    )
    base["list_item"] = StyleDef(
        name="list_item",
        font=body_font,
        para=body_para.derive(left_margin_pt=24.0, indent_pt=-12.0),
    )
    base["footnote"] = StyleDef(
        name="footnote",
        font=body_font.derive(size_pt=9.0),
        para=body_para.derive(line_spacing_percent=150, space_after_pt=3.0),
    )

    return base


def _build_business_styles() -> dict[str, StyleDef]:
    """Build the **business** preset -- sans-serif, compact."""

    base = _build_default_styles()

    body_font = FontSpec(
        hangul="\ub9d1\uc740 \uace0\ub515",             # 맑은 고딕
        latin="Arial",
        size_pt=10.0,
    )
    body_para = ParaSpec(
        align="left",
        line_spacing_percent=150,
        space_after_pt=4.0,
    )

    heading_sizes = {1: 20.0, 2: 16.0, 3: 13.0, 4: 11.0, 5: 10.5, 6: 10.0}
    heading_space_before = {1: 14.0, 2: 12.0, 3: 10.0, 4: 8.0, 5: 6.0, 6: 6.0}
    heading_space_after = {1: 8.0, 2: 6.0, 3: 4.0, 4: 4.0, 5: 4.0, 6: 4.0}

    for level in range(1, 7):
        base[f"heading_{level}"] = StyleDef(
            name=f"heading_{level}",
            font=body_font.derive(size_pt=heading_sizes[level], bold=True),
            para=body_para.derive(
                align="left",
                space_before_pt=heading_space_before[level],
                space_after_pt=heading_space_after[level],
            ),
        )

    base["body"] = StyleDef(name="body", font=body_font, para=body_para)

    base["code_block"] = StyleDef(
        name="code_block",
        font=FontSpec(hangul="D2Coding", latin="Consolas", size_pt=9.0, background="#f5f5f5"),
        para=ParaSpec(align="left", line_spacing_percent=140, space_before_pt=4.0, space_after_pt=4.0),
    )
    base["inline_code"] = StyleDef(
        name="inline_code",
        font=FontSpec(hangul="D2Coding", latin="Consolas", size_pt=9.0, color="#333333", background="#f0f0f0"),
        para=body_para,
    )
    base["blockquote"] = StyleDef(
        name="blockquote",
        font=body_font.derive(italic=True, color="#555555"),
        para=body_para.derive(left_margin_pt=16.0, space_before_pt=4.0, space_after_pt=4.0),
    )
    base["table_header"] = StyleDef(
        name="table_header",
        font=body_font.derive(bold=True, size_pt=9.0),
        para=body_para.derive(align="center", space_after_pt=2.0, space_before_pt=2.0),
    )
    base["table_body"] = StyleDef(
        name="table_body",
        font=body_font.derive(size_pt=9.0),
        para=body_para.derive(align="left", space_after_pt=2.0, space_before_pt=2.0),
    )
    base["list_item"] = StyleDef(
        name="list_item",
        font=body_font,
        para=body_para.derive(left_margin_pt=18.0, indent_pt=-9.0),
    )
    base["footnote"] = StyleDef(
        name="footnote",
        font=body_font.derive(size_pt=8.0),
        para=body_para.derive(line_spacing_percent=130, space_after_pt=2.0),
    )

    return base


def _build_minimal_styles() -> dict[str, StyleDef]:
    """Build the **minimal** preset -- clean, tight spacing."""

    base = _build_default_styles()

    body_font = FontSpec(
        hangul="\ub098\ub214\uace0\ub515",               # 나눔고딕
        latin="Helvetica Neue",
        size_pt=10.0,
    )
    body_para = ParaSpec(
        align="left",
        line_spacing_percent=145,
        space_after_pt=3.0,
    )

    heading_sizes = {1: 18.0, 2: 15.0, 3: 12.5, 4: 11.0, 5: 10.5, 6: 10.0}
    heading_space_before = {1: 12.0, 2: 10.0, 3: 8.0, 4: 6.0, 5: 4.0, 6: 4.0}
    heading_space_after = {1: 6.0, 2: 5.0, 3: 4.0, 4: 3.0, 5: 3.0, 6: 3.0}

    for level in range(1, 7):
        base[f"heading_{level}"] = StyleDef(
            name=f"heading_{level}",
            font=body_font.derive(size_pt=heading_sizes[level], bold=True),
            para=body_para.derive(
                align="left",
                space_before_pt=heading_space_before[level],
                space_after_pt=heading_space_after[level],
            ),
        )

    base["body"] = StyleDef(name="body", font=body_font, para=body_para)

    base["code_block"] = StyleDef(
        name="code_block",
        font=FontSpec(hangul="D2Coding", latin="Menlo", size_pt=9.0, background="#fafafa"),
        para=ParaSpec(align="left", line_spacing_percent=140, space_before_pt=3.0, space_after_pt=3.0),
    )
    base["inline_code"] = StyleDef(
        name="inline_code",
        font=FontSpec(hangul="D2Coding", latin="Menlo", size_pt=9.0, color="#333333", background="#f0f0f0"),
        para=body_para,
    )
    base["blockquote"] = StyleDef(
        name="blockquote",
        font=body_font.derive(italic=True, color="#666666"),
        para=body_para.derive(left_margin_pt=14.0, space_before_pt=3.0, space_after_pt=3.0),
    )
    base["table_header"] = StyleDef(
        name="table_header",
        font=body_font.derive(bold=True, size_pt=9.0),
        para=body_para.derive(align="center", space_after_pt=1.0, space_before_pt=1.0),
    )
    base["table_body"] = StyleDef(
        name="table_body",
        font=body_font.derive(size_pt=9.0),
        para=body_para.derive(align="left", space_after_pt=1.0, space_before_pt=1.0),
    )
    base["list_item"] = StyleDef(
        name="list_item",
        font=body_font,
        para=body_para.derive(left_margin_pt=16.0, indent_pt=-8.0),
    )
    base["footnote"] = StyleDef(
        name="footnote",
        font=body_font.derive(size_pt=8.0),
        para=body_para.derive(line_spacing_percent=130, space_after_pt=2.0),
    )

    return base


# ---------------------------------------------------------------------------
# Preset registry
# ---------------------------------------------------------------------------

_PRESET_BUILDERS = {
    "default": _build_default_styles,
    "academic": _build_academic_styles,
    "business": _build_business_styles,
    "minimal": _build_minimal_styles,
}


# ---------------------------------------------------------------------------
# StyleManager
# ---------------------------------------------------------------------------

class StyleManager:
    """Manages document style presets and provides style definitions.

    Usage::

        sm = StyleManager("academic")
        heading_style = sm.get_style("heading_1")
        body_font = sm.get_body_font()
    """

    PRESETS = list(_PRESET_BUILDERS.keys())

    def __init__(self, preset: str = "default") -> None:
        if preset not in _PRESET_BUILDERS:
            raise ValueError(
                f"Unknown preset {preset!r}. Choose from: {', '.join(_PRESET_BUILDERS)}"
            )
        self.preset = preset
        self._styles: dict[str, StyleDef] = {}
        self._load_preset(preset)

    # -- public API ---------------------------------------------------------

    def get_style(self, name: str) -> StyleDef:
        """Get style by semantic name.

        Supported names: heading_1..heading_6, body, code_block,
        inline_code, blockquote, table_header, table_body, list_item,
        footnote, horizontal_rule.

        Falls back to ``body`` for unknown names.
        """
        return self._styles.get(name, self._styles["body"])

    def get_font_for_heading(self, level: int) -> FontSpec:
        """Return the :class:`FontSpec` for heading level *1--6*."""
        level = max(1, min(6, level))
        return self.get_style(f"heading_{level}").font

    def get_para_for_heading(self, level: int) -> ParaSpec:
        """Return the :class:`ParaSpec` for heading level *1--6*."""
        level = max(1, min(6, level))
        return self.get_style(f"heading_{level}").para

    def get_body_font(self) -> FontSpec:
        return self.get_style("body").font

    def get_body_para(self) -> ParaSpec:
        return self.get_style("body").para

    def get_code_font(self) -> FontSpec:
        return self.get_style("code_block").font

    def get_code_para(self) -> ParaSpec:
        return self.get_style("code_block").para

    def get_inline_code_font(self) -> FontSpec:
        return self.get_style("inline_code").font

    def list_style_names(self) -> list[str]:
        """Return all available style names in this preset."""
        return sorted(self._styles.keys())

    # -- internals ----------------------------------------------------------

    def _load_preset(self, preset: str) -> None:
        builder = _PRESET_BUILDERS[preset]
        self._styles = builder()
