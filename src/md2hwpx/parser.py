"""Markdown parser that produces an intermediate AST for HWPX conversion.

Uses mistune v3 to parse Markdown and converts the token stream into
a normalised AST representation defined by :class:`ASTNode`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import mistune


# ---------------------------------------------------------------------------
# AST node definitions
# ---------------------------------------------------------------------------

class NodeType(Enum):
    DOCUMENT = "document"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TEXT = "text"
    BOLD = "bold"
    ITALIC = "italic"
    STRIKETHROUGH = "strikethrough"
    INLINE_CODE = "inline_code"
    CODE_BLOCK = "code_block"
    ORDERED_LIST = "ordered_list"
    UNORDERED_LIST = "unordered_list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    BLOCKQUOTE = "blockquote"
    HORIZONTAL_RULE = "horizontal_rule"
    LINK = "link"
    IMAGE = "image"
    FOOTNOTE_REF = "footnote_ref"
    FOOTNOTE_DEF = "footnote_def"
    TASK_LIST_ITEM = "task_list_item"
    LINE_BREAK = "line_break"
    SOFT_BREAK = "soft_break"


@dataclass
class ASTNode:
    type: NodeType
    children: list[ASTNode] = field(default_factory=list)
    text: str = ""
    # Heading
    level: int = 0
    # Code block
    language: str = ""
    # Link / Image
    url: str = ""
    title: str = ""
    alt: str = ""
    # Table cell
    align: str = ""
    is_header: bool = False
    # Task list
    checked: bool = False
    # Footnote
    footnote_id: str = ""
    # Ordered list start
    start: int = 1


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class MarkdownParser:
    """Parse Markdown text into an :class:`ASTNode` tree."""

    def __init__(self) -> None:
        self._md = mistune.create_markdown(
            renderer=None,  # AST mode
            plugins=["table", "strikethrough", "footnotes", "task_lists"],
        )

    # -- public API ---------------------------------------------------------

    def parse(self, markdown_text: str) -> ASTNode:
        """Return a *DOCUMENT* ``ASTNode`` for *markdown_text*."""
        tokens: list[dict[str, Any]] = self._md(markdown_text)  # type: ignore[assignment]
        children = self._convert_tokens(tokens)
        return ASTNode(type=NodeType.DOCUMENT, children=children)

    # -- token conversion ---------------------------------------------------

    def _convert_tokens(self, tokens: list[dict[str, Any]]) -> list[ASTNode]:
        nodes: list[ASTNode] = []
        for tok in tokens:
            ttype = tok.get("type", "")
            # Flatten footnotes container into individual definitions
            if ttype == "footnotes":
                for child in tok.get("children", []):
                    if child.get("type") == "footnote_item":
                        nodes.append(self._handle_footnote_item(child))
                continue
            node = self._convert_token(tok)
            if node is not None:
                nodes.append(node)
        return nodes

    def _convert_token(self, tok: dict[str, Any]) -> Optional[ASTNode]:
        ttype = tok.get("type", "")
        handler = getattr(self, f"_handle_{ttype}", None)
        if handler:
            return handler(tok)
        # Fallback – treat unknown tokens as plain text if they carry text.
        raw = tok.get("raw", tok.get("text", ""))
        if raw:
            return ASTNode(type=NodeType.TEXT, text=str(raw))
        return None

    # -- inline helpers -----------------------------------------------------

    def _convert_inline(self, children: Any) -> list[ASTNode]:
        if children is None:
            return []
        if isinstance(children, str):
            return [ASTNode(type=NodeType.TEXT, text=children)]
        if isinstance(children, list):
            return self._convert_tokens(children)
        return []

    # -- block handlers -----------------------------------------------------

    def _handle_heading(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children") or tok.get("text", "")
        return ASTNode(
            type=NodeType.HEADING,
            level=tok.get("attrs", {}).get("level", tok.get("level", 1)),
            children=self._convert_inline(children_raw),
        )

    def _handle_paragraph(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children") or tok.get("text", "")
        return ASTNode(
            type=NodeType.PARAGRAPH,
            children=self._convert_inline(children_raw),
        )

    def _handle_thematic_break(self, _tok: dict) -> ASTNode:
        return ASTNode(type=NodeType.HORIZONTAL_RULE)

    # -- inline handlers ----------------------------------------------------

    def _handle_text(self, tok: dict) -> ASTNode:
        raw = tok.get("raw", tok.get("text", tok.get("children", "")))
        if isinstance(raw, str):
            return ASTNode(type=NodeType.TEXT, text=raw)
        return ASTNode(type=NodeType.TEXT, children=self._convert_inline(raw))

    def _handle_strong(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children") or tok.get("text", "")
        return ASTNode(type=NodeType.BOLD, children=self._convert_inline(children_raw))

    def _handle_emphasis(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children") or tok.get("text", "")
        return ASTNode(type=NodeType.ITALIC, children=self._convert_inline(children_raw))

    def _handle_strikethrough(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children") or tok.get("text", "")
        return ASTNode(type=NodeType.STRIKETHROUGH, children=self._convert_inline(children_raw))

    def _handle_codespan(self, tok: dict) -> ASTNode:
        raw = tok.get("raw", tok.get("text", tok.get("children", "")))
        if isinstance(raw, str):
            return ASTNode(type=NodeType.INLINE_CODE, text=raw)
        return ASTNode(type=NodeType.INLINE_CODE, text=str(raw))

    def _handle_code(self, tok: dict) -> ASTNode:
        """Fenced / indented code block."""
        attrs = tok.get("attrs", {})
        raw = tok.get("raw", tok.get("text", tok.get("children", "")))
        text = raw if isinstance(raw, str) else str(raw)
        return ASTNode(
            type=NodeType.CODE_BLOCK,
            text=text,
            language=attrs.get("info", tok.get("info", "")) or "",
        )

    def _handle_block_code(self, tok: dict) -> ASTNode:
        return self._handle_code(tok)

    # -- link / image -------------------------------------------------------

    def _handle_link(self, tok: dict) -> ASTNode:
        attrs = tok.get("attrs", {})
        children_raw = tok.get("children") or tok.get("text", "")
        return ASTNode(
            type=NodeType.LINK,
            url=attrs.get("url", tok.get("link", "")),
            title=attrs.get("title", "") or "",
            children=self._convert_inline(children_raw),
        )

    def _handle_image(self, tok: dict) -> ASTNode:
        attrs = tok.get("attrs", {})
        alt = attrs.get("alt", tok.get("alt", ""))
        children_raw = tok.get("children")
        if not alt and children_raw:
            alt = self._extract_text(children_raw)
        return ASTNode(
            type=NodeType.IMAGE,
            url=attrs.get("url", tok.get("src", "")),
            title=attrs.get("title", "") or "",
            alt=alt,
        )

    # -- lists --------------------------------------------------------------

    def _handle_list(self, tok: dict) -> ASTNode:
        attrs = tok.get("attrs", {})
        ordered = attrs.get("ordered", False)
        start = attrs.get("start", 1) or 1
        children_raw = tok.get("children", [])
        items = self._convert_tokens(children_raw) if isinstance(children_raw, list) else []
        return ASTNode(
            type=NodeType.ORDERED_LIST if ordered else NodeType.UNORDERED_LIST,
            children=items,
            start=start,
        )

    def _handle_list_item(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children", [])
        children = self._convert_tokens(children_raw) if isinstance(children_raw, list) else self._convert_inline(children_raw)

        # Check for task list item
        attrs = tok.get("attrs", {})
        if "checked" in attrs:
            return ASTNode(
                type=NodeType.TASK_LIST_ITEM,
                children=children,
                checked=bool(attrs["checked"]),
            )
        return ASTNode(type=NodeType.LIST_ITEM, children=children)

    def _handle_task_list_item(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children", [])
        children = self._convert_tokens(children_raw) if isinstance(children_raw, list) else self._convert_inline(children_raw)
        attrs = tok.get("attrs", {})
        return ASTNode(
            type=NodeType.TASK_LIST_ITEM,
            children=children,
            checked=bool(attrs.get("checked", False)),
        )

    def _handle_block_text(self, tok: dict) -> ASTNode:
        """Block text inside list items."""
        children_raw = tok.get("children") or tok.get("text", "")
        return ASTNode(
            type=NodeType.PARAGRAPH,
            children=self._convert_inline(children_raw),
        )

    # -- blockquote ---------------------------------------------------------

    def _handle_block_quote(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children", [])
        children = self._convert_tokens(children_raw) if isinstance(children_raw, list) else self._convert_inline(children_raw)
        return ASTNode(type=NodeType.BLOCKQUOTE, children=children)

    def _handle_blockquote(self, tok: dict) -> ASTNode:
        return self._handle_block_quote(tok)

    # -- table --------------------------------------------------------------

    def _handle_table(self, tok: dict) -> ASTNode:
        rows: list[ASTNode] = []
        children_raw = tok.get("children", [])

        # Collect alignment info from attrs
        aligns: list[str] = []
        attrs = tok.get("attrs", {})
        if "aligns" in attrs:
            aligns = [a or "" for a in attrs["aligns"]]

        for child in children_raw:
            ctype = child.get("type", "")
            if ctype in ("table_head", "thead"):
                rows.extend(self._handle_table_section(child, is_header=True, aligns=aligns))
            elif ctype in ("table_body", "tbody"):
                rows.extend(self._handle_table_section(child, is_header=False, aligns=aligns))
            elif ctype in ("table_row", "tr"):
                rows.append(self._handle_table_row(child, is_header=False, aligns=aligns))

        return ASTNode(type=NodeType.TABLE, children=rows)

    def _handle_table_section(
        self, tok: dict, *, is_header: bool, aligns: list[str]
    ) -> list[ASTNode]:
        rows: list[ASTNode] = []
        children = tok.get("children", [])
        if not children:
            return rows

        # table_head has table_cell children directly (one implicit row)
        # table_body has table_row children, each with table_cell children
        first_child_type = children[0].get("type", "")
        if first_child_type == "table_cell":
            # Direct cells → wrap as single row
            row = self._make_table_row(children, is_header=is_header, aligns=aligns)
            rows.append(row)
        else:
            # table_row children
            for child in children:
                rows.append(self._make_table_row(
                    child.get("children", []),
                    is_header=is_header,
                    aligns=aligns,
                ))
        return rows

    def _make_table_row(
        self, cell_tokens: list[dict], *, is_header: bool, aligns: list[str]
    ) -> ASTNode:
        cells: list[ASTNode] = []
        for idx, cell_tok in enumerate(cell_tokens):
            cell_attrs = cell_tok.get("attrs", {})
            align = cell_attrs.get("align", "")
            if not align and idx < len(aligns):
                align = aligns[idx]
            cell_is_header = cell_attrs.get("head", is_header)
            children = self._convert_inline(cell_tok.get("children", []))
            cells.append(ASTNode(
                type=NodeType.TABLE_CELL,
                children=children,
                align=align or "",
                is_header=bool(cell_is_header),
            ))
        return ASTNode(type=NodeType.TABLE_ROW, children=cells)

    # -- footnotes ----------------------------------------------------------

    def _handle_footnote_ref(self, tok: dict) -> ASTNode:
        attrs = tok.get("attrs", {})
        key = tok.get("raw", "") or str(attrs.get("index", attrs.get("key", "")))
        return ASTNode(
            type=NodeType.FOOTNOTE_REF,
            footnote_id=str(key),
        )

    def _handle_footnotes(self, tok: dict) -> Optional[ASTNode]:
        """Container for footnote definitions. Flatten into individual defs."""
        children_raw = tok.get("children", [])
        # Process footnote_item children and produce FOOTNOTE_DEF nodes
        # We return a dummy wrapper; _convert_token returns single node,
        # so we handle this by returning them via a paragraph wrapper.
        # Better: add them as children of a virtual node we can flatten.
        defs: list[ASTNode] = []
        for child in children_raw:
            if child.get("type") == "footnote_item":
                defs.append(self._handle_footnote_item(child))
        if len(defs) == 1:
            return defs[0]
        # Return multiple defs – wrap in DOCUMENT-like container then flatten
        # Actually, since _convert_token returns one node, we return the first
        # and inject the rest. Better approach: override _convert_tokens to handle.
        # Simplest: return a paragraph wrapper (won't be ideal).
        # Best approach: handle in _convert_tokens specially.
        return ASTNode(type=NodeType.DOCUMENT, children=defs)

    def _handle_footnote_item(self, tok: dict) -> ASTNode:
        children_raw = tok.get("children", [])
        children = self._convert_tokens(children_raw) if isinstance(children_raw, list) else self._convert_inline(children_raw)
        attrs = tok.get("attrs", {})
        return ASTNode(
            type=NodeType.FOOTNOTE_DEF,
            footnote_id=str(attrs.get("key", attrs.get("index", ""))),
            children=children,
        )

    # -- breaks -------------------------------------------------------------

    def _handle_linebreak(self, _tok: dict) -> ASTNode:
        return ASTNode(type=NodeType.LINE_BREAK)

    def _handle_newline(self, _tok: dict) -> ASTNode:
        return ASTNode(type=NodeType.LINE_BREAK)

    def _handle_softbreak(self, _tok: dict) -> ASTNode:
        return ASTNode(type=NodeType.SOFT_BREAK)

    # -- blank / unknown ----------------------------------------------------

    def _handle_blank_line(self, _tok: dict) -> Optional[ASTNode]:
        return None

    # -- helpers ------------------------------------------------------------

    def _extract_text(self, children: Any) -> str:
        if isinstance(children, str):
            return children
        if isinstance(children, list):
            parts: list[str] = []
            for c in children:
                if isinstance(c, dict):
                    parts.append(c.get("raw", c.get("text", "")))
                elif isinstance(c, str):
                    parts.append(c)
            return "".join(parts)
        return ""
