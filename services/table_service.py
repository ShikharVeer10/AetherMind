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
        Deep structural analysis to detect sophisticated table patterns:
        - Multi-level hierarchical headers (n-tier)
        - Pivot/Cross-tab structures
        - Asymmetric grids (merged cells)
        - Key-Value pairs vs Matrix data
        - Section-based row grouping
        """
        import re
        if not table_data:
            return {}

        num_rows = len(table_data)
        num_cols = max(len(row) for row in table_data) if num_rows > 0 else 0
        padded_table_data = [row + [""] * (num_cols - len(row)) for row in table_data]

        # 1. Detect Header Depth (hierarchical headers)
        header_depth = 0
        for i in range(min(4, num_rows)):
            row_str = "".join(padded_table_data[i]).strip()
            # If row is empty or looks like a continuation of headers (duplicated cells for spans)
            if i < num_rows - 1:
                unique_cells = len(set(c for c in padded_table_data[i] if c.strip()))
                if unique_cells < num_cols * 0.5: # Many merged cells usually indicates a top-level category header
                    header_depth = i + 1
                else:
                    break
        
        # 2. Detect Pivot Structure (headers on both X and Y axis)
        is_pivot = False
        if num_rows > 1 and num_cols > 1:
            first_col_headers = sum(1 for r in range(header_depth, num_rows) if padded_table_data[r][0].strip())
            if first_col_headers > (num_rows - header_depth) * 0.8:
                is_pivot = True

        # 3. Detect Row Sections (Sub-headers within the body)
        section_rows = []
        for i in range(header_depth, num_rows):
            non_empty = [c.strip() for c in padded_table_data[i] if c.strip()]
            if len(non_empty) == 1 and i < num_rows - 1:
                section_rows.append(i)

        # 4. Detect Financial/Data intensity
        all_text = " ".join([" ".join(r) for r in padded_table_data]).lower()
        is_financial = any(kw in all_text for kw in {"revenue", "ebitda", "profit", "budget", "cost", "total", "variance"})
        has_numeric_density = sum(1 for r in padded_table_data for c in r if re.search(r'\d', c)) > (num_rows * num_cols * 0.4)

        return {
            "header_depth": header_depth or 1,
            "is_pivot_structure": is_pivot,
            "section_rows": section_rows,
            "is_asymmetric": "merged_cells" in locals() or header_depth > 1, # Heuristic
            "is_financial": is_financial,
            "has_numeric_density": has_numeric_density,
            "dimensions": {"rows": num_rows, "cols": num_cols},
            "table_archetype": self._infer_archetype(header_depth, is_pivot, section_rows, is_financial)
        }

    def _infer_archetype(self, header_depth, is_pivot, section_rows, is_financial) -> str:
        if is_pivot and header_depth > 1: return "complex_cross_tab"
        if section_rows: return "sectioned_report"
        if is_pivot: return "matrix_comparison"
        if is_financial: return "financial_statement"
        return "standard_list"

    def generate_semantic_context(self, table_data: List[List[str]]) -> dict:
        if not table_data:
            return {}

        structure = self.analyze_structure(table_data)
        
        # Dense reconstruction strategy for LLM
        strategy = []
        if structure["table_archetype"] == "complex_cross_tab":
            strategy.append("Recreate as a multi-tier hierarchical matrix. Map the top {d} rows as spanning headers.".format(d=structure["header_depth"]))
        if structure["is_pivot_structure"]:
            strategy.append("The first column contains primary row identifiers; treat as Y-axis headers.")
        if structure["section_rows"]:
            strategy.append("This table contains mid-table section headers at rows {r}. These should span the full width.".format(r=structure["section_rows"]))
        
        return {
            "archetype": structure["table_archetype"],
            "structural_summary": "A {a} with {r} rows and {c} columns.".format(a=structure["table_archetype"], r=structure["dimensions"]["rows"], c=structure["dimensions"]["cols"]),
            "reconstruction_strategy": " ".join(strategy),
            "key_insights": self.generate_key_insights(table_data),
            "logical_reading_order": "column-major" if structure["is_pivot_structure"] else "row-major"
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

        insights = self.generate_key_insights(table_data)
        if insights:
            interpretation_parts.append(f"Key insights: {' '.join(insights)}")
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

    def build_reconstruction_payload(
        self,
        table_id: str,
        raw_table_content: List[List[str]],
        table_structure: dict,
        table_render_model: dict,
        table_semantics: dict,
        is_visual: bool,
        table_geometry: dict = None,
        raw_table_styles: List[List[Any]] = None
    ) -> "TableReconstructionModel":
        from models.document_model import (
            TableReconstructionModel,
            TableCellModel,
            TableSemanticStructureModel,
            TableRenderModel
        )
        
        if not raw_table_content:
            return None

        num_rows = len(raw_table_content)
        num_cols = max(len(r) for r in raw_table_content) if num_rows > 0 else 0

        headers = [c.strip() for c in raw_table_content[0]] if num_rows > 0 else []
        row_headers = [r[0].strip() for r in raw_table_content[1:] if len(r) > 0] if num_rows > 1 else []

        merged_cells_data = table_structure.get("merged_cells", [])

        cells = []
        for r_idx, row in enumerate(raw_table_content):
            for c_idx, text in enumerate(row):
                role = "data"
                importance = "normal"
                
                # Check for spans from merged_cells_data
                row_span = 1
                column_span = 1
                for mc in merged_cells_data:
                    if mc.get("row") == r_idx and mc.get("col") == c_idx:
                        row_span = mc.get("row_span", 1)
                        column_span = mc.get("col_span", 1)
                        break

                if r_idx == 0:
                    role = "header"
                    importance = "high"
                elif c_idx == 0:
                    role = "row_header"
                elif r_idx in table_structure.get("total_rows", []):
                    role = "summary"
                    importance = "high"
                elif r_idx in table_structure.get("subtotal_rows", []):
                    role = "subtotal"

                cell_style = None
                if raw_table_styles and r_idx < len(raw_table_styles) and c_idx < len(raw_table_styles[r_idx]):
                    cell_style = raw_table_styles[r_idx][c_idx]

                cells.append(TableCellModel(
                    row=r_idx,
                    column=c_idx,
                    text=text.strip(),
                    row_span=row_span,
                    column_span=column_span,
                    role=role,
                    importance=importance,
                    semantic_meaning=table_semantics.get("key_insights", [""])[0] if table_semantics.get("key_insights") else "",
                    cell_geometry={},
                    style=cell_style
                ))
        
        semantic_structure = TableSemanticStructureModel(
            comparison_dimension=headers if table_structure.get("is_comparison_table") else [],
            evaluation_dimension=row_headers if table_structure.get("is_comparison_table") else [],
            decision_dimension=[]
        )

        render_model = TableRenderModel(
            layout_type="matrix" if table_structure.get("is_comparison_table") else "grid",
            header_rows=[0] if num_rows > 0 else [],
            body_rows=list(range(1, num_rows)),
            grouped_columns=table_structure.get("grouped_column_indices", []),
            grouped_rows=table_structure.get("grouped_row_indices", []),
            merged_regions=merged_cells_data,
            visual_hierarchy=["header"] + (["summary"] if table_structure.get("has_totals") else [])
        )
        
        reqs = ["Preserve row hierarchy", "Preserve column hierarchy"]
        if table_structure.get("is_comparison_table"):
            reqs.append("Preserve comparison relationships")
        if table_structure.get("has_grouped_rows"):
            reqs.append("Preserve grouping structure")
        if table_structure.get("is_financial_table"):
            reqs.append("Preserve financial calculation logic")

        table_type = "standard"
        if table_structure.get("is_comparison_table"):
            table_type = "comparison_matrix"
        elif table_structure.get("is_financial_table"):
            table_type = "financial_statement"

        # Standardized Guide for Downstream LLMs
        guide = (
            "INTERPRETATION GUIDE: This table uses a {archetype} structure. "
            "1. Header Hierarchy: Treat the first {h_depth} rows as multi-level headers. "
            "2. Grid Mapping: Use the 'cells' array to extract data. "
            "3. Merged Regions: Refer to 'merged_cells' to identify specific spanning instructions (colspan/rowspan). "
            "4. Reconstruction: {strategy}"
        ).format(
            archetype=table_semantics.get("archetype", "standard"),
            h_depth=table_structure.get("header_depth", 1),
            strategy=table_semantics.get("reconstruction_strategy", "Maintain exact grid alignment.")
        )

        return TableReconstructionModel(
            table_id=table_id,
            table_type=table_type,
            visual_table=is_visual,
            rows=num_rows,
            columns=num_cols,
            headers=headers,
            row_headers=row_headers,
            cells=cells,
            merged_cells=merged_cells_data,
            semantic_structure=semantic_structure,
            table_geometry=table_geometry or {},
            table_render_model=render_model,
            functional_equivalence_requirements=reqs,
            reconstruction_strategy=table_semantics.get("reconstruction_strategy", ""),
            interpretation_guide=guide
        )