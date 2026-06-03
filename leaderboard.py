from __future__ import annotations

import json
import os
from dataclasses import dataclass


LEADERBOARD_FILE = "leaderboard.json"


@dataclass
class ScoreEntry:
    user_id: str
    score: int
    cleared_floors: int
    monsters_killed: int
    remaining_items: int
    remaining_hp: int
    elapsed_minutes: int
    overtime_minutes: int


class BSTNode:
    def __init__(self, entry: ScoreEntry):
        self.entry = entry
        self.left: BSTNode | None = None
        self.right: BSTNode | None = None


class LeaderboardBST:
    def __init__(self):
        self.root: BSTNode | None = None

    def insert(self, entry: ScoreEntry) -> None:
        self.root = self._insert(self.root, entry)

    def _insert(self, node: BSTNode | None, entry: ScoreEntry) -> BSTNode:
        if node is None:
            return BSTNode(entry)

        # Higher score should appear first.
        # So larger score goes to the LEFT side.
        if entry.score > node.entry.score:
            node.left = self._insert(node.left, entry)
        else:
            node.right = self._insert(node.right, entry)

        return node

    def to_sorted_list(self) -> list[ScoreEntry]:
        result: list[ScoreEntry] = []
        self._reverse_inorder(self.root, result)
        return result

    def _reverse_inorder(self, node: BSTNode | None, result: list[ScoreEntry]) -> None:
        if node is None:
            return

        self._reverse_inorder(node.left, result)
        result.append(node.entry)
        self._reverse_inorder(node.right, result)


def calculate_score(
    cleared_floors: int,
    monsters_killed: int,
    remaining_items: int,
    remaining_hp: int,
    elapsed_minutes: int,
) -> tuple[int, int]:
    overtime_minutes = max(0, elapsed_minutes - 7)

    score = (
        cleared_floors * 1000
        + monsters_killed * 50
        + remaining_items * 70
        + remaining_hp * 10
        - overtime_minutes * 300
    )

    return score, overtime_minutes


def load_leaderboard() -> LeaderboardBST:
    bst = LeaderboardBST()

    if not os.path.exists(LEADERBOARD_FILE):
        return bst

    with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        entry = ScoreEntry(**item)
        bst.insert(entry)

    return bst


def save_leaderboard(bst: LeaderboardBST) -> None:
    data = [entry.__dict__ for entry in bst.to_sorted_list()]

    with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def add_score(entry: ScoreEntry) -> LeaderboardBST:
    bst = load_leaderboard()
    bst.insert(entry)
    save_leaderboard(bst)
    return bst

def clear_leaderboard() -> LeaderboardBST:
    """Delete all saved leaderboard scores and return an empty leaderboard."""
    if os.path.exists(LEADERBOARD_FILE):
        os.remove(LEADERBOARD_FILE)

    return LeaderboardBST()