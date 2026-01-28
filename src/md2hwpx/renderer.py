"""HWPX document renderer - converts AST to HWPX format.

This module converts an AST tree (produced by :mod:`md2hwpx.parser`) into a
valid HWPX document.  The HWPX file is a ZIP archive containing OWPML XML
files that Hancom Office / Hancom Docs can open.

The renderer uses the OWPML ID-based reference system: styles are defined
in ``header.xml`` with numeric IDs, and section content references them
via ``paraPrIDRef``, ``charPrIDRef``, and ``styleIDRef`` attributes.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring

from md2hwpx.parser import ASTNode, NodeType
from md2hwpx.style_manager import FontSpec, ParaSpec, StyleDef, StyleManager

# ---------------------------------------------------------------------------
# Register OWPML namespaces for ElementTree serialization
# ---------------------------------------------------------------------------

import xml.etree.ElementTree as _ET

NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hv": "http://www.hancom.co.kr/hwpml/2011/version",
    "opf": "http://www.idpf.org/2007/opf/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "odf": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}

for _prefix, _uri in NS.items():
    _ET.register_namespace(_prefix, _uri)

# ---------------------------------------------------------------------------
# OWPML constants
# ---------------------------------------------------------------------------

_ALIGN_MAP = {
    "left": "LEFT",
    "center": "CENTER",
    "right": "RIGHT",
    "both": "JUSTIFY",
    "justify": "JUSTIFY",
}

# A4 page dimensions in HWPUNIT (1/7200 inch)
_A4_WIDTH = 59528    # 210mm
_A4_HEIGHT = 84186   # 297mm
_MARGIN_LEFT = 8504  # 30mm
_MARGIN_RIGHT = 8504
_MARGIN_TOP = 5668   # 20mm
_MARGIN_BOTTOM = 4252  # 15mm
_MARGIN_HEADER = 4252
_MARGIN_FOOTER = 4252

# Common namespace declarations used on root elements of header/section/hpf
_ALL_NS_DECL = (
    ' xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"'
    ' xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
    ' xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph"'
    ' xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
    ' xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"'
    ' xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
    ' xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history"'
    ' xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page"'
    ' xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf"'
    ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
    ' xmlns:opf="http://www.idpf.org/2007/opf/"'
    ' xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart"'
    ' xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar"'
    ' xmlns:epub="http://www.idpf.org/2007/ops"'
    ' xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_plain_text(node: ASTNode) -> str:
    """Recursively extract plain text from an AST subtree."""
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node.children:
        parts.append(_extract_plain_text(child))
    return "".join(parts)


def _xml_escape(s: str) -> str:
    """Escape XML special characters for string-built XML."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _color_to_hex(color: str) -> str:
    """Ensure colour is in ``#RRGGBB`` hex format."""
    if not color:
        return "#000000"
    if color.startswith("#") and len(color) == 7:
        return color
    try:
        return f"#{int(color):06x}"
    except (ValueError, TypeError):
        return "#000000"


_XMLNS_RE = re.compile(r'\s+xmlns(?::[a-z0-9]+)?="[^"]*"')


def _elem_to_str(elem: Element) -> str:
    """Serialize an ElementTree element to XML string without ns declarations.

    The namespace declarations are placed on the document root element, so
    individual element serializations must strip them.
    """
    raw = tostring(elem, encoding="unicode")
    return _XMLNS_RE.sub("", raw)


# ---------------------------------------------------------------------------
# Style registry -- assigns numeric IDs to unique property combinations
# ---------------------------------------------------------------------------

class _StyleRegistry:
    """Track unique font / paragraph properties and assign numeric IDs."""

    def __init__(self) -> None:
        self._fonts: list[str] = []
        self._font_idx: dict[str, int] = {}

        self._char_map: dict[tuple, int] = {}
        self._char_list: list[FontSpec] = []

        self._para_map: dict[tuple, int] = {}
        self._para_list: list[ParaSpec] = []

    def register_font_name(self, name: str) -> int:
        if name in self._font_idx:
            return self._font_idx[name]
        idx = len(self._fonts)
        self._font_idx[name] = idx
        self._fonts.append(name)
        return idx

    def register_char(self, font: FontSpec) -> int:
        key = (
            font.hangul, font.latin, font.size_pt,
            font.bold, font.italic, font.underline, font.strikethrough,
            font.color, font.background,
        )
        if key in self._char_map:
            return self._char_map[key]
        cid = len(self._char_list)
        self._char_map[key] = cid
        self._char_list.append(font)
        self.register_font_name(font.hangul)
        self.register_font_name(font.latin)
        return cid

    def register_para(self, para: ParaSpec) -> int:
        key = (
            para.align, para.indent_pt,
            para.left_margin_pt, para.right_margin_pt,
            para.line_spacing_percent,
            para.space_before_pt, para.space_after_pt,
        )
        if key in self._para_map:
            return self._para_map[key]
        pid = len(self._para_list)
        self._para_map[key] = pid
        self._para_list.append(para)
        return pid

    @property
    def fonts(self) -> list[str]:
        return self._fonts

    @property
    def char_properties(self) -> list[FontSpec]:
        return self._char_list

    @property
    def para_properties(self) -> list[ParaSpec]:
        return self._para_list

    def font_idx(self, name: str) -> int:
        return self._font_idx.get(name, 0)


# ---------------------------------------------------------------------------
# HwpxRenderer
# ---------------------------------------------------------------------------

