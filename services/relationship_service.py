"""
Detects spatial relationships between document elements on a slide.

Supports:
    - Proximity-based grouping (elements close together)
    - Containment (one element inside another)
    - Connector-based linking (arrows/connectors joining shapes)
"""

from typing import List

from models.document_model import DocumentElementModel, RelationshipModel


_PROXIMITY_THRESHOLD = 500_000


class RelationshipService:

    def detect(
        self, elements: List[DocumentElementModel]
    ) -> List[RelationshipModel]:
        """
        Analyse all elements on a slide and return a list of
        detected relationships.
        """
        relationships: List[RelationshipModel] = []

        connectors = [
            e for e in elements if e.element_type in {"arrow", "connector"}
        ]
        boxes = [
            e for e in elements
            if e.element_type not in {"arrow", "connector"}
        ]

        for connector in connectors:
            linked = self._find_connector_targets(connector, boxes)
            if linked:
                relationships.append(linked)

        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if self._is_contained(a, b):
                    relationships.append(
                        RelationshipModel(
                            relationship_type="contains",
                            source_element_id=b.element_id,
                            target_element_id=a.element_id,
                        )
                    )
                elif self._is_contained(b, a):
                    relationships.append(
                        RelationshipModel(
                            relationship_type="contains",
                            source_element_id=a.element_id,
                            target_element_id=b.element_id,
                        )
                    )
                elif self._is_proximate(a, b):
                    relationships.append(
                        RelationshipModel(
                            relationship_type="proximity",
                            source_element_id=a.element_id,
                            target_element_id=b.element_id,
                            confidence=0.7,
                        )
                    )

        return relationships

    @staticmethod
    def _center(element: DocumentElementModel):
        cx = element.position.x + element.position.width / 2
        cy = element.position.y + element.position.height / 2
        return cx, cy

    def _find_connector_targets(
        self,
        connector: DocumentElementModel,
        boxes: List[DocumentElementModel],
    ) -> RelationshipModel | None:
        endpoints = connector.metadata.get("connector_endpoints", {})
        if not endpoints:
            return None

        begin = (endpoints.get("begin_x"), endpoints.get("begin_y"))
        end = (endpoints.get("end_x"), endpoints.get("end_y"))

        if begin[0] is None or end[0] is None:
            return None

        source = self._closest_box(begin, boxes)
        target = self._closest_box(end, boxes)

        if source and target and source.element_id != target.element_id:
            return RelationshipModel(
                relationship_type="connector",
                source_element_id=source.element_id,
                target_element_id=target.element_id,
                label=connector.text,
            )
        return None

    def _closest_box(self, point, boxes):
        best = None
        best_dist = float("inf")
        for box in boxes:
            cx, cy = self._center(box)
            dist = ((point[0] - cx) ** 2 + (point[1] - cy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = box
        return best

    @staticmethod
    def _is_contained(inner: DocumentElementModel, outer: DocumentElementModel) -> bool:
        return (
            inner.position.x >= outer.position.x
            and inner.position.y >= outer.position.y
            and (inner.position.x + inner.position.width)
            <= (outer.position.x + outer.position.width)
            and (inner.position.y + inner.position.height)
            <= (outer.position.y + outer.position.height)
        )

    @staticmethod
    def _is_proximate(a: DocumentElementModel, b: DocumentElementModel) -> bool:
        a_cx = a.position.x + a.position.width / 2
        a_cy = a.position.y + a.position.height / 2
        b_cx = b.position.x + b.position.width / 2
        b_cy = b.position.y + b.position.height / 2
        dist = ((a_cx - b_cx) ** 2 + (a_cy - b_cy) ** 2) ** 0.5
        return dist < _PROXIMITY_THRESHOLD