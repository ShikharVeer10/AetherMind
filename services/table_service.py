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
