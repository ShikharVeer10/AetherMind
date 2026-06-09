from typing import Dict, List


class SemanticTableService:

    def build_table_json(
        self,
        table_cells: List[Dict],
        table_bbox: Dict
    ) -> Dict:

        rows = {}
        cols = {}

        for cell in table_cells:

            row = cell["row"]
            col = cell["col"]

            rows[row] = True
            cols[col] = True

        return {
            "table_type": "semantic_table",

            "bbox": table_bbox,

            "row_count": len(rows),
            "column_count": len(cols),

            "cells": table_cells
        }

    def analyze_visual_table(
    self,
    visual_table
    ):

        rows = visual_table["rows"]

        return {
            "summary":
                f"{len(rows)} rows detected",

            "table_category":
                "consulting_framework",

            "confidence":
                0.8
        }