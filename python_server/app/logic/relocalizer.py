"""Sequence-based qualitative relocalization against previously observed cells."""

from __future__ import annotations

from dataclasses import dataclass

from app.state.cell_graph import CellGraph, CellNode


@dataclass(slots=True)
class RelocalizationCandidate:
    cell_id: int
    score: float


class Relocalizer:
    """Matches recent qualitative context against historical cells."""

    def score_candidates(self, graph: CellGraph, current_cell: CellNode, recent_transitions: list[str]) -> list[RelocalizationCandidate]:
        candidates: list[RelocalizationCandidate] = []
        for cell in graph.cells.values():
            if cell.cell_id == current_cell.cell_id:
                continue
            scene_match = 1.0 if cell.cell_type == current_cell.cell_type else 0.0
            door_match = 1.0 if bool(cell.observed_doors & current_cell.observed_doors) else 0.0
            turn_match = 1.0 if graph.transition_signature(cell.cell_id, 5) == recent_transitions[-5:] else 0.0
            step_match = max(0.0, 1.0 - abs(cell.step_span - current_cell.step_span) / max(current_cell.step_span, 1))
            landmark_match = 1.0 if bool(set(cell.landmark_tokens) & set(current_cell.landmark_tokens)) else 0.0
            score = 0.30 * scene_match + 0.25 * door_match + 0.20 * turn_match + 0.15 * step_match + 0.10 * landmark_match
            if score > 0.2:
                candidates.append(RelocalizationCandidate(cell_id=cell.cell_id, score=round(score, 3)))
        return sorted(candidates, key=lambda item: item.score, reverse=True)[:5]