class HwpxRenderer:
    """Render an :class:`~md2hwpx.parser.ASTNode` document tree to HWPX bytes."""

    def __init__(self, style_manager: Optional[StyleManager] = None) -> None:
        self.style: StyleManager = style_manager or StyleManager()
        self._para_id: int = 0
        self._preview_lines: list[str] = []
        self._registry: _StyleRegistry = _StyleRegistry()

    # ======================================================================
    # Public API
    # ======================================================================

    def render(self, doc: ASTNode) -> bytes:
        """Return a complete HWPX file as *bytes* for the given AST *doc*."""
        assert doc.type == NodeType.DOCUMENT, (
            f"Expected DOCUMENT node, got {doc.type}"
        )
        self._para_id = 0
        self._preview_lines = []
        self._registry = _StyleRegistry()

        body = self.style.get_style("body")
        self._registry.register_char(body.font)
        self._registry.register_para(body.para)

        body_elements: list[Element] = []
        for child in doc.children:
            elements = self._render_node(child)
            body_elements.extend(elements)

        return self._package_hwpx(body_elements)

    def render_to_file(self, doc: ASTNode, path: str) -> None:
        """Render and write to *path*."""
        data = self.render(doc)
        with open(path, "wb") as fh:
            fh.write(data)

    # ======================================================================
    # Node dispatch
    # ======================================================================

    def _render_node(self, node: ASTNode) -> list[Element]:
        handler = getattr(self, f"_render_{node.type.value}", None)
        if handler is not None:
            return handler(node)
        return []

    # ======================================================================
    # Per-NodeType renderers
    # ======================================================================

    def _render_heading(self, node: ASTNode) -> list[Element]:
        level = max(1, min(6, node.level))
        style = self.style.get_style(f"heading_{level}")
        runs = self._collect_inline_runs(node, style.font)
        para = self._make_paragraph(runs, style.para)
        text = _extract_plain_text(node)
        self._preview_lines.append(text)
        return [para]

    def _render_paragraph(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("body")
        runs = self._collect_inline_runs(node, style.font)
        if not runs:
            return []
        para = self._make_paragraph(runs, style.para)
        text = _extract_plain_text(node)
        if text.strip():
            self._preview_lines.append(text)
        return [para]

    def _render_text(self, node: ASTNode) -> list[Element]:
        if not node.text:
            return []
        style = self.style.get_style("body")
        para = self._make_paragraph(
            [(node.text, style.font)],
            style.para,
        )
        self._preview_lines.append(node.text)
        return [para]

    def _render_bold(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("body")
        font = style.font.derive(bold=True)
        runs = self._collect_inline_runs(node, font)
        return [self._make_paragraph(runs, style.para)] if runs else []

    def _render_italic(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("body")
        font = style.font.derive(italic=True)
        runs = self._collect_inline_runs(node, font)
        return [self._make_paragraph(runs, style.para)] if runs else []

    def _render_strikethrough(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("body")
        font = style.font.derive(strikethrough=True)
        runs = self._collect_inline_runs(node, font)
        return [self._make_paragraph(runs, style.para)] if runs else []

    def _render_inline_code(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("body")
        code_font = self.style.get_inline_code_font()
        text = node.text or _extract_plain_text(node)
        return [self._make_paragraph([(text, code_font)], style.para)] if text else []

    def _render_code_block(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("code_block")
        text = node.text or ""
        elements: list[Element] = []
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        for line in lines:
            display = line if line else " "
            para = self._make_paragraph([(display, style.font)], style.para)
            elements.append(para)
        preview = text[:200].replace("\n", " ")
        self._preview_lines.append(f"[Code: {preview}]")
        return elements

    def _render_blockquote(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("blockquote")
        elements: list[Element] = []
        for child in node.children:
            if child.type == NodeType.PARAGRAPH:
                runs = self._collect_inline_runs(child, style.font)
                if runs:
                    elements.append(self._make_paragraph(runs, style.para))
            else:
                sub = self._render_node(child)
                elements.extend(sub)
        text = _extract_plain_text(node)
        if text.strip():
            self._preview_lines.append(f"> {text.strip()[:120]}")
        return elements

    def _render_horizontal_rule(self, _node: ASTNode) -> list[Element]:
        style = self.style.get_style("horizontal_rule")
        hr_text = "\u2500" * 40
        para = self._make_paragraph(
            [(hr_text, style.font)],
            style.para.derive(align="center"),
        )
        self._preview_lines.append("---")
        return [para]

    def _render_ordered_list(self, node: ASTNode) -> list[Element]:
        return self._render_list_block(node, ordered=True)

    def _render_unordered_list(self, node: ASTNode) -> list[Element]:
        return self._render_list_block(node, ordered=False)

    def _render_list_item(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("list_item")
        return self._render_single_list_item(
            node, style=style, ordered=False, counter=0, depth=0,
        )

    def _render_task_list_item(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("list_item")
        return self._render_single_list_item(
            node, style=style, ordered=False, counter=0, depth=0,
        )

    def _render_table(self, node: ASTNode) -> list[Element]:
        if not node.children:
            return []

        first_row = node.children[0]
        num_cols = len(first_row.children) if first_row.children else 1
        num_rows = len(node.children)

        # Available page width (A4 minus margins)
        page_content_width = _A4_WIDTH - _MARGIN_LEFT - _MARGIN_RIGHT  # 42520
        col_width = page_content_width // num_cols
        default_row_height = 2886  # standard row height
        total_height = default_row_height * num_rows

        HP = f"{{{NS['hp']}}}"

        tbl = Element(f"{HP}tbl")
        tbl.set("id", str(self._para_id + 1000))
        tbl.set("zOrder", "0")
        tbl.set("numberingType", "TABLE")
        tbl.set("textWrap", "TOP_AND_BOTTOM")
        tbl.set("textFlow", "BOTH_SIDES")
        tbl.set("lock", "0")
        tbl.set("dropcapstyle", "None")
        tbl.set("pageBreak", "CELL")
        tbl.set("repeatHeader", "1")
        tbl.set("rowCnt", str(num_rows))
        tbl.set("colCnt", str(num_cols))
        tbl.set("cellSpacing", "0")
        tbl.set("borderFillIDRef", "3")
        tbl.set("noAdjust", "0")

        # Table size
        sz = SubElement(tbl, f"{HP}sz")
        sz.set("width", str(page_content_width))
        sz.set("widthRelTo", "ABSOLUTE")
        sz.set("height", str(total_height))
        sz.set("heightRelTo", "ABSOLUTE")
        sz.set("protect", "0")

        # Table position
        pos = SubElement(tbl, f"{HP}pos")
        pos.set("treatAsChar", "0")
        pos.set("affectLSpacing", "0")
        pos.set("flowWithText", "1")
        pos.set("allowOverlap", "0")
        pos.set("holdAnchorAndSO", "0")
        pos.set("vertRelTo", "PARA")
        pos.set("horzRelTo", "COLUMN")
        pos.set("vertAlign", "TOP")
        pos.set("horzAlign", "LEFT")
        pos.set("vertOffset", "0")
        pos.set("horzOffset", "0")

        # Table margins
        out_margin = SubElement(tbl, f"{HP}outMargin")
        out_margin.set("left", "283")
        out_margin.set("right", "283")
        out_margin.set("top", "283")
        out_margin.set("bottom", "283")

        in_margin = SubElement(tbl, f"{HP}inMargin")
        in_margin.set("left", "510")
        in_margin.set("right", "510")
        in_margin.set("top", "141")
        in_margin.set("bottom", "141")

        for row_idx, row_node in enumerate(node.children):
            tr = SubElement(tbl, f"{HP}tr")
            for col_idx, cell_node in enumerate(row_node.children):
                tc = SubElement(tr, f"{HP}tc")
                tc.set("name", "")
                tc.set("header", "1" if cell_node.is_header else "0")
                tc.set("hasMargin", "0")
                tc.set("protect", "0")
                tc.set("editable", "0")
                tc.set("dirty", "0")
                tc.set("borderFillIDRef", "3")

                # subList (must come first)
                sub_list = SubElement(tc, f"{HP}subList")
                sub_list.set("id", "")
                sub_list.set("textDirection", "HORIZONTAL")
                sub_list.set("lineWrap", "BREAK")
                sub_list.set("vertAlign", "CENTER")
                sub_list.set("linkListIDRef", "0")
                sub_list.set("linkListNextIDRef", "0")
                sub_list.set("textWidth", "0")
                sub_list.set("textHeight", "0")
                sub_list.set("hasTextRef", "0")
                sub_list.set("hasNumRef", "0")

                is_header = cell_node.is_header
                cell_style = self.style.get_style(
                    "table_header" if is_header else "table_body"
                )
                cell_para = cell_style.para
                if cell_node.align:
                    cell_para = cell_para.derive(align=cell_node.align)

                runs = self._collect_inline_runs(cell_node, cell_style.font)
                if not runs:
                    runs = [(" ", cell_style.font)]
                para = self._make_paragraph(runs, cell_para)
                sub_list.append(para)

                # cellAddr (after subList)
                addr = SubElement(tc, f"{HP}cellAddr")
                addr.set("colAddr", str(col_idx))
                addr.set("rowAddr", str(row_idx))

                # cellSpan
                span = SubElement(tc, f"{HP}cellSpan")
                span.set("colSpan", "1")
                span.set("rowSpan", "1")

                # cellSz
                cell_sz = SubElement(tc, f"{HP}cellSz")
                cell_sz.set("width", str(col_width))
                cell_sz.set("height", str(default_row_height))

                # cellMargin
                cell_margin = SubElement(tc, f"{HP}cellMargin")
                cell_margin.set("left", "510")
                cell_margin.set("right", "510")
                cell_margin.set("top", "141")
                cell_margin.set("bottom", "141")

        # Wrap table in a paragraph > run (OWPML requires tables inside hp:p)
        self._para_id += 1
        body_style = self.style.get_style("body")
        wrap_para_pr = self._registry.register_para(body_style.para)
        wrap_char_pr = self._registry.register_char(body_style.font)

        p = Element(f"{HP}p")
        p.set("id", str(self._para_id))
        p.set("paraPrIDRef", str(wrap_para_pr))
        p.set("styleIDRef", "0")
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")

        run = SubElement(p, f"{HP}run")
        run.set("charPrIDRef", str(wrap_char_pr))
        run.append(tbl)

        t = SubElement(run, f"{HP}t")
        t.text = " "

        lineseg_arr = SubElement(p, f"{HP}linesegarray")
        lineseg = SubElement(lineseg_arr, f"{HP}lineseg")
        lineseg.set("textpos", "0")
        lineseg.set("vertpos", "0")
        lineseg.set("vertsize", "1000")
        lineseg.set("textheight", "1000")
        lineseg.set("baseline", "850")
        lineseg.set("spacing", "600")
        lineseg.set("horzpos", "0")
        lineseg.set("horzsize", str(page_content_width))
        lineseg.set("flags", "393216")

        self._preview_lines.append("[Table]")
        return [p]

    def _render_table_row(self, _node: ASTNode) -> list[Element]:
        return []

    def _render_table_cell(self, _node: ASTNode) -> list[Element]:
        return []

    def _render_image(self, node: ASTNode) -> list[Element]:
        alt = node.alt or node.title or node.url or "image"
        placeholder = f"[Image: {alt}]"
        style = self.style.get_style("body")
        font = style.font.derive(italic=True, color="#666666")
        para = self._make_paragraph([(placeholder, font)], style.para)
        self._preview_lines.append(placeholder)
        return [para]

    def _render_link(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("body")
        link_font = style.font.derive(underline=True, color="#0563C1")
        runs = self._collect_inline_runs(node, link_font)
        if node.url:
            url_font = style.font.derive(color="#666666", size_pt=8.0)
            runs.append((f" ({node.url})", url_font))
        if not runs:
            runs = [(node.url or "", link_font)]
        para = self._make_paragraph(runs, style.para)
        return [para]

    def _render_footnote_ref(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("body")
        ref_text = f"[{node.footnote_id}]"
        font = style.font.derive(size_pt=7.0, color="#0000FF")
        para = self._make_paragraph([(ref_text, font)], style.para)
        return [para]

    def _render_footnote_def(self, node: ASTNode) -> list[Element]:
        style = self.style.get_style("footnote")
        prefix = f"[{node.footnote_id}] "
        elements: list[Element] = []

        for idx, child in enumerate(node.children):
            runs = self._collect_inline_runs(child, style.font)
            if idx == 0 and runs:
                first_text, first_font = runs[0]
                runs[0] = (prefix + first_text, first_font)
            elif idx == 0:
                runs = [(prefix, style.font)]
            if runs:
                elements.append(self._make_paragraph(runs, style.para))

        if not elements:
            elements.append(
                self._make_paragraph([(prefix, style.font)], style.para)
            )

        text = _extract_plain_text(node)
        self._preview_lines.append(f"  [{node.footnote_id}] {text.strip()[:80]}")
        return elements

    def _render_line_break(self, _node: ASTNode) -> list[Element]:
        return []

    def _render_soft_break(self, _node: ASTNode) -> list[Element]:
        return []

    def _render_document(self, node: ASTNode) -> list[Element]:
        elements: list[Element] = []
        for child in node.children:
            elements.extend(self._render_node(child))
        return elements

    # ======================================================================
    # List rendering helpers
    # ======================================================================

    def _render_list_block(self, node: ASTNode, *, ordered: bool) -> list[Element]:
        style = self.style.get_style("list_item")
        elements: list[Element] = []
        counter = node.start if ordered else 0

        for item in node.children:
            item_elements = self._render_single_list_item(
                item,
                style=style,
                ordered=ordered,
                counter=counter,
                depth=0,
            )
            elements.extend(item_elements)
            if ordered:
                counter += 1

        return elements

    def _render_single_list_item(
        self,
        node: ASTNode,
        *,
        style: StyleDef,
        ordered: bool,
        counter: int,
        depth: int,
    ) -> list[Element]:
        elements: list[Element] = []
        indent_per_depth = 20.0
        extra_indent = depth * indent_per_depth

        para_spec = style.para.derive(
            left_margin_pt=style.para.left_margin_pt + extra_indent,
        )

        if node.type == NodeType.TASK_LIST_ITEM:
            check = "\u2611 " if node.checked else "\u2610 "
            prefix = check
        elif ordered:
            prefix = f"{counter}. "
        else:
            bullets = ["\u2022", "\u25e6", "\u25aa"]
            prefix = f"{bullets[depth % len(bullets)]} "

        inline_runs: list[tuple[str, FontSpec]] = []
        nested_elements: list[Element] = []

        for child in node.children:
            if child.type in (NodeType.PARAGRAPH, NodeType.TEXT):
                runs = self._collect_inline_runs(child, style.font)
                inline_runs.extend(runs)
            elif child.type in (NodeType.ORDERED_LIST, NodeType.UNORDERED_LIST):
                nested_elements.extend(
                    self._render_nested_list(child, style=style, depth=depth + 1)
                )
            else:
                nested_elements.extend(self._render_node(child))

        if inline_runs:
            first_text, first_font = inline_runs[0]
            inline_runs[0] = (prefix + first_text, first_font)
        else:
            inline_runs = [(prefix.rstrip(), style.font)]

        elements.append(self._make_paragraph(inline_runs, para_spec))
        elements.extend(nested_elements)

        text = _extract_plain_text(node)
        self._preview_lines.append(
            f"  {'  ' * depth}{prefix}{text.strip()[:80]}"
        )

        return elements

    def _render_nested_list(
        self, node: ASTNode, *, style: StyleDef, depth: int
    ) -> list[Element]:
        ordered = node.type == NodeType.ORDERED_LIST
        elements: list[Element] = []
        counter = node.start if ordered else 0

        for item in node.children:
            item_elements = self._render_single_list_item(
                item,
                style=style,
                ordered=ordered,
                counter=counter,
                depth=depth,
            )
            elements.extend(item_elements)
            if ordered:
                counter += 1

        return elements

    # ======================================================================
    # Paragraph builder (ID-reference based)
    # ======================================================================

    def _make_paragraph(
        self,
        runs: list[tuple[str, FontSpec]],
        para_spec: ParaSpec,
    ) -> Element:
        """Build an ``hp:p`` element using OWPML ID references."""
        self._para_id += 1
        para_pr_id = self._registry.register_para(para_spec)

        p = Element(f"{{{NS['hp']}}}p")
        p.set("id", str(self._para_id))
        p.set("paraPrIDRef", str(para_pr_id))
        p.set("styleIDRef", "0")
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")

        for text, font in runs:
            if not text:
                continue
            char_pr_id = self._registry.register_char(font)
            run_el = SubElement(p, f"{{{NS['hp']}}}run")
            run_el.set("charPrIDRef", str(char_pr_id))

            t_el = SubElement(run_el, f"{{{NS['hp']}}}t")
            t_el.text = text

        return p

    # ======================================================================
    # Inline run collection
    # ======================================================================

    def _collect_inline_runs(
        self, node: ASTNode, base_font: FontSpec
    ) -> list[tuple[str, FontSpec]]:
        runs: list[tuple[str, FontSpec]] = []

        if node.text and not node.children:
            runs.append((node.text, base_font))
            return runs

        for child in node.children:
            child_runs = self._collect_inline_child(child, base_font)
            runs.extend(child_runs)

        return runs

    def _collect_inline_child(
        self, node: ASTNode, base_font: FontSpec
    ) -> list[tuple[str, FontSpec]]:
        nt = node.type

        if nt == NodeType.TEXT:
            text = node.text
            if not text and node.children:
                text = _extract_plain_text(node)
            return [(text, base_font)] if text else []

        if nt == NodeType.BOLD:
            font = base_font.derive(bold=True)
            return self._collect_inline_runs(node, font)

        if nt == NodeType.ITALIC:
            font = base_font.derive(italic=True)
            return self._collect_inline_runs(node, font)

        if nt == NodeType.STRIKETHROUGH:
            font = base_font.derive(strikethrough=True)
            return self._collect_inline_runs(node, font)

        if nt == NodeType.INLINE_CODE:
            code_font = self.style.get_inline_code_font()
            text = node.text or _extract_plain_text(node)
            return [(text, code_font)] if text else []

        if nt == NodeType.LINK:
            link_font = base_font.derive(underline=True, color="#0563C1")
            return self._collect_inline_runs(node, link_font)

        if nt == NodeType.IMAGE:
            alt = node.alt or node.title or "image"
            placeholder_font = base_font.derive(italic=True, color="#666666")
            return [(f"[Image: {alt}]", placeholder_font)]

        if nt == NodeType.FOOTNOTE_REF:
            ref_font = base_font.derive(size_pt=7.0, color="#0000FF")
            return [(f"[{node.footnote_id}]", ref_font)]

        if nt == NodeType.LINE_BREAK:
            return [("\n", base_font)]

        if nt == NodeType.SOFT_BREAK:
            return [(" ", base_font)]

        text = _extract_plain_text(node)
        return [(text, base_font)] if text else []

    # ======================================================================
    # HWPX ZIP packaging
    # ======================================================================

    def _package_hwpx(self, body_elements: list[Element]) -> bytes:
        """Assemble body elements into a valid HWPX ZIP archive."""
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. mimetype (MUST be first, uncompressed)
            zf.writestr(
                zipfile.ZipInfo("mimetype"),
                "application/hwp+zip",
                compress_type=zipfile.ZIP_STORED,
            )

            # 2. version.xml
            zf.writestr("version.xml", self._build_version_xml())

            # 3. META-INF/container.xml
            zf.writestr("META-INF/container.xml", self._build_container_xml())

            # 4. META-INF/manifest.xml
            zf.writestr("META-INF/manifest.xml", self._build_manifest_xml())

            # 5. META-INF/container.rdf
            zf.writestr("META-INF/container.rdf", self._build_container_rdf())

            # 6. settings.xml
            zf.writestr("settings.xml", self._build_settings_xml())

            # 7. Contents/content.hpf
            zf.writestr("Contents/content.hpf", self._build_content_hpf())

            # 8. Contents/header.xml
            zf.writestr("Contents/header.xml", self._build_header_xml())

            # 9. Contents/section0.xml
            zf.writestr(
                "Contents/section0.xml",
                self._build_section_xml(body_elements),
            )

            # 10. Preview/PrvText.txt
            preview = "\n".join(self._preview_lines[:50])
            zf.writestr("Preview/PrvText.txt", preview.encode("utf-8"))

        return buf.getvalue()

    # -- Fixed-structure XML files ------------------------------------------

    def _build_version_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<hv:HCFVersion'
            ' xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version"'
            ' tagetApplication="WORDPROCESSOR"'
            ' major="5" minor="1" micro="1" buildNumber="0"'
            ' os="1" xmlVersion="1.5"'
            ' application="Hancom Office Hangul"'
            ' appVersion="13, 0, 0, 1408 WIN32LEWindows_10"/>'
        )

    def _build_settings_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<ha:HWPApplicationSetting'
            ' xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"'
            ' xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
            '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
            '</ha:HWPApplicationSetting>'
        )

    def _build_container_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<ocf:container'
            ' xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container"'
            ' xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf">'
            '<ocf:rootfiles>'
            '<ocf:rootfile full-path="Contents/content.hpf"'
            ' media-type="application/hwpml-package+xml"/>'
            '<ocf:rootfile full-path="Preview/PrvText.txt"'
            ' media-type="text/plain"/>'
            '<ocf:rootfile full-path="META-INF/container.rdf"'
            ' media-type="application/rdf+xml"/>'
            '</ocf:rootfiles>'
            '</ocf:container>'
        )

    def _build_manifest_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<odf:manifest'
            ' xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
        )

    def _build_container_rdf(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description rdf:about="">'
            '<ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#"'
            ' rdf:resource="Contents/header.xml"/>'
            '</rdf:Description>'
            '<rdf:Description rdf:about="Contents/header.xml">'
            '<rdf:type rdf:resource='
            '"http://www.hancom.co.kr/hwpml/2016/meta/pkg#HeaderFile"/>'
            '</rdf:Description>'
            '<rdf:Description rdf:about="">'
            '<ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#"'
            ' rdf:resource="Contents/section0.xml"/>'
            '</rdf:Description>'
            '<rdf:Description rdf:about="Contents/section0.xml">'
            '<rdf:type rdf:resource='
            '"http://www.hancom.co.kr/hwpml/2016/meta/pkg#SectionFile"/>'
            '</rdf:Description>'
            '<rdf:Description rdf:about="">'
            '<rdf:type rdf:resource='
            '"http://www.hancom.co.kr/hwpml/2016/meta/pkg#Document"/>'
            '</rdf:Description>'
            '</rdf:RDF>'
        )

    def _build_content_hpf(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            '<opf:package' + _ALL_NS_DECL +
            ' version="" unique-identifier="" id="">'
            '<opf:metadata>'
            '<opf:title/>'
            '<opf:language>ko</opf:language>'
            '<opf:meta name="creator" content="text">md2hwpx</opf:meta>'
            '</opf:metadata>'
            '<opf:manifest>'
            '<opf:item id="header" href="Contents/header.xml"'
            ' media-type="application/xml"/>'
            '<opf:item id="section0" href="Contents/section0.xml"'
            ' media-type="application/xml"/>'
            '<opf:item id="settings" href="settings.xml"'
            ' media-type="application/xml"/>'
            '</opf:manifest>'
            '<opf:spine>'
            '<opf:itemref idref="header" linear="yes"/>'
            '<opf:itemref idref="section0" linear="yes"/>'
            '</opf:spine>'
            '</opf:package>'
        )

    # -- header.xml (style definitions) ------------------------------------

    def _build_header_xml(self) -> str:
        """Build ``Contents/header.xml`` matching OWPML Skeleton structure."""
        reg = self._registry
        L = []  # noqa: E741
        a = L.append

        a('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>')
        a(f'<hh:head{_ALL_NS_DECL} version="1.5" secCnt="1">')

        # beginNum
        a('<hh:beginNum page="1" footnote="1" endnote="1"'
          ' pic="1" tbl="1" equation="1"/>')

        a('<hh:refList>')

        # ---- fontfaces (7 languages) ----
        fonts = reg.fonts
        if not fonts:
            fonts = ["\ub9d1\uc740 \uace0\ub515"]  # 맑은 고딕

        font_cnt = len(fonts)
        langs = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]
        a(f'<hh:fontfaces itemCnt="{len(langs)}">')
        for lang in langs:
            a(f'<hh:fontface lang="{lang}" fontCnt="{font_cnt}">')
            for fi, fn in enumerate(fonts):
                a(f'<hh:font id="{fi}" face="{_xml_escape(fn)}"'
                  f' type="TTF" isEmbedded="0">'
                  '<hh:typeInfo familyType="FCAT_GOTHIC" weight="6"'
                  ' proportion="4" contrast="0" strokeVariation="1"'
                  ' armStyle="1" letterform="1" midline="1" xHeight="1"/>'
                  '</hh:font>')
            a('</hh:fontface>')
        a('</hh:fontfaces>')

        # ---- borderFills ----
        a('<hh:borderFills itemCnt="3">')
        # id=1: page border (no visible borders)
        a('<hh:borderFill id="1" threeD="0" shadow="0"'
          ' centerLine="NONE" breakCellSeparateLine="0">'
          '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
          '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
          '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
          '</hh:borderFill>')
        # id=2: default charPr/paraPr border (no visible borders, with fill)
        a('<hh:borderFill id="2" threeD="0" shadow="0"'
          ' centerLine="NONE" breakCellSeparateLine="0">'
          '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
          '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
          '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
          '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
          '<hc:fillBrush>'
          '<hc:winBrush faceColor="none" hatchColor="#999999" alpha="0"/>'
          '</hc:fillBrush>'
          '</hh:borderFill>')
        # id=3: table/cell border (SOLID visible borders)
        a('<hh:borderFill id="3" threeD="0" shadow="0"'
          ' centerLine="NONE" breakCellSeparateLine="0">'
          '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
          '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
          '<hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/>'
          '<hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/>'
          '<hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/>'
          '<hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/>'
          '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
          '</hh:borderFill>')
        a('</hh:borderFills>')

        # ---- charProperties ----
        chars = reg.char_properties
        if not chars:
            body = self.style.get_style("body")
            chars = [body.font]

        a(f'<hh:charProperties itemCnt="{len(chars)}">')
        for idx, font in enumerate(chars):
            tc = _color_to_hex(font.color)
            sc = "none"
            if font.background:
                sc = _color_to_hex(font.background)
            h_idx = reg.font_idx(font.hangul)
            l_idx = reg.font_idx(font.latin)
            height = font.size_hwp

            a(f'<hh:charPr id="{idx}" height="{height}"'
              f' textColor="{tc}" shadeColor="{sc}"'
              f' useFontSpace="0" useKerning="0"'
              f' symMark="NONE" borderFillIDRef="2">')
            a(f'<hh:fontRef hangul="{h_idx}" latin="{l_idx}"'
              f' hanja="{h_idx}" japanese="{h_idx}" other="{l_idx}"'
              f' symbol="{l_idx}" user="{l_idx}"/>')
            if font.bold:
                a('<hh:bold/>')
            if font.italic:
                a('<hh:italic/>')
            a(f'<hh:ratio hangul="100" latin="100" hanja="100"'
              f' japanese="100" other="100" symbol="100" user="100"/>')
            a(f'<hh:spacing hangul="0" latin="0" hanja="0"'
              f' japanese="0" other="0" symbol="0" user="0"/>')
            a(f'<hh:relSz hangul="100" latin="100" hanja="100"'
              f' japanese="100" other="100" symbol="100" user="100"/>')
            a(f'<hh:offset hangul="0" latin="0" hanja="0"'
              f' japanese="0" other="0" symbol="0" user="0"/>')
            ul_type = "BOTTOM" if font.underline else "NONE"
            a(f'<hh:underline type="{ul_type}" shape="SOLID" color="#000000"/>')
            st_shape = "SINGLE" if font.strikethrough else "NONE"
            a(f'<hh:strikeout shape="{st_shape}" color="#000000"/>')
            a('<hh:outline type="NONE"/>')
            a('<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>')
            a('</hh:charPr>')
        a('</hh:charProperties>')

        # ---- tabProperties ----
        a('<hh:tabProperties itemCnt="1">')
        a('<hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>')
        a('</hh:tabProperties>')

        # ---- numberings ----
        a('<hh:numberings itemCnt="1">'
          '<hh:numbering id="1" start="0">'
          '<hh:paraHead start="1" level="1" align="LEFT" useInstWidth="1"'
          ' autoIndent="1" widthAdjust="0" textOffsetType="PERCENT"'
          ' textOffset="50" numFormat="DIGIT"'
          ' charPrIDRef="4294967295" checkable="0">^1.</hh:paraHead>'
          '</hh:numbering>'
          '</hh:numberings>')

        # ---- paraProperties ----
        paras = reg.para_properties
        if not paras:
            body = self.style.get_style("body")
            paras = [body.para]

        a(f'<hh:paraProperties itemCnt="{len(paras)}">')
        for idx, para in enumerate(paras):
            align = _ALIGN_MAP.get(para.align, "JUSTIFY")
            a(f'<hh:paraPr id="{idx}" tabPrIDRef="0" condense="0"'
              f' fontLineHeight="0" snapToGrid="1"'
              f' suppressLineNumbers="0" checked="0" textDir="LTR">')
            a(f'<hh:align horizontal="{align}" vertical="BASELINE"/>')
            a('<hh:heading type="NONE" idRef="0" level="0"/>')
            a('<hh:breakSetting breakLatinWord="KEEP_WORD"'
              ' breakNonLatinWord="BREAK_WORD" widowOrphan="0"'
              ' keepWithNext="0" keepLines="0" pageBreakBefore="0"'
              ' lineWrap="BREAK"/>')
            a('<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>')
            # hp:switch with margin and lineSpacing
            intent = para.indent_hwp
            left = para.left_margin_hwp
            right = para.right_margin_hwp
            prev = para.space_before_hwp
            nxt = para.space_after_hwp
            ls = para.line_spacing_percent
            margin_block = (
                '<hh:margin>'
                f'<hc:intent value="{intent}" unit="HWPUNIT"/>'
                f'<hc:left value="{left}" unit="HWPUNIT"/>'
                f'<hc:right value="{right}" unit="HWPUNIT"/>'
                f'<hc:prev value="{prev}" unit="HWPUNIT"/>'
                f'<hc:next value="{nxt}" unit="HWPUNIT"/>'
                '</hh:margin>'
                f'<hh:lineSpacing type="PERCENT" value="{ls}" unit="HWPUNIT"/>'
            )
            a('<hp:switch>'
              '<hp:case hp:required-namespace='
              '"http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
              + margin_block +
              '</hp:case>'
              '<hp:default>'
              + margin_block +
              '</hp:default>'
              '</hp:switch>')
            a('<hh:border borderFillIDRef="2" offsetLeft="0"'
              ' offsetRight="0" offsetTop="0" offsetBottom="0"'
              ' connect="0" ignoreMargin="0"/>')
            a('</hh:paraPr>')
        a('</hh:paraProperties>')

        # ---- styles ----
        a('<hh:styles itemCnt="1">')
        a('<hh:style id="0" type="PARA"'
          ' name="\ubc14\ud0d5\uae00" engName="Normal"'
          ' paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0"'
          ' langID="1042" lockForm="0"/>')
        a('</hh:styles>')

        a('</hh:refList>')

        # ---- compatibleDocument ----
        a('<hh:compatibleDocument targetProgram="HWP201X">'
          '<hh:layoutCompatibility/>'
          '</hh:compatibleDocument>')

        # ---- docOption ----
        a('<hh:docOption>'
          '<hh:linkinfo path="" pageInherit="0" footnoteInherit="0"/>'
          '</hh:docOption>')

        # ---- metaTag ----
        a('<hh:metaTag>{"name":""}</hh:metaTag>')

        # ---- trackchageConfig ----
        a('<hh:trackchageConfig flags="56"/>')

        a('</hh:head>')

        return "".join(L)

    # -- section0.xml (body content) ---------------------------------------

    def _build_section_xml(self, body_elements: list[Element]) -> str:
        """Build ``Contents/section0.xml`` with secPr preamble and body."""
        parts: list[str] = []
        a = parts.append

        a('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>')
        a(f'<hs:sec{_ALL_NS_DECL}>')

        # First paragraph: contains secPr + colPr + empty text
        body_style = self.style.get_style("body")
        first_char_id = self._registry.register_char(body_style.font)

        self._para_id += 1
        first_para_id = self._para_id
        first_para_pr_id = self._registry.register_para(body_style.para)

        a(f'<hp:p id="{first_para_id}" paraPrIDRef="{first_para_pr_id}"'
          f' styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">')

        # Run with secPr
        a(f'<hp:run charPrIDRef="{first_char_id}">')
        a('<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134"'
          ' tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT"'
          ' outlineShapeIDRef="1" memoShapeIDRef="0"'
          ' textVerticalWidthHead="0" masterPageCnt="0">')
        a('<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>')
        a('<hp:startNum pageStartsOn="BOTH" page="0" pic="0"'
          ' tbl="0" equation="0"/>')
        a('<hp:visibility hideFirstHeader="0" hideFirstFooter="0"'
          ' hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL"'
          ' hideFirstPageNum="0" hideFirstEmptyLine="0"'
          ' showLineNumber="0"/>')
        a('<hp:lineNumberShape restartType="0" countBy="0"'
          ' distance="0" startNumber="0"/>')
        a(f'<hp:pagePr landscape="WIDELY" width="{_A4_WIDTH}"'
          f' height="{_A4_HEIGHT}" gutterType="LEFT_ONLY">')
        a(f'<hp:margin header="{_MARGIN_HEADER}" footer="{_MARGIN_FOOTER}"'
          f' gutter="0" left="{_MARGIN_LEFT}" right="{_MARGIN_RIGHT}"'
          f' top="{_MARGIN_TOP}" bottom="{_MARGIN_BOTTOM}"/>')
        a('</hp:pagePr>')
        a('<hp:footNotePr>'
          '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar=""'
          ' suffixChar=")" supscript="0"/>'
          '<hp:noteLine length="-1" type="SOLID"'
          ' width="0.12 mm" color="#000000"/>'
          '<hp:noteSpacing betweenNotes="283" belowLine="567"'
          ' aboveLine="850"/>'
          '<hp:numbering type="CONTINUOUS" newNum="1"/>'
          '<hp:placement place="EACH_COLUMN" beneathText="0"/>'
          '</hp:footNotePr>')
        a('<hp:endNotePr>'
          '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar=""'
          ' suffixChar=")" supscript="0"/>'
          '<hp:noteLine length="14692344" type="SOLID"'
          ' width="0.12 mm" color="#000000"/>'
          '<hp:noteSpacing betweenNotes="0" belowLine="567"'
          ' aboveLine="850"/>'
          '<hp:numbering type="CONTINUOUS" newNum="1"/>'
          '<hp:placement place="END_OF_DOCUMENT" beneathText="0"/>'
          '</hp:endNotePr>')
        for pbt in ("BOTH", "EVEN", "ODD"):
            a(f'<hp:pageBorderFill type="{pbt}" borderFillIDRef="1"'
              ' textBorder="PAPER" headerInside="0" footerInside="0"'
              ' fillArea="PAPER">'
              '<hp:offset left="1417" right="1417" top="1417"'
              ' bottom="1417"/>'
              '</hp:pageBorderFill>')
        a('</hp:secPr>')

        # colPr control
        a('<hp:ctrl>'
          '<hp:colPr id="" type="NEWSPAPER" layout="LEFT"'
          ' colCount="1" sameSz="1" sameGap="0"/>'
          '</hp:ctrl>')
        a('</hp:run>')

        # Empty text run
        a(f'<hp:run charPrIDRef="{first_char_id}"><hp:t/></hp:run>')

        # linesegarray
        a('<hp:linesegarray>'
          '<hp:lineseg textpos="0" vertpos="0" vertsize="1000"'
          ' textheight="1000" baseline="850" spacing="600"'
          ' horzpos="0" horzsize="42520" flags="393216"/>'
          '</hp:linesegarray>')

        a('</hp:p>')

        # Body content paragraphs/tables
        if body_elements:
            for el in body_elements:
                a(_elem_to_str(el))
        else:
            # Ensure at least one content paragraph
            self._para_id += 1
            ppid = self._registry.register_para(body_style.para)
            cpid = self._registry.register_char(body_style.font)
            a(f'<hp:p id="{self._para_id}" paraPrIDRef="{ppid}"'
              f' styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">')
            a(f'<hp:run charPrIDRef="{cpid}"><hp:t> </hp:t></hp:run>')
            a('</hp:p>')

        a('</hs:sec>')

        return "".join(parts)
