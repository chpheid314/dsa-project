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
    room: RectangularRoom,
    dungeon: GameMap,
    maximum_monsters: int,
    maximum_items: int,
    floor_number: int,
) -> None:
    if floor_number == 1:
        # Level 1: original difficulty.
        number_of_monsters = random.randint(0, maximum_monsters)
        number_of_items = random.randint(0, maximum_items)

    elif floor_number == 2:
        # Level 2: monsters are optional, but trolls are more common.
        number_of_monsters = random.randint(0, maximum_monsters)

        # Level 2: more potions than Level 1.
        number_of_items = random.randint(1, maximum_items + 1)

    else:
        # Level 3: at least one monster per room, max 3.
        number_of_monsters = random.randint(1, 3)

        # Level 3: still gives potions.
        number_of_items = random.randint(1, maximum_items + 1)

    for i in range(number_of_monsters):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            if floor_number == 1:
                # Level 1: 80% slime, 20% cactus.
                if random.random() < 0.8:
                    entity_factories.slime.spawn(dungeon, x, y)
                else:
                    entity_factories.cactus.spawn(dungeon, x, y)

            elif floor_number == 2:
                # Level 2: 60% slime, 40% cactus.
                if random.random() < 0.6:
                    entity_factories.slime.spawn(dungeon, x, y)
                else:
                    entity_factories.cactus.spawn(dungeon, x, y)

            else:
                # Level 3: 40% slime, 40% cactus, 20% ghost.
                monster_roll = random.random()

                if monster_roll < 0.4:
                    entity_factories.slime.spawn(dungeon, x, y)
                elif monster_roll < 0.8:
                    entity_factories.cactus.spawn(dungeon, x, y)
                else:
                    entity_factories.ghost.spawn(dungeon, x, y)

    for i in range(number_of_items):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            if floor_number == 1:
                # Level 1: only normal health potions.
                entity_factories.hp_potion.spawn(dungeon, x, y)

            elif floor_number == 2:
                # Level 2: 50% normal potion, 50% strong potion.
                if random.random() < 0.5:
                    entity_factories.hp_potion.spawn(dungeon, x, y)
                else:
                    entity_factories.strong_hp_potion.spawn(dungeon, x, y)

            else:
                # Level 3: strong potion is more frequent.
                # 30% normal potion, 70% strong potion.
                if random.random() < 0.3:
                    entity_factories.hp_potion.spawn(dungeon, x, y)
                else:
                    entity_factories.strong_hp_potion.spawn(dungeon, x, y)


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


def tunnel_to_edge(
    start: Tuple[int, int],
    map_width: int,
    map_height: int,
) -> Iterator[Tuple[int, int]]:
    """Create a straight tunnel from a point to the nearest map edge."""
    x, y = start

    distances = {
        "left": x,
        "right": map_width - 1 - x,
        "top": y,
        "bottom": map_height - 1 - y,
    }

    nearest_edge = min(distances, key=distances.get)

    if nearest_edge == "left":
        for tunnel_x in range(x, -1, -1):
            yield tunnel_x, y

    elif nearest_edge == "right":
        for tunnel_x in range(x, map_width):
            yield tunnel_x, y

    elif nearest_edge == "top":
        for tunnel_y in range(y, -1, -1):
            yield x, tunnel_y

    elif nearest_edge == "bottom":
        for tunnel_y in range(y, map_height):
            yield x, tunnel_y

    
def generate_dungeon(
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    max_monsters_per_room: int,
    max_items_per_room: int,
    engine: Engine,
    floor_number: int = 1,
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

        place_entities(
            room,
            dungeon,
            max_monsters_per_room,
            max_items_per_room,
            floor_number,
        )

        rooms.append(room)

    if rooms:
        exit_path = list(
            tunnel_to_edge(
                rooms[-1].center,
                map_width,
                map_height,
            )
        )

        for x, y in exit_path:
            dungeon.tiles[x, y] = tile_types.floor

        dungeon.downstairs_location = exit_path[-1]
        dungeon.tiles[dungeon.downstairs_location] = tile_types.down_stairs

    return dungeon