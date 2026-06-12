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
                "rows": grid_info["rows_data"],
                "styles": grid_info["cell_styles"],
                "merged_cells": grid_info["merged_cells"],
                "num_rows": grid_info["num_rows"],
                "num_cols": grid_info["num_cols"],
                "consumed_ids": grid_info["consumed_ids"],
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
        """
        Lossless grid reconstruction using strict geometric intersections.
        Guarantees that every input element is accounted for and mapped to a unique grid space.
        """
        if not elements:
            return {}

        # 0. Cleanup: Merge very close spans (PDF encoding artifacts)
        # This is a safe pre-process to avoid fragmentation of single logical words
        merged_elements = self._merge_adjacent_spans(elements)

        # 1. Discover definitive Column and Row boundaries (Grid Lines)
        # We look for clusters of X (start/end) and Y (start/end) to find the "bones"
        x_points = []
        y_points = []
        for e in merged_elements:
            x_points.extend([e.position.x, e.position.x + e.position.width])
            y_points.extend([e.position.y, e.position.y + e.position.height])

        # Cluster points into unique grid lines with a tight tolerance
        # 80000 EMU is ~0.08 inch
        grid_x = self._cluster_coordinates(x_points, 80000.0)
        grid_y = self._cluster_coordinates(y_points, 80000.0)

        num_cols = len(grid_x) - 1
        num_rows = len(grid_y) - 1
        
        if num_cols <= 0 or num_rows <= 0:
            return {}

        # 2. Map elements to the Grid
        # Every element MUST belong to at least one cell.
        # If it spans boundaries, it dictates a merged region.
        
        # grid[row][col] -> list of elements in that cell
        logical_grid = [[[] for _ in range(num_cols)] for _ in range(num_rows)]
        
        for e in merged_elements:
            # Find the best fitting row/col indices based on center-point intersection
            # to avoid ambiguity at the exact boundaries.
            cx = e.position.x + e.position.width / 2
            cy = e.position.y + e.position.height / 2
            
            col_idx = -1
            for i in range(num_cols):
                if grid_x[i] <= cx <= grid_x[i+1]:
                    col_idx = i
                    break
            
            row_idx = -1
            for i in range(num_rows):
                if grid_y[i] <= cy <= grid_y[i+1]:
                    row_idx = i
                    break
            
            # Fallback to nearest if somehow outside (geometric floating point edge cases)
            if col_idx == -1:
                col_idx = min(range(num_cols), key=lambda i: abs(cx - (grid_x[i] + grid_x[i+1])/2))
            if row_idx == -1:
                row_idx = min(range(num_rows), key=lambda i: abs(cy - (grid_y[i] + grid_y[i+1])/2))

            # Determine span based on bounding box covering grid lines
            # If an element's edge significantly crosses a grid line, it's a span
            SPAN_THRESHOLD = 50000.0 # ~0.05 inch
            
            start_col = col_idx
            end_col = col_idx
            # Check for column span
            for i in range(num_cols + 1):
                if grid_x[i] > e.position.x + SPAN_THRESHOLD and grid_x[i] < (e.position.x + e.position.width) - SPAN_THRESHOLD:
                    # Spans this boundary
                    pass # We will use the start_col/row logic to fill merged_cells later
            
            # For lossless extraction, we first place it in its primary logical cell
            logical_grid[row_idx][col_idx].append(e)

        # 3. Structural Normalization and Merge Detection
        # Identify "Visually Merged" regions (spans)
        # In this lossless model, we detect spans by looking at which grid-defined cells 
        # are actually part of the same physical shape or text flow.
        
        merged_cells = []
        rows_data = []
        cell_styles = []
        
        for r in range(num_rows):
            row_vals = []
            row_styles = []
            for c in range(num_cols):
                cell_elements = logical_grid[r][c]
                # Sort elements within a cell by their visual position (reading order within cell)
                cell_elements.sort(key=lambda x: (x.position.y, x.position.x))
                
                text = "\n".join([elem.text.strip() for elem in cell_elements if elem.text])
                row_vals.append(text)
                
                # Capture visual metadata from the primary element in the cell
                style = None
                if cell_elements:
                    style = cell_elements[0].style
                row_styles.append(style)
            
            rows_data.append(row_vals)
            cell_styles.append(row_styles)

        # 4. Refine Spans (Heuristic based on empty neighbors and global alignment)
        # To maintain "Identical Structure", we look for logical neighbors that are empty 
        # but likely part of a span based on the element's actual width/height.
        for e in merged_elements:
            # Re-verify spans based on actual geometry vs grid lines
            r_start = -1; r_end = -1; c_start = -1; c_end = -1
            
            for i in range(num_rows):
                if grid_y[i] <= e.position.y + SPAN_THRESHOLD: r_start = i
                if grid_y[i+1] >= (e.position.y + e.position.height) - SPAN_THRESHOLD:
                    r_end = i
                    if r_start != -1: break
            
            for i in range(num_cols):
                if grid_x[i] <= e.position.x + SPAN_THRESHOLD: c_start = i
                if grid_x[i+1] >= (e.position.x + e.position.width) - SPAN_THRESHOLD:
                    c_end = i
                    if c_start != -1: break
            
            if r_start != -1 and r_end != -1 and c_start != -1 and c_end != -1:
                row_span = (r_end - r_start) + 1
                col_span = (c_end - c_start) + 1
                if row_span > 1 or col_span > 1:
                    merged_cells.append({
                        "row": r_start,
                        "column": c_start,
                        "row_span": row_span,
                        "column_span": col_span
                    })

        # 5. Validation and Deduplication
        # - Verify no text lost or duplicated
        all_mapped_elements = [el for r in range(num_rows) for c in range(num_cols) for el in logical_grid[r][c]]
        if len(all_mapped_elements) != len(merged_elements):
             print(f"[FlexibleTableDetector] WARNING: Lossless mapping mismatch. Mapped {len(all_mapped_elements)} vs Input {len(merged_elements)}")

        # - Deduplicate merged regions and ensure no overlaps
        unique_merged = []
        covered_cells = set()
        for mc in merged_cells:
            # Check if start cell already covered
            if (mc["row"], mc["column"]) in covered_cells:
                continue
            
            # Add to unique and mark all cells in span as covered
            unique_merged.append(mc)
            for r in range(mc["row"], mc["row"] + mc["row_span"]):
                for c in range(mc["column"], mc["column"] + mc["column_span"]):
                    covered_cells.add((r, c))

        return {
            "rows": list(range(num_rows)),
            "columns": list(range(num_cols)),
            "rows_data": rows_data,
            "cell_styles": cell_styles,
            "merged_cells": unique_merged,
            "num_rows": num_rows,
            "num_cols": num_cols,
            "consumed_ids": [eid for e in merged_elements for eid in (getattr(e, "original_ids", [e.element_id]))]
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