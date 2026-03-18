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

    def __init__(self) -> None:
        self._last_cache_key: tuple[object, ...] | None = None
        self._last_results: list[RelocalizationCandidate] = []

    def reset(self) -> None:
        self._last_cache_key = None
        self._last_results = []

    def score_candidates(self, graph: CellGraph, current_cell: CellNode, recent_transitions: list[str]) -> list[RelocalizationCandidate]:
        cache_key = (
            len(graph.edges),
            current_cell.cell_id,
            current_cell.cell_type,
            tuple(sorted(current_cell.observed_doors)),
            tuple(current_cell.landmark_tokens),
            current_cell.step_span,
            tuple(recent_transitions[-5:]),
        )
        if cache_key == self._last_cache_key:
            return self._last_results

        candidates: list[RelocalizationCandidate] = []
        current_signature = tuple(recent_transitions[-5:])
        current_landmarks = set(current_cell.landmark_tokens)
        for cell in graph.cells.values():
            if cell.cell_id == current_cell.cell_id:
                continue
            scene_match = 1.0 if cell.cell_type == current_cell.cell_type else 0.0
            door_match = 1.0 if bool(cell.observed_doors & current_cell.observed_doors) else 0.0
            candidate_signature = tuple(graph.transition_signature(cell.cell_id, 5))
            if not current_signature:
                turn_match = 0.0
            elif candidate_signature == current_signature:
                turn_match = 1.0
            else:
                overlap = sum(1 for a, b in zip(candidate_signature[-len(current_signature):], current_signature) if a == b)
                turn_match = overlap / max(len(current_signature), 1)
            step_match = max(0.0, 1.0 - abs(cell.step_span - current_cell.step_span) / max(current_cell.step_span, 1))
            landmark_match = 1.0 if bool(set(cell.landmark_tokens) & current_landmarks) else 0.0
            score = 0.30 * scene_match + 0.20 * door_match + 0.25 * turn_match + 0.15 * step_match + 0.10 * landmark_match
            if score > 0.2:
                candidates.append(RelocalizationCandidate(cell_id=cell.cell_id, score=round(score, 3)))
        self._last_cache_key = cache_key
        self._last_results = sorted(candidates, key=lambda item: item.score, reverse=True)[:5]
        return self._last_results
