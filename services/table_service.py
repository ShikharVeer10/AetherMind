"""
Converts raw table data (list of lists) into GitHub-Flavoured Markdown.

Called by the orchestrator for every table element found on a slide.
"""

from typing import List


class TableService:

    def to_markdown(self, table_data: List[List[str]]) -> str:
        """
        Convert a 2D list of cell strings into a GFM table.

        Example:
            [["Name", "Age"], ["Alice", "30"]]
            →
            | Name  | Age |
            |-------|-----|
            | Alice | 30  |

        If the table has only one row it is treated as a header-only table.
        """
        if not table_data:
            return ""

        escaped = [
            [str(cell).replace("\n", " ").replace("|", "\\|") for cell in row]
            for row in table_data
        ]

        header = "| " + " | ".join(escaped[0]) + " |"
        separator = "| " + " | ".join("---" for _ in escaped[0]) + " |"

        lines = [header, separator]
        for row in escaped[1:]:
            # Pad row if it has fewer cells than the header
            while len(row) < len(escaped[0]):
                row.append("")
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def analyze_structure(self, table_data: List[List[str]]) -> dict:
        """
        Analyze table structure to detect:
        - nested headers
        - grouped rows
        - grouped columns
        - subtotals
        - totals
        - comparison tables
        - audit-style financial tables
        """
        import re
        if not table_data:
            return {}

        num_rows = len(table_data)
        num_cols = len(table_data[0]) if num_rows > 0 else 0

        # Check for nested headers
        has_nested_headers = False
        if num_rows > 1:
            first_row = table_data[0]
            # Duplicate adjacent cells in header rows often represent merged cells
            has_duplicates = any(first_row[i] == first_row[i+1] and first_row[i].strip() for i in range(len(first_row)-1))
            empty_first = sum(1 for c in first_row if not c.strip())
            if empty_first > 0 or has_duplicates:
                has_nested_headers = True

        # Check for subtotals and totals
        has_subtotals = False
        has_totals = False
        total_rows = []
        subtotal_rows = []
        
        # Check for grouped rows
        grouped_row_indices = []
        for i, row in enumerate(table_data):
            row_str = " ".join(row).lower()
            if "subtotal" in row_str or "sub-total" in row_str:
                has_subtotals = True
                subtotal_rows.append(i)
            elif "total" in row_str or "sum" in row_str:
                has_totals = True
                total_rows.append(i)

            non_empty_cells = [c.strip() for c in row if c.strip()]
            if len(non_empty_cells) == 1 and i > 0 and i not in total_rows and i not in subtotal_rows:
                grouped_row_indices.append(i)

        # Check for grouped columns
        grouped_cols = []
        for col_idx in range(num_cols):
            col_cells = [table_data[row_idx][col_idx].strip() for row_idx in range(num_rows)]
            empty_count = sum(1 for c in col_cells if not c)
            if empty_count > num_rows * 0.7 and empty_count < num_rows:
                grouped_cols.append(col_idx)

        # Check for comparison tables
        is_comparison = False
        all_cells_str = " ".join(" ".join(row) for row in table_data).lower()
        if any(kw in all_cells_str for kw in ("vs", "versus", "compare", "features")):
            is_comparison = True
        yes_no_count = sum(1 for row in table_data for cell in row if cell.strip().lower() in ("yes", "no", "y", "n", "✓", "✗", "true", "false"))
        if yes_no_count > 2:
            is_comparison = True

        # Check for audit-style financial tables
        is_financial = False
        financial_keywords = {"revenue", "profit", "ebitda", "balance", "audit", "cash flow", "assets", "liabilities", "expenses", "income", "tax", "operating"}
        if any(kw in all_cells_str for kw in financial_keywords):
            is_financial = True
        financial_patterns = sum(1 for row in table_data for cell in row if re.search(r'\$\d+|\(\d+\)|\b\d+,\d{3}\b', cell))
        if financial_patterns > 1:
            is_financial = True

        return {
            "has_nested_headers": has_nested_headers,
            "has_grouped_rows": len(grouped_row_indices) > 0,
            "grouped_row_indices": grouped_row_indices,
            "has_grouped_columns": len(grouped_cols) > 0,
            "grouped_column_indices": grouped_cols,
            "has_subtotals": has_subtotals,
            "subtotal_rows": subtotal_rows,
            "has_totals": has_totals,
            "total_rows": total_rows,
            "is_comparison_table": is_comparison,
            "is_financial_table": is_financial
        }

    def generate_semantic_context(self,table_data: List[List[str]]) -> dict:

        if not table_data:
            return {}

        interpretation = self.generate_interpretation(
            table_data
    )

        headers = [
            str(c).strip()
            for c in table_data[0]
            if str(c).strip()
        ]

        entities = []

        for row in table_data[1:]:
            if row and row[0].strip():
                entities.append(row[0].strip())

        purpose = "reference"

        structure = self.analyze_structure(
            table_data
    )

        if structure.get("is_comparison_table"):
            purpose = "comparison"

        elif structure.get("is_financial_table"):
            purpose = "financial_reporting"

        elif len(headers) >= 2:
            purpose = "categorization"

        return {
            "title": self.infer_table_title(table_data),
            "purpose": purpose,
            "column_headers": headers,
            "entities": entities[:10],
            "semantic_summary": interpretation,
            "key_insights": self.generate_key_insights(table_data),
            "row_count": len(table_data),
            "column_count": len(headers),
            "raw_text": table_data,
        }
    def generate_interpretation(self, table_data: List[List[str]]) -> str:
        """
        Generate a semantic interpretation of the table content and structure.
        """
        if not table_data:
            return "Empty table."

        struct = self.analyze_structure(table_data)
        interpretation_parts = []

        table_type = "standard table"
        if struct.get("is_financial_table"):
            table_type = "audit-style financial table"
        elif struct.get("is_comparison_table"):
            table_type = "comparison table"

        interpretation_parts.append(f"This is a {table_type}.")

        headers = [c.strip() for c in table_data[0] if c.strip()]
        if headers:
            interpretation_parts.append(f"It contains columns for: {', '.join(headers)}.")

        if struct.get("has_nested_headers"):
            interpretation_parts.append("The table uses a nested header structure for multi-level category organization.")
        if struct.get("has_grouped_rows"):
            interpretation_parts.append("The table has rows grouped into sections.")
        if struct.get("has_subtotals"):
            interpretation_parts.append("The table contains subtotal rows for intermediate sums.")
        if struct.get("has_totals"):
            interpretation_parts.append("The table contains overall totals or summary rows.")

        row_identifiers = []
        for row in table_data[1:]:
            if row and row[0].strip():
                row_str = row[0].strip().lower()
                if "total" not in row_str and "sum" not in row_str:
                    row_identifiers.append(row[0].strip())
        if row_identifiers:
            interpretation_parts.append(f"Row items include: {', '.join(row_identifiers[:6])}.")

        key_insight = self.generate_key_insight(table_data)
        interpretation_parts.append(f"Key insight: {key_insight}")
        return " ".join(interpretation_parts)

    
    def generate_key_insights(self,table_data: List[List[str]]) -> List[str]:

        insights = []

        if not table_data:
            return insights

        headers = [
        c.strip()
        for c in table_data[0]
        if c.strip()
    ]

        if headers:
            insights.append(
            f"The table contains {len(headers)} key dimensions."
        )

        if len(table_data) > 1:
            insights.append(
            f"The table compares {len(table_data)-1} entities."
        )

        structure = self.analyze_structure(table_data)

        if structure.get("is_financial_table"):
            insights.append(
            "The table contains financial reporting information."
        )

        if structure.get("is_comparison_table"):
            insights.append(
            "The table is structured for side-by-side comparison."
        )
            

        return insights
    
    def infer_table_title(
    self,
    table_data: List[List[str]]
) -> str:
        headers = [
        c.strip()
        for c in table_data[0]
        if c.strip()
    ]
        if headers:
            return f"Table showing {', '.join(headers[:3])}"
        return "Untitled Table"


    def build_render_model(self, table_data, table_structure):

        if not table_data:
            return {}

        rows = len(table_data)
        cols = max(len(r) for r in table_data)

        cells = []

        for row_idx, row in enumerate(table_data):

            for col_idx in range(cols):

                value = ""

                if col_idx < len(row):
                    value = row[col_idx]

                cell_type = "data"

                if row_idx == 0:
                    cell_type = "header"

                if (table_structure.get("has_grouped_rows") and row_idx in table_structure.get("grouped_row_indices",[])):
                    cell_type = "group_header"

                cells.append(
                    {
                        "row": row_idx,
                        "column": col_idx,
                        "text": value,
                        "cell_type": cell_type,
                        "row_span": 1,
                        "col_span": 1,

                        "fill_color": None,
                        "font_size": None,
                        "font_color": None,

                        "bold": row_idx == 0,

                        "horizontal_alignment": "center",

                        "border_top": True,
                        "border_bottom": True,
                        "border_left": True,
                        "border_right": True,
                    }
                )

        return {
            "table_type": (
                "financial"
                if table_structure.get(
                    "is_financial_table"
                )
                else (
                    "comparison"
                    if table_structure.get(
                        "is_comparison_table"
                    )
                    else "generic"
                )
            ),

            "rows": rows,
            "columns": cols,

            "layout": {
                "header_rows": [0],
                "group_rows": table_structure.get(
                    "grouped_row_indices",
                    []
            ),
            "total_rows": table_structure.get(
                "total_rows",
                []
            ),
            "subtotal_rows": table_structure.get(
                "subtotal_rows",
                []
            ),
        },
        "cells": cells,
        "structure": table_structure,
    }