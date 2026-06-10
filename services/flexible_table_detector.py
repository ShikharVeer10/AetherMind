from collections import defaultdict
from typing import List, Dict, Any


class FlexibleTableDetector:

    def detect_visual_tables(self, elements: List[Any]) -> List[Dict[str, Any]]:
        text_elements = [
            e for e in elements
            if e.element_type == "text_box" and e.text and e.text.strip()
        ]

        # A table needs at least some content
        if len(text_elements) < 3:
            return []

        # 1. Sort all elements by vertical position
        text_elements.sort(key=lambda x: x.position.y)

        rows = []
        current_row = []
        
        # Tolerance for elements to be considered on the same "row"
        # 150000 EMU is roughly 0.15 inches
        Y_TOLERANCE = 150000.0  

        for element in text_elements:
            if not current_row:
                current_row.append(element)
            else:
                # Use center-y for more robust row grouping than just top-y
                curr_center_y = element.position.y + element.position.height / 2
                prev_element = current_row[-1]
                prev_center_y = prev_element.position.y + prev_element.position.height / 2
                
                if abs(curr_center_y - prev_center_y) <= Y_TOLERANCE:
                    current_row.append(element)
                else:
                    rows.append(current_row)
                    current_row = [element]

        if current_row:
            rows.append(current_row)

        if len(rows) < 2:
            return []

        # 2. Group contiguous rows into distinct tables
        tables = []
        current_table_rows = []

        # Tolerance for vertical gap between rows in the same table
        MAX_ROW_GAP = 600000.0  

        for i, row in enumerate(rows):
            if not current_table_rows:
                current_table_rows.append(row)
            else:
                prev_row_bottom = max([e.position.y + e.position.height for e in current_table_rows[-1]])
                current_row_top = min([e.position.y for e in row])

                if (current_row_top - prev_row_bottom) <= MAX_ROW_GAP:
                    current_table_rows.append(row)
                else:
                    if self._is_likely_table(current_table_rows):
                        tables.append(current_table_rows)
                    current_table_rows = [row]

        if self._is_likely_table(current_table_rows):
            tables.append(current_table_rows)

        # 3. Format output using Grid Reconstruction
        detected_tables = []
        for table_idx, table_rows in enumerate(tables):
            all_elements = [e for row in table_rows for e in row]
            
            # Reconstruct the grid from these elements
            grid_info = self._reconstruct_grid(all_elements)
            
            if not grid_info:
                continue

            min_x = min(e.position.x for e in all_elements)
            min_y = min(e.position.y for e in all_elements)
            max_x = max(e.position.x + e.position.width for e in all_elements)
            max_y = max(e.position.y + e.position.height for e in all_elements)

            detected_tables.append({
                "table_type": "visual_grid",
                "rows": grid_info["rows"],
                "merged_cells": grid_info["merged_cells"],
                "num_rows": grid_info["num_rows"],
                "num_cols": grid_info["num_cols"],
                "bbox": {
                    "x": min_x,
                    "y": min_y,
                    "width": max_x - min_x,
                    "height": max_y - min_y
                }
            })

        return detected_tables

    def _is_likely_table(self, table_rows: List[List[Any]]) -> bool:
        """Heuristic to check if a group of rows is likely a table."""
        if len(table_rows) < 2:
            return False
        
        has_multi_col = any(len(row) > 1 for row in table_rows)
        if not has_multi_col:
            return False
            
        total_cells = sum(len(row) for row in table_rows)
        return total_cells >= 4

    def _reconstruct_grid(self, elements: List[Any]) -> Dict[str, Any]:
        """Reconstructs a 2D grid from a collection of spatially positioned elements."""
        if not elements:
            return {}

        # 0. Merge very close spans (PDF encoding artifacts)
        merged_elements = self._merge_adjacent_spans(elements)

        # 1. Extract all horizontal and vertical boundaries
        x_coords = []
        y_coords = []
        for e in merged_elements:
            x_coords.append(e.position.x)
            x_coords.append(e.position.x + e.position.width)
            y_coords.append(e.position.y)
            y_coords.append(e.position.y + e.position.height)

        # 2. Cluster boundaries to find grid lines
        GRID_TOLERANCE = 120000.0 
        
        grid_x = self._cluster_coordinates(x_coords, GRID_TOLERANCE)
        grid_y = self._cluster_coordinates(y_coords, GRID_TOLERANCE)
        
        # 2.5 Refine grid lines based on alignment density
        grid_x = self._refine_grid_lines(grid_x, [e.position.x for e in merged_elements] + [e.position.x + e.position.width for e in merged_elements])
        grid_y = self._refine_grid_lines(grid_y, [e.position.y for e in merged_elements] + [e.position.y + e.position.height for e in merged_elements])

        num_cols = len(grid_x) - 1
        num_rows = len(grid_y) - 1
        
        if num_cols <= 0 or num_rows <= 0:
            return {}

        # 3. Initialize grid and map elements
        grid = [[None for _ in range(num_cols)] for _ in range(num_rows)]
        grid_styles = [[None for _ in range(num_cols)] for _ in range(num_rows)]
        merged_cells = []
        consumed_ids = []

        for e in merged_elements:
            col_start = min(range(len(grid_x)), key=lambda i: abs(grid_x[i] - e.position.x))
            col_end = min(range(len(grid_x)), key=lambda i: abs(grid_x[i] - (e.position.x + e.position.width)))
            row_start = min(range(len(grid_y)), key=lambda i: abs(grid_y[i] - e.position.y))
            row_end = min(range(len(grid_y)), key=lambda i: abs(grid_y[i] - (e.position.y + e.position.height)))

            # Clip indices to valid grid range
            col_start = min(col_start, num_cols - 1)
            row_start = min(row_start, num_rows - 1)
            
            if col_end <= col_start: col_end = col_start + 1
            if row_end <= row_start: row_end = row_start + 1
            
            col_end = min(col_end, num_cols)
            row_end = min(row_end, num_rows)

            text = e.text.strip()
            if hasattr(e, "original_ids"):
                consumed_ids.extend(e.original_ids)
            else:
                consumed_ids.append(e.element_id)
            
            if grid[row_start][col_start] is None:
                grid[row_start][col_start] = text
                if hasattr(e, "style") and e.style:
                    grid_styles[row_start][col_start] = e.style
            else:
                grid[row_start][col_start] += " " + text
            
            row_span = row_end - row_start
            col_span = col_end - col_start
            
            if row_span > 1 or col_span > 1:
                merged_cells.append({
                    "row": row_start, "col": col_start,
                    "row_span": row_span, "col_span": col_span, "text": text
                })
                for r in range(row_start, row_end):
                    for c in range(col_start, col_end):
                        if r == row_start and c == col_start: continue
                        if grid[r][c] is None: grid[r][c] = ""

        final_rows = []
        final_styles = []
        for r in range(num_rows):
            row_data = []
            row_styles = []
            for c in range(num_cols):
                val = grid[r][c]
                style = grid_styles[r][c]
                row_data.append(val if val is not None else "")
                row_styles.append(style)
            final_rows.append(row_data)
            final_styles.append(row_styles)

        return {
            "rows": final_rows,
            "styles": final_styles,
            "merged_cells": merged_cells,
            "num_rows": num_rows,
            "num_cols": num_cols,
            "consumed_ids": consumed_ids
        }

    def _merge_adjacent_spans(self, elements: List[Any]) -> List[Any]:
        """PDF artifact cleanup: merges spans that are visually part of the same word/number."""
        if not elements: return []
        sorted_elements = sorted(elements, key=lambda e: (e.position.y, e.position.x))
        merged = []
        if not sorted_elements: return []
        
        curr = sorted_elements[0]
        # Copy to avoid mutating input objects
        from copy import deepcopy
        curr = curr.model_copy(deep=True)
        curr.original_ids = [curr.element_id]
        
        # Micro-tolerance (30000 EMU is ~0.03 inches)
        X_TOL = 40000.0
        Y_TOL = 20000.0
        
        for i in range(1, len(sorted_elements)):
            nxt = sorted_elements[i]
            # If horizontally adjacent and vertically aligned
            if (abs(nxt.position.y - curr.position.y) < Y_TOL and 
                (nxt.position.x - (curr.position.x + curr.position.width)) < X_TOL):
                # Merge
                curr.text += nxt.text
                new_width = (nxt.position.x + nxt.position.width) - curr.position.x
                curr.position.width = new_width
                curr.original_ids.append(nxt.element_id)
            else:
                merged.append(curr)
                curr = nxt.model_copy(deep=True)
                curr.original_ids = [curr.element_id]
        merged.append(curr)
        return merged

    def _refine_grid_lines(self, clusters: List[float], all_coords: List[float]) -> List[float]:
        """Eliminates shaky grid lines by snapping to high-density alignment points."""
        if not clusters: return []
        refined = []
        for c in clusters:
            # Find all coordinates that contributed to this cluster
            near = [coord for coord in all_coords if abs(coord - c) < 150000.0]
            if near:
                # Snap to the most frequent coordinate (or average of dense group)
                refined.append(sum(near) / len(near))
            else:
                refined.append(c)
        return sorted(list(set(refined)))

    def _cluster_coordinates(self, coords: List[float], tolerance: float) -> List[float]:
        if not coords:
            return []
        
        # Unique sorted values
        vals = sorted(list(set(coords)))
        if not vals:
            return []
            
        clusters = []
        if vals:
            current_cluster = [vals[0]]
            for i in range(1, len(vals)):
                if vals[i] - vals[i-1] <= tolerance:
                    current_cluster.append(vals[i])
                else:
                    clusters.append(sum(current_cluster) / len(current_cluster))
                    current_cluster = [vals[i]]
            clusters.append(sum(current_cluster) / len(current_cluster))
            
        return sorted(clusters)