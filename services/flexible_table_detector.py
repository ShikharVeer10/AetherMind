from collections import defaultdict
from typing import List, Dict, Any


class FlexibleTableDetector:

    def detect_visual_tables(self, elements: List[Any]) -> List[Dict[str, Any]]:
        text_elements = [
            e for e in elements
            if e.element_type == "text_box" and e.text and e.text.strip()
        ]

        # A table needs at least 4 cells (e.g., 2x2)
        if len(text_elements) < 4:
            return []

        # 1. Sort all elements by vertical position
        text_elements.sort(key=lambda x: x.position.y)

        rows = []
        current_row = []
        current_y_baseline = None

        # Tolerance for elements to be considered on the same "row"
        # 100000 EMU is roughly 0.1 inches, adjusting for slight PDF alignment quirks
        Y_TOLERANCE = 150000.0  

        for element in text_elements:
            if not current_row:
                current_row.append(element)
                current_y_baseline = element.position.y
            else:
                # If the element is within the vertical tolerance of the current row baseline
                if abs(element.position.y - current_y_baseline) <= Y_TOLERANCE:
                    current_row.append(element)
                else:
                    # New row detected
                    if len(current_row) > 1: # Only save rows with multiple columns
                        rows.append(current_row)
                    current_row = [element]
                    current_y_baseline = element.position.y

        # Catch the last row
        if len(current_row) > 1:
            rows.append(current_row)

        if len(rows) < 2:
            return []

        # 2. Group contiguous rows into distinct tables
        tables = []
        current_table_rows = []

        # Tolerance for vertical gap between rows in the same table
        # 400000 EMU is roughly 0.4 inches
        MAX_ROW_GAP = 500000.0  

        for i, row in enumerate(rows):
            if not current_table_rows:
                current_table_rows.append(row)
            else:
                prev_row_bottom = max([e.position.y + e.position.height for e in current_table_rows[-1]])
                current_row_top = min([e.position.y for e in row])

                if (current_row_top - prev_row_bottom) <= MAX_ROW_GAP:
                    current_table_rows.append(row)
                else:
                    if len(current_table_rows) >= 2:
                        tables.append(current_table_rows)
                    current_table_rows = [row]

        if len(current_table_rows) >= 2:
            tables.append(current_table_rows)

        # 3. Format output
        detected_tables = []
        for table_idx, table_rows in enumerate(tables):
            # Sort cells in each row horizontally
            formatted_rows = []
            min_x = float('inf')
            min_y = float('inf')
            max_x = float('-inf')
            max_y = float('-inf')

            for row in table_rows:
                row.sort(key=lambda x: x.position.x)
                formatted_rows.append([cell.text.strip() for cell in row])
                for cell in row:
                    min_x = min(min_x, cell.position.x)
                    min_y = min(min_y, cell.position.y)
                    max_x = max(max_x, cell.position.x + cell.position.width)
                    max_y = max(max_y, cell.position.y + cell.position.height)

            detected_tables.append({
                "table_type": "visual_grid",
                "rows": formatted_rows,
                "bbox": {
                    "x": min_x,
                    "y": min_y,
                    "width": max_x - min_x,
                    "height": max_y - min_y
                }
            })

        return detected_tables