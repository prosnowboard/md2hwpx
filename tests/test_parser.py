"""Tests for the Markdown parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from md2hwpx.parser import ASTNode, MarkdownParser, NodeType

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_nodes(root: ASTNode, ntype: NodeType) -> list[ASTNode]:
    """Recursively collect all nodes of *ntype* under *root*."""
    found: list[ASTNode] = []
    if root.type == ntype:
        found.append(root)
    for child in root.children:
        found.extend(find_nodes(child, ntype))
    return found


def first_node(root: ASTNode, ntype: NodeType) -> ASTNode:
    nodes = find_nodes(root, ntype)
    assert nodes, f"No {ntype.value} node found"
    return nodes[0]


def collect_text(node: ASTNode) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node.children:
        parts.append(collect_text(child))
    return "".join(parts)


@pytest.fixture
def parser() -> MarkdownParser:
    return MarkdownParser()


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------

class TestHeadings:
    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_heading_levels(self, parser: MarkdownParser, level: int) -> None:
        md = f"{'#' * level} Heading Level {level}"
        doc = parser.parse(md)
        headings = find_nodes(doc, NodeType.HEADING)
        assert len(headings) == 1
        assert headings[0].level == level

    def test_heading_text_content(self, parser: MarkdownParser) -> None:
        doc = parser.parse("# Hello World")
        heading = first_node(doc, NodeType.HEADING)
        assert "Hello World" in collect_text(heading)

    def test_heading_with_inline(self, parser: MarkdownParser) -> None:
        doc = parser.parse("## **Bold** Heading")
        heading = first_node(doc, NodeType.HEADING)
        assert find_nodes(heading, NodeType.BOLD)

    def test_multiple_headings(self, parser: MarkdownParser) -> None:
        md = "# H1\n\n## H2\n\n### H3\n"
        doc = parser.parse(md)
        headings = find_nodes(doc, NodeType.HEADING)
        assert len(headings) == 3
        assert [h.level for h in headings] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Paragraphs
# ---------------------------------------------------------------------------

class TestParagraphs:
    def test_simple_paragraph(self, parser: MarkdownParser) -> None:
        doc = parser.parse("Hello, world!")
        paras = find_nodes(doc, NodeType.PARAGRAPH)
        assert len(paras) == 1
        assert "Hello, world!" in collect_text(paras[0])

    def test_multiple_paragraphs(self, parser: MarkdownParser) -> None:
        md = "First paragraph.\n\nSecond paragraph.\n\nThird."
        doc = parser.parse(md)
        paras = find_nodes(doc, NodeType.PARAGRAPH)
        assert len(paras) == 3

    def test_paragraph_with_mixed_inline(self, parser: MarkdownParser) -> None:
        md = "Normal **bold** and *italic* and `code`."
        doc = parser.parse(md)
        para = first_node(doc, NodeType.PARAGRAPH)
        assert find_nodes(para, NodeType.BOLD)
        assert find_nodes(para, NodeType.ITALIC)
        assert find_nodes(para, NodeType.INLINE_CODE)


# ---------------------------------------------------------------------------
# Inline formatting
# ---------------------------------------------------------------------------

class TestInlineFormatting:
    def test_bold(self, parser: MarkdownParser) -> None:
        doc = parser.parse("**bold text**")
        bold = first_node(doc, NodeType.BOLD)
        assert collect_text(bold) == "bold text"

    def test_italic(self, parser: MarkdownParser) -> None:
        doc = parser.parse("*italic text*")
        italic = first_node(doc, NodeType.ITALIC)
        assert collect_text(italic) == "italic text"

    def test_strikethrough(self, parser: MarkdownParser) -> None:
        doc = parser.parse("~~struck~~")
        strike = first_node(doc, NodeType.STRIKETHROUGH)
        assert collect_text(strike) == "struck"

    def test_inline_code(self, parser: MarkdownParser) -> None:
        doc = parser.parse("`code here`")
        code = first_node(doc, NodeType.INLINE_CODE)
        assert code.text == "code here"

    def test_bold_inside_italic(self, parser: MarkdownParser) -> None:
        doc = parser.parse("*italic with **bold** inside*")
        italic = first_node(doc, NodeType.ITALIC)
        assert find_nodes(italic, NodeType.BOLD)


# ---------------------------------------------------------------------------
# Code blocks
# ---------------------------------------------------------------------------

class TestCodeBlocks:
    def test_code_block_with_language(self, parser: MarkdownParser) -> None:
        md = "```python\nprint('hello')\n```"
        doc = parser.parse(md)
        code = first_node(doc, NodeType.CODE_BLOCK)
        assert code.language == "python"
        assert "print" in code.text

    def test_code_block_without_language(self, parser: MarkdownParser) -> None:
        md = "```\nplain code\n```"
        doc = parser.parse(md)
        code = first_node(doc, NodeType.CODE_BLOCK)
        assert code.language == ""
        assert "plain code" in code.text

    def test_code_block_preserves_content(self, parser: MarkdownParser) -> None:
        md = "```js\nconst x = 1;\nconst y = 2;\n```"
        doc = parser.parse(md)
        code = first_node(doc, NodeType.CODE_BLOCK)
        assert "const x = 1;" in code.text
        assert "const y = 2;" in code.text


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

class TestLists:
    def test_unordered_list(self, parser: MarkdownParser) -> None:
        md = "- Item A\n- Item B\n- Item C\n"
        doc = parser.parse(md)
        ul = first_node(doc, NodeType.UNORDERED_LIST)
        items = find_nodes(ul, NodeType.LIST_ITEM)
        assert len(items) >= 3

    def test_ordered_list(self, parser: MarkdownParser) -> None:
        md = "1. First\n2. Second\n3. Third\n"
        doc = parser.parse(md)
        ol = first_node(doc, NodeType.ORDERED_LIST)
        items = find_nodes(ol, NodeType.LIST_ITEM)
        assert len(items) >= 3

    def test_nested_unordered_list(self, parser: MarkdownParser) -> None:
        md = "- Parent\n  - Child\n    - Grandchild\n"
        doc = parser.parse(md)
        lists = find_nodes(doc, NodeType.UNORDERED_LIST)
        assert len(lists) >= 2

    def test_nested_ordered_list(self, parser: MarkdownParser) -> None:
        md = "1. First\n   1. Sub one\n   2. Sub two\n2. Second\n"
        doc = parser.parse(md)
        ols = find_nodes(doc, NodeType.ORDERED_LIST)
        assert len(ols) >= 2


# ---------------------------------------------------------------------------
# Task lists
# ---------------------------------------------------------------------------

class TestTaskLists:
    def test_checked_task(self, parser: MarkdownParser) -> None:
        md = "- [x] Done task\n"
        doc = parser.parse(md)
        tasks = find_nodes(doc, NodeType.TASK_LIST_ITEM)
        assert len(tasks) >= 1
        assert tasks[0].checked is True

    def test_unchecked_task(self, parser: MarkdownParser) -> None:
        md = "- [ ] Pending task\n"
        doc = parser.parse(md)
        tasks = find_nodes(doc, NodeType.TASK_LIST_ITEM)
        assert len(tasks) >= 1
        assert tasks[0].checked is False

    def test_mixed_tasks(self, parser: MarkdownParser) -> None:
        md = "- [x] Done\n- [ ] Not done\n- [x] Also done\n"
        doc = parser.parse(md)
        tasks = find_nodes(doc, NodeType.TASK_LIST_ITEM)
        assert len(tasks) >= 3


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class TestTables:
    def test_simple_table(self, parser: MarkdownParser) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        doc = parser.parse(md)
        table = first_node(doc, NodeType.TABLE)
        rows = find_nodes(table, NodeType.TABLE_ROW)
        assert len(rows) >= 2

    def test_table_header_cells(self, parser: MarkdownParser) -> None:
        md = "| Name | Age |\n|------|-----|\n| Alice | 30 |\n"
        doc = parser.parse(md)
        cells = find_nodes(doc, NodeType.TABLE_CELL)
        header_cells = [c for c in cells if c.is_header]
        assert len(header_cells) >= 2

    def test_table_alignment(self, parser: MarkdownParser) -> None:
        md = "| Left | Center | Right |\n|:-----|:------:|------:|\n| a | b | c |\n"
        doc = parser.parse(md)
        cells = find_nodes(doc, NodeType.TABLE_CELL)
        header_cells = [c for c in cells if c.is_header]
        if header_cells:
            aligns = [c.align for c in header_cells]
            assert "left" in aligns
            assert "center" in aligns
            assert "right" in aligns

    def test_table_body_cells(self, parser: MarkdownParser) -> None:
        md = "| X | Y |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
        doc = parser.parse(md)
        cells = find_nodes(doc, NodeType.TABLE_CELL)
        body_cells = [c for c in cells if not c.is_header]
        assert len(body_cells) >= 4


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------

class TestBlockquotes:
    def test_simple_blockquote(self, parser: MarkdownParser) -> None:
        md = "> Quoted text here."
        doc = parser.parse(md)
        bq = first_node(doc, NodeType.BLOCKQUOTE)
        assert "Quoted text" in collect_text(bq)

    def test_nested_blockquote(self, parser: MarkdownParser) -> None:
        md = "> Outer\n>\n> > Inner nested\n"
        doc = parser.parse(md)
        bqs = find_nodes(doc, NodeType.BLOCKQUOTE)
        assert len(bqs) >= 2

    def test_blockquote_with_paragraphs(self, parser: MarkdownParser) -> None:
        md = "> First paragraph.\n>\n> Second paragraph.\n"
        doc = parser.parse(md)
        bq = first_node(doc, NodeType.BLOCKQUOTE)
        paras = find_nodes(bq, NodeType.PARAGRAPH)
        assert len(paras) >= 2


# ---------------------------------------------------------------------------
# Horizontal rules
# ---------------------------------------------------------------------------

class TestHorizontalRules:
    def test_triple_dash(self, parser: MarkdownParser) -> None:
        md = "Above\n\n---\n\nBelow"
        doc = parser.parse(md)
        assert find_nodes(doc, NodeType.HORIZONTAL_RULE)

    def test_triple_asterisk(self, parser: MarkdownParser) -> None:
        md = "Above\n\n***\n\nBelow"
        doc = parser.parse(md)
        assert find_nodes(doc, NodeType.HORIZONTAL_RULE)


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

class TestLinks:
    def test_inline_link(self, parser: MarkdownParser) -> None:
        md = "[Click here](https://example.com)"
        doc = parser.parse(md)
        link = first_node(doc, NodeType.LINK)
        assert link.url == "https://example.com"
        assert "Click here" in collect_text(link)

    def test_link_with_title(self, parser: MarkdownParser) -> None:
        md = '[Link](https://example.com "My Title")'
        doc = parser.parse(md)
        link = first_node(doc, NodeType.LINK)
        assert link.url == "https://example.com"
        assert link.title == "My Title"


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class TestImages:
    def test_image(self, parser: MarkdownParser) -> None:
        md = "![Alt text](https://example.com/img.png)"
        doc = parser.parse(md)
        img = first_node(doc, NodeType.IMAGE)
        assert img.url == "https://example.com/img.png"

    def test_image_with_title(self, parser: MarkdownParser) -> None:
        md = '![Photo](https://example.com/photo.jpg "Photo Title")'
        doc = parser.parse(md)
        img = first_node(doc, NodeType.IMAGE)
        assert img.title == "Photo Title"


# ---------------------------------------------------------------------------
# Footnotes
# ---------------------------------------------------------------------------

class TestFootnotes:
    def test_footnote_ref(self, parser: MarkdownParser) -> None:
        md = "Text with a footnote[^1].\n\n[^1]: The definition.\n"
        doc = parser.parse(md)
        refs = find_nodes(doc, NodeType.FOOTNOTE_REF)
        assert len(refs) >= 1

    def test_footnote_def(self, parser: MarkdownParser) -> None:
        md = "Text[^abc].\n\n[^abc]: Definition here.\n"
        doc = parser.parse(md)
        defs = find_nodes(doc, NodeType.FOOTNOTE_DEF)
        assert len(defs) >= 1

    def test_multiple_footnotes(self, parser: MarkdownParser) -> None:
        md = "A[^1] and B[^2].\n\n[^1]: First.\n[^2]: Second.\n"
        doc = parser.parse(md)
        defs = find_nodes(doc, NodeType.FOOTNOTE_DEF)
        assert len(defs) >= 2


# ---------------------------------------------------------------------------
# Line breaks
# ---------------------------------------------------------------------------

class TestLineBreaks:
    def test_hard_break(self, parser: MarkdownParser) -> None:
        md = "Line one  \nLine two"
        doc = parser.parse(md)
        breaks = find_nodes(doc, NodeType.LINE_BREAK)
        assert len(breaks) >= 1

    def test_soft_break(self, parser: MarkdownParser) -> None:
        md = "Line one\nLine two"
        doc = parser.parse(md)
        paras = find_nodes(doc, NodeType.PARAGRAPH)
        assert len(paras) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_input(self, parser: MarkdownParser) -> None:
        doc = parser.parse("")
        assert doc.type == NodeType.DOCUMENT
        assert doc.children == []

    def test_whitespace_only(self, parser: MarkdownParser) -> None:
        doc = parser.parse("   \n\n   \n")
        assert doc.type == NodeType.DOCUMENT

    def test_single_word(self, parser: MarkdownParser) -> None:
        doc = parser.parse("Hello")
        assert doc.type == NodeType.DOCUMENT
        paras = find_nodes(doc, NodeType.PARAGRAPH)
        assert len(paras) == 1

    def test_code_block_no_language(self, parser: MarkdownParser) -> None:
        md = "```\nno language\n```"
        doc = parser.parse(md)
        code = first_node(doc, NodeType.CODE_BLOCK)
        assert code.language == ""


# ---------------------------------------------------------------------------
# Korean text
# ---------------------------------------------------------------------------

class TestKoreanText:
    def test_korean_paragraph(self, parser: MarkdownParser) -> None:
        doc = parser.parse("안녕하세요, 세계!")
        assert "안녕하세요" in collect_text(doc)

    def test_korean_heading(self, parser: MarkdownParser) -> None:
        doc = parser.parse("# 한글 제목")
        heading = first_node(doc, NodeType.HEADING)
        assert "한글" in collect_text(heading)

    def test_korean_bold(self, parser: MarkdownParser) -> None:
        doc = parser.parse("**굵은 글씨**")
        bold = first_node(doc, NodeType.BOLD)
        assert "굵은" in collect_text(bold)

    def test_korean_table(self, parser: MarkdownParser) -> None:
        md = "| 이름 | 나이 |\n|------|------|\n| 홍길동 | 30 |\n"
        doc = parser.parse(md)
        table = first_node(doc, NodeType.TABLE)
        assert "홍길동" in collect_text(table)

    def test_mixed_korean_english(self, parser: MarkdownParser) -> None:
        md = "This is **한글** mixed with English."
        doc = parser.parse(md)
        bold = first_node(doc, NodeType.BOLD)
        assert "한글" in collect_text(bold)


# ---------------------------------------------------------------------------
# Sample fixture
# ---------------------------------------------------------------------------

class TestSampleFixture:
    @pytest.fixture
    def sample_doc(self, parser: MarkdownParser) -> ASTNode:
        sample_path = FIXTURES_DIR / "sample.md"
        assert sample_path.exists(), f"Fixture not found: {sample_path}"
        md_text = sample_path.read_text(encoding="utf-8")
        return parser.parse(md_text)

    def test_fixture_parses(self, sample_doc: ASTNode) -> None:
        assert sample_doc.type == NodeType.DOCUMENT
        assert len(sample_doc.children) > 0

    def test_fixture_has_headings(self, sample_doc: ASTNode) -> None:
        headings = find_nodes(sample_doc, NodeType.HEADING)
        assert len(headings) >= 6

    def test_fixture_has_table(self, sample_doc: ASTNode) -> None:
        assert find_nodes(sample_doc, NodeType.TABLE)

    def test_fixture_has_code_blocks(self, sample_doc: ASTNode) -> None:
        blocks = find_nodes(sample_doc, NodeType.CODE_BLOCK)
        assert len(blocks) >= 2

    def test_fixture_has_blockquotes(self, sample_doc: ASTNode) -> None:
        assert find_nodes(sample_doc, NodeType.BLOCKQUOTE)

    def test_fixture_has_horizontal_rules(self, sample_doc: ASTNode) -> None:
        hrs = find_nodes(sample_doc, NodeType.HORIZONTAL_RULE)
        assert len(hrs) >= 2

    def test_fixture_has_links(self, sample_doc: ASTNode) -> None:
        assert find_nodes(sample_doc, NodeType.LINK)

    def test_fixture_has_images(self, sample_doc: ASTNode) -> None:
        assert find_nodes(sample_doc, NodeType.IMAGE)

    def test_fixture_has_korean(self, sample_doc: ASTNode) -> None:
        text = collect_text(sample_doc)
        assert "한글" in text
        assert "HWPX" in text

    def test_fixture_has_task_lists(self, sample_doc: ASTNode) -> None:
        tasks = find_nodes(sample_doc, NodeType.TASK_LIST_ITEM)
        assert len(tasks) >= 2

    def test_fixture_has_line_breaks(self, sample_doc: ASTNode) -> None:
        breaks = find_nodes(sample_doc, NodeType.LINE_BREAK)
        assert len(breaks) >= 1
