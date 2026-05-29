from __future__ import annotations

import random
from typing import Iterator, List, Tuple, TYPE_CHECKING

import tcod
from tcod.bsp import BSP

import entity_factories
from game_map import GameMap
import tile_types

if TYPE_CHECKING:
    from engine import Engine

class RectangularRoom:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)

        return center_x, center_y
    
    @property
    def inner(self) -> Tuple[slice, slice]:
        """Return the inner area of this room as a 2D array index."""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)
    
    def intersects(self, other: RectangularRoom) -> bool:
        """Return True if this room overlaps with another RectangularRoom."""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )
    

def create_room_from_leaf(
    leaf: BSP,
    room_min_size: int,
    room_max_size: int,
) -> RectangularRoom | None:

    if leaf.width < room_min_size + 2 or leaf.height < room_min_size + 2:
        return None

    room_width = random.randint(
        room_min_size,
        min(room_max_size, leaf.width - 1)
    )

    room_height = random.randint(
        room_min_size,
        min(room_max_size, leaf.height - 1)
    )

    x = random.randint(
        leaf.x,
        leaf.x + leaf.width - room_width
    )

    y = random.randint(
        leaf.y,
        leaf.y + leaf.height - room_height
    )

    return RectangularRoom(
        x,
        y,
        room_width,
        room_height,
    )

    
def place_entities(
    room: RectangularRoom, dungeon: GameMap, maximum_monsters: int, maximum_items: int
) -> None:
    number_of_monsters = random.randint(0, maximum_monsters)
    number_of_items = random.randint(0, maximum_items)

    for i in range(number_of_monsters):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            if random.random() < 0.8:
                entity_factories.orc.spawn(dungeon, x, y)
            else:
                entity_factories.troll.spawn(dungeon, x, y)

    for i in range(number_of_items):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            entity_factories.health_potion.spawn(dungeon, x, y)

def tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int]
) -> Iterator[Tuple[int, int]]:
    """Return an L-shaped tunnel between these two points."""
    x1, y1 = start
    x2, y2 = end
    if random.random() < 0.5:  # 50% chance.
        # Move horizontally, then vertically.
        corner_x, corner_y = x2, y1
    else:
        # Move vertically, then horizontally.
        corner_x, corner_y = x1, y2

    # Generate the coordinates for this tunnel.
    for x, y in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
        yield x, y
    for x, y in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
        yield x, y


def generate_dungeon(
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    max_monsters_per_room: int,
    max_items_per_room: int,
    engine: Engine,
) -> GameMap:

    player = engine.player

    dungeon = GameMap(
        engine,
        map_width,
        map_height,
        entities=[player]
    )

    rooms = []

    bsp = BSP(
        x=0,
        y=0,
        width=map_width,
        height=map_height
    )

    bsp.split_recursive(
        depth=5,
        min_width=room_max_size + 2,
        min_height=room_max_size + 2,
        max_horizontal_ratio=1.5,
        max_vertical_ratio=1.5,
    )

    leaves = [node for node in bsp.pre_order() if not node.children]

    for leaf in leaves:

        room = create_room_from_leaf(
            leaf,
            room_min_size,
            room_max_size,
        )

        if room is None:
            continue

        dungeon.tiles[room.inner] = tile_types.floor

        if not rooms:
            player.place(*room.center, dungeon)

        else:
            previous_room = rooms[-1]

            for x, y in tunnel_between(
                previous_room.center,
                room.center,
            ):
                dungeon.tiles[x, y] = tile_types.floor

        place_entities(room, dungeon, max_monsters_per_room, max_items_per_room)

        rooms.append(room)

    return dungeon