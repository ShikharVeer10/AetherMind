from collections import defaultdict


class FlexibleTableDetector:

    def detect_visual_tables(self, elements):

        text_elements = [
            e
            for e in elements
            if e.element_type == "text_box"
            and e.text
        ]

        if len(text_elements) < 4:
            return []

        rows = defaultdict(list)

        for element in text_elements:

            y_bucket = round(
                element.position.y / 150000
            )

            rows[y_bucket].append(element)

        candidate_rows = []

        for row in rows.values():

            row = sorted(
                row,
                key=lambda x: x.position.x
            )

            if len(row) >= 2:

                candidate_rows.append(
                    [
                        cell.text.strip()
                        for cell in row
                    ]
                )

        if len(candidate_rows) < 2:
            return []

        return [
            {
                "table_type": "visual_grid",
                "rows": candidate_rows
            }
        ]