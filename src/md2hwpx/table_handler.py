"""HWPX table handler for converting Markdown tables to HWPX XML format.

This module converts TABLE ASTNodes (from the parser) into HWPX-compliant
table XML elements using ElementTree. It supports:
- Header row distinction (bold text, background color)
- Cell alignment (left, center, right)
- Proper border styling
- Korean text rendering
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element
    from md2hwpx.parser import ASTNode

from md2hwpx.parser import NodeType

# Register the HWPX paragraph namespace
ET.register_namespace('hp', 'http://www.hancom.co.kr/hwpml/2011/paragraph')


class TableHandler:
    """Converts Markdown TABLE ASTNodes to HWPX table XML elements."""

    HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"

    def __init__(self) -> None:
        """Initialize table handler with default formatting values."""
        self.default_col_width = 3000  # HWPX units
        self.default_row_height = 800  # HWPX units
        self.header_bg_color = "#e0e0e0"  # Light gray for header background
        self.cell_margin_left = 56
        self.cell_margin_right = 56
        self.cell_margin_top = 28
        self.cell_margin_bottom = 28
        self.cell_spacing = 0
        self.border_fill_id = 1  # Reference to border style definition
        self.header_border_fill_id = 2  # Reference to header border style

    def render_table(self, table_node: ASTNode) -> Element:
        """Convert a TABLE ASTNode to an hp:tbl Element.

        Args:
            table_node: TABLE ASTNode containing TABLE_ROW children

        Returns:
            ElementTree Element representing the HWPX table

        Raises:
            ValueError: If table_node is not a TABLE type
        """
        if table_node.type != NodeType.TABLE:
            raise ValueError(f"Expected TABLE node, got {table_node.type}")

        rows = table_node.children
        if not rows:
            # Empty table - create a 1x1 placeholder
            rows = [self._create_empty_row()]

        row_count = len(rows)
        # Determine column count from the first row
        col_count = len(rows[0].children) if rows and rows[0].children else 1

        # Create table element with namespace
        tbl = ET.Element(f"{{{self.HP_NS}}}tbl")
        tbl.set("colCnt", str(col_count))
        tbl.set("rowCnt", str(row_count))
        tbl.set("cellSpacing", str(self.cell_spacing))
        tbl.set("borderFill", str(self.border_fill_id))

        # Add table properties
        tbl_pr = ET.SubElement(tbl, f"{{{self.HP_NS}}}tblPr")
        cell_margin = ET.SubElement(tbl_pr, f"{{{self.HP_NS}}}cellMargin")
        cell_margin.set("left", str(self.cell_margin_left))
        cell_margin.set("right", str(self.cell_margin_right))
        cell_margin.set("top", str(self.cell_margin_top))
        cell_margin.set("bottom", str(self.cell_margin_bottom))

        # Render each row
        for row_idx, row_node in enumerate(rows):
            if row_node.type != NodeType.TABLE_ROW:
                continue
            tr = self._render_row(row_node, row_idx, col_count)
            tbl.append(tr)

        return tbl

    def _render_row(self, row_node: ASTNode, row_idx: int, col_count: int) -> Element:
        """Render a single table row.

        Args:
            row_node: TABLE_ROW ASTNode
            row_idx: Zero-based row index
            col_count: Total number of columns in table

        Returns:
            ElementTree Element representing hp:tr
        """
        tr = ET.Element(f"{{{self.HP_NS}}}tr")

        cells = row_node.children
        for col_idx, cell_node in enumerate(cells):
            if col_idx >= col_count:
                break  # Don't exceed column count
            if cell_node.type != NodeType.TABLE_CELL:
                continue
            tc = self._render_cell(cell_node, row_idx, col_idx)
            tr.append(tc)

        # Pad row with empty cells if needed
        for col_idx in range(len(cells), col_count):
            tc = self._render_empty_cell(row_idx, col_idx)
            tr.append(tc)

        return tr

    def _render_cell(self, cell_node: ASTNode, row_idx: int, col_idx: int) -> Element:
        """Render a single table cell.

        Args:
            cell_node: TABLE_CELL ASTNode
            row_idx: Zero-based row index
            col_idx: Zero-based column index

        Returns:
            ElementTree Element representing hp:tc
        """
        tc = ET.Element(f"{{{self.HP_NS}}}tc")
        tc.set("colAddr", str(col_idx))
        tc.set("rowAddr", str(row_idx))
        tc.set("colSpan", "1")
        tc.set("rowSpan", "1")

        # Cell properties
        tc_pr = ET.SubElement(tc, f"{{{self.HP_NS}}}tcPr")

        # Cell address
        cell_addr = ET.SubElement(tc_pr, f"{{{self.HP_NS}}}cellAddr")
        cell_addr.set("colAddr", str(col_idx))
        cell_addr.set("rowAddr", str(row_idx))

        # Cell size
        sz = ET.SubElement(tc_pr, f"{{{self.HP_NS}}}sz")
        sz.set("width", str(self.default_col_width))
        sz.set("height", str(self.default_row_height))

        # Cell border and fill (special styling for header cells)
        is_header = cell_node.is_header
        if is_header:
            tc_border_fill = ET.SubElement(tc_pr, f"{{{self.HP_NS}}}tcBorderFill")
            tc_border_fill.set("borderFill", str(self.header_border_fill_id))

            fill_brush = ET.SubElement(tc_border_fill, f"{{{self.HP_NS}}}fillBrush")
            win_brush = ET.SubElement(fill_brush, f"{{{self.HP_NS}}}winBrush")
            win_brush.set("faceColor", self.header_bg_color)

        # Cell content
        sub_list = ET.SubElement(tc, f"{{{self.HP_NS}}}subList")

        # Extract text from cell and determine alignment
        cell_text = self._get_cell_text(cell_node)
        align = cell_node.align or "left"

        # Create paragraph with content
        p = self._make_cell_paragraph(cell_text, is_header, align)
        sub_list.append(p)

        return tc

    def _render_empty_cell(self, row_idx: int, col_idx: int) -> Element:
        """Render an empty table cell for padding.

        Args:
            row_idx: Zero-based row index
            col_idx: Zero-based column index

        Returns:
            ElementTree Element representing hp:tc
        """
        tc = ET.Element(f"{{{self.HP_NS}}}tc")
        tc.set("colAddr", str(col_idx))
        tc.set("rowAddr", str(row_idx))
        tc.set("colSpan", "1")
        tc.set("rowSpan", "1")

        # Cell properties
        tc_pr = ET.SubElement(tc, f"{{{self.HP_NS}}}tcPr")

        cell_addr = ET.SubElement(tc_pr, f"{{{self.HP_NS}}}cellAddr")
        cell_addr.set("colAddr", str(col_idx))
        cell_addr.set("rowAddr", str(row_idx))

        sz = ET.SubElement(tc_pr, f"{{{self.HP_NS}}}sz")
        sz.set("width", str(self.default_col_width))
        sz.set("height", str(self.default_row_height))

        # Empty content
        sub_list = ET.SubElement(tc, f"{{{self.HP_NS}}}subList")
        p = ET.SubElement(sub_list, f"{{{self.HP_NS}}}p")

        return tc

    def _get_cell_text(self, cell_node: ASTNode) -> str:
        """Extract plain text from a cell node by collecting from all children.

        This recursively walks the cell's children to extract all text content,
        handling inline formatting nodes like BOLD, ITALIC, etc.

        Args:
            cell_node: TABLE_CELL ASTNode

        Returns:
            Concatenated plain text from cell
        """
        def extract_text(node: ASTNode) -> str:
            """Recursively extract text from node and children."""
            parts: list[str] = []

            # Direct text content
            if node.text:
                parts.append(node.text)

            # Recurse into children
            for child in node.children:
                parts.append(extract_text(child))

            return "".join(parts)

        text = extract_text(cell_node)
        return text.strip()

    def _make_cell_paragraph(self, text: str, is_header: bool, align: str) -> Element:
        """Create an hp:p element for cell content.

        Args:
            text: Cell text content
            is_header: Whether this is a header cell (applies bold)
            align: Text alignment ("left", "center", "right", or "")

        Returns:
            ElementTree Element representing hp:p
        """
        p = ET.Element(f"{{{self.HP_NS}}}p")

        # Paragraph properties for alignment
        if align and align in ("center", "right"):
            p_pr = ET.SubElement(p, f"{{{self.HP_NS}}}pPr")
            align_elem = ET.SubElement(p_pr, f"{{{self.HP_NS}}}align")
            align_elem.set("type", align)

        # Empty cell - just return empty paragraph
        if not text:
            return p

        # Create run with text
        run = ET.SubElement(p, f"{{{self.HP_NS}}}run")

        # Run properties (bold for headers)
        if is_header:
            r_pr = ET.SubElement(run, f"{{{self.HP_NS}}}rPr")
            ET.SubElement(r_pr, f"{{{self.HP_NS}}}bold")

        # Text element
        t = ET.SubElement(run, f"{{{self.HP_NS}}}t")
        t.text = text

        return p

    def _create_empty_row(self) -> ASTNode:
        """Create a placeholder empty row for empty tables.

        Returns:
            TABLE_ROW ASTNode with a single empty cell
        """
        from md2hwpx.parser import ASTNode

        empty_cell = ASTNode(
            type=NodeType.TABLE_CELL,
            text="",
            children=[],
            align="",
            is_header=False
        )

        return ASTNode(
            type=NodeType.TABLE_ROW,
            children=[empty_cell]
        )
