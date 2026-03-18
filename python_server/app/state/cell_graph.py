"""Qualitative cell graph data structures and update helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class CellNode:
    cell_id: int
    cell_type: str
    entry_heading_deg: float
    entry_side: str | None
    corridor_axis_heading_deg: float | None
    observed_doors: set[str] = field(default_factory=set)
    landmark_tokens: list[str] = field(default_factory=list)
    text_tokens: list[str] = field(default_factory=list)
    step_span: int = 0
    distance_span_m: float = 0.0
    confidence: float = 0.0
    start_frame: int = 0
    end_frame: int = 0


@dataclass(slots=True)
class Edge:
    from_cell: int
    to_cell: int
    transition_type: str
    exit_side: str | None
    turn_angle_deg: float
    step_count: int
    distance_m: float
    total_step_count: int
    total_distance_m: float
    confidence: float


class CellGraph:
    """Stores qualitative cells and traversed transitions for route memory."""

    def __init__(self) -> None:
        self.cells: dict[int, CellNode] = {}
        self.edges: list[Edge] = []
        self._next_cell_id = 0
        self.current_cell_id = self.add_cell(
            cell_type="corridor_segment",
            entry_heading_deg=0.0,
            entry_side=None,
            corridor_axis_heading_deg=None,
            step_span=0,
            distance_span_m=0.0,
            confidence=1.0,
            frame_id=0,
        )

    def add_cell(
        self,
        cell_type: str,
        entry_heading_deg: float,
        entry_side: str | None,
        corridor_axis_heading_deg: float | None,
        step_span: int,
        distance_span_m: float,
        confidence: float,
        frame_id: int,
        landmark_tokens: list[str] | None = None,
        text_tokens: list[str] | None = None,
    ) -> int:
        cell_id = self._next_cell_id
        self._next_cell_id += 1
        self.cells[cell_id] = CellNode(
            cell_id=cell_id,
            cell_type=cell_type,
            entry_heading_deg=entry_heading_deg,
            entry_side=entry_side,
            corridor_axis_heading_deg=corridor_axis_heading_deg,
            step_span=step_span,
            distance_span_m=distance_span_m,
            confidence=confidence,
            start_frame=frame_id,
            end_frame=frame_id,
            landmark_tokens=landmark_tokens or [],
            text_tokens=text_tokens or [],
        )
        return cell_id

    def update_current_cell(
        self,
        frame_id: int,
        step_span: int,
        distance_span_m: float,
        confidence: float,
        corridor_axis_heading_deg: float | None,
        landmark_tokens: list[str],
        text_tokens: list[str],
        door_side: str | None = None,
    ) -> CellNode:
        cell = self.cells[self.current_cell_id]
        cell.end_frame = frame_id
        cell.step_span = step_span
        cell.distance_span_m = distance_span_m
        cell.confidence = confidence
        cell.corridor_axis_heading_deg = corridor_axis_heading_deg
        cell.landmark_tokens = sorted(set(cell.landmark_tokens + landmark_tokens))
        cell.text_tokens = sorted(set(cell.text_tokens + text_tokens))
        if door_side:
            cell.observed_doors.add(door_side)
        return cell

    def create_boundary(
        self,
        transition_type: str,
        cell_type: str,
        heading_deg: float,
        exit_side: str | None,
        turn_angle_deg: float,
        step_count: int,
        distance_m: float,
        total_step_count: int,
        total_distance_m: float,
        confidence: float,
        frame_id: int,
        corridor_axis_heading_deg: float | None,
        landmark_tokens: list[str],
        text_tokens: list[str],
    ) -> int:
        """Commits a boundary using per-cell spans while keeping total counters for export/debug."""

        previous_cell = self.current_cell_id
        previous = self.cells[previous_cell]
        previous.end_frame = frame_id
        previous.step_span = step_count
        previous.distance_span_m = distance_m
        next_cell = self.add_cell(
            cell_type=cell_type,
            entry_heading_deg=heading_deg,
            entry_side=exit_side,
            corridor_axis_heading_deg=corridor_axis_heading_deg,
            step_span=0,
            distance_span_m=0.0,
            confidence=confidence,
            frame_id=frame_id,
            landmark_tokens=landmark_tokens,
            text_tokens=text_tokens,
        )
        self.edges.append(
            Edge(
                from_cell=previous_cell,
                to_cell=next_cell,
                transition_type=transition_type,
                exit_side=exit_side,
                turn_angle_deg=turn_angle_deg,
                step_count=step_count,
                distance_m=distance_m,
                total_step_count=total_step_count,
                total_distance_m=total_distance_m,
                confidence=confidence,
            )
        )
        self.current_cell_id = next_cell
        return next_cell

    def transition_signature(self, cell_id: int, limit: int) -> list[str]:
        """Returns the ordered transition history that led to the given cell."""

        signature: list[str] = []
        for edge in self.edges:
            signature.append(edge.transition_type)
            if edge.to_cell == cell_id:
                break
        return signature[-limit:]

    def reverse_edges(self) -> list[Edge]:
        return list(reversed(self.edges))

    def reverse_edge_at(self, cursor: int) -> Edge | None:
        reversed_edges = self.reverse_edges()
        if cursor < 0 or cursor >= len(reversed_edges):
            return None
        return reversed_edges[cursor]

    def summary(self) -> dict[str, int]:
        return {"num_cells": len(self.cells), "num_edges": len(self.edges)}

    def export(self) -> dict[str, object]:
        return {
            "cells": [
                {
                    **asdict(cell),
                    "observed_doors": sorted(cell.observed_doors),
                }
                for cell in self.cells.values()
            ],
            "edges": [asdict(edge) for edge in self.edges],
            "summary": self.summary(),
        }
