"""Generates Korean instructions for live and reverse traversal guidance."""

from __future__ import annotations


def instruction_for_transition(transition_type: str | None, exit_side: str | None = None) -> str:
    if transition_type == "turn_left":
        return "왼쪽으로 도세요"
    if transition_type == "turn_right":
        return "오른쪽으로 도세요"
    if transition_type == "door_pass":
        if exit_side == "left":
            return "왼쪽 벽의 문으로 나가세요"
        if exit_side == "right":
            return "오른쪽 벽의 문으로 나가세요"
        return "앞 문으로 나가세요"
    if transition_type == "straight_continue":
        return "복도를 따라 직진하세요"
    if transition_type == "branch_enter":
        if exit_side == "left":
            return "왼쪽 갈림길로 진입하세요"
        if exit_side == "right":
            return "오른쪽 갈림길로 진입하세요"
        return "갈림길로 진입하세요"
    if transition_type == "ambiguity_warning":
        return "주변을 천천히 확인하세요"
    return "계속 진행하세요"
