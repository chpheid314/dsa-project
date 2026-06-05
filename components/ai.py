from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

from actions import Action, MeleeAction, MovementAction, WaitAction

if TYPE_CHECKING:
    from entity import Actor

class BaseAI(Action):

    def perform(self) -> None:
        raise NotImplementedError()
    
    def get_path_to(self, dest_x: int, dest_y: int) -> List[Tuple[int, int]]:
        """Compute and return a path to the target position using A*.

        If there is no valid path then returns an empty list.
        """

        import heapq

        start = (self.entity.x, self.entity.y)
        goal = (dest_x, dest_y)

        gamemap = self.entity.gamemap

        def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> int:
            """Manhattan distance heuristic for 4-direction movement."""
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        def movement_cost(x: int, y: int) -> int:
            """Return movement cost for a tile.

            Walls are not handled here because neighbors are checked before calling this.
            Blocking entities get extra cost so enemies avoid crowding.
            """
            cost = 1

            for entity in gamemap.entities:
                if entity.blocks_movement and entity.x == x and entity.y == y:
                    cost += 10

            return cost

        open_set = []
        heapq.heappush(open_set, (0, start))

        came_from: dict[Tuple[int, int], Tuple[int, int]] = {}

        g_score: dict[Tuple[int, int], int] = {
            start: 0
        }

        # 4-direction movement: up, down, left, right.
        directions = [
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
        ]

        while open_set:
            current_f, current = heapq.heappop(open_set)

            if current == goal:
                path = []

                while current != start:
                    path.append(current)
                    current = came_from[current]

                path.reverse()
                return path

            current_x, current_y = current

            for dx, dy in directions:
                neighbor_x = current_x + dx
                neighbor_y = current_y + dy
                neighbor = (neighbor_x, neighbor_y)

                if not gamemap.in_bounds(neighbor_x, neighbor_y):
                    continue

                if not gamemap.tiles["walkable"][neighbor_x, neighbor_y]:
                    continue

                tentative_g_score = g_score[current] + movement_cost(neighbor_x, neighbor_y)

                if tentative_g_score < g_score.get(neighbor, 999999):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score

                    f_score = tentative_g_score + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, neighbor))

        return []
    
class HostileEnemy(BaseAI):
    def __init__(self, entity: Actor):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []

    def perform(self) -> None:
        target = self.engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = abs(dx) + abs(dy)

        if self.engine.game_map.visible[self.entity.x, self.entity.y]:
            if distance <= 1:
                return MeleeAction(self.entity, dx, dy).perform()

            self.path = self.get_path_to(target.x, target.y)

        if self.path:
            dest_x, dest_y = self.path.pop(0)
            return MovementAction(
                self.entity, dest_x - self.entity.x, dest_y - self.entity.y,
            ).perform()

        return WaitAction(self.entity).perform()