from __future__ import annotations

from typing import Iterable, Iterator, Optional, TYPE_CHECKING

import numpy as np  # type: ignore
from tcod.console import Console

from entity import Actor, Item
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

class GameMap:
    def __init__(
        self, engine: Engine, width: int, height: int, entities: Iterable[Entity] = ()
    ):
        self.engine = engine
        self.width, self.height = width, height
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")
        self.entities = set(entities)
        self.downstairs_location = (0, 0)

        self.visible = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player can currently see
        self.explored = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player has seen before

    @property
    def gamemap(self) -> GameMap:
        return self

    @property
    def actors(self) -> Iterator[Actor]:
        """Iterate over this maps living actors."""
        yield from (
            entity
            for entity in self.entities
            if isinstance(entity, Actor) and entity.is_alive
        )

    @property
    def items(self) -> Iterator[Item]:
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    def get_blocking_entity_at_location(
        self, location_x: int, location_y: int,
    ) -> Optional[Entity]:
        for entity in self.entities:
            if (
                entity.blocks_movement
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity

        return None
    
    def get_actor_at_location(self, x: int, y: int) -> Optional[Actor]:
        for actor in self.actors:
            if actor.x == x and actor.y == y:
                return actor

        return None

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y <self.height
    
    def render(self, console: Console) -> None:
        """
        Renders the map.

        If a tile is in the "visible" array, then draw it with the "light" colors.
        If it isn't, but it's in the "explored" array, then draw it with the "dark" colors.
        Otherwise, the default is "SHROUD".
        """

        camera_x, camera_y = self.engine.get_camera_origin()

        camera_width = self.engine.camera_width
        camera_height = self.engine.camera_height

        visible_slice = self.visible[
            camera_x : camera_x + camera_width,
            camera_y : camera_y + camera_height,
        ]

        explored_slice = self.explored[
            camera_x : camera_x + camera_width,
            camera_y : camera_y + camera_height,
        ]

        tiles_light_slice = self.tiles["light"][
            camera_x : camera_x + camera_width,
            camera_y : camera_y + camera_height,
        ]

        tiles_dark_slice = self.tiles["dark"][
            camera_x : camera_x + camera_width,
            camera_y : camera_y + camera_height,
        ]

        console.rgb[
            0:camera_width,
            0:camera_height
        ] = np.select(
            condlist=[visible_slice, explored_slice],
            choicelist=[tiles_light_slice, tiles_dark_slice],
            default=tile_types.SHROUD,
        )

        entities_sorted_for_rendering = sorted(
            self.entities, key=lambda x: x.render_order.value
        )

        for entity in entities_sorted_for_rendering:
            if not self.visible[entity.x, entity.y]:
                continue

            screen_x = entity.x - camera_x
            screen_y = entity.y - camera_y

            if (
                0 <= screen_x < camera_width
                and
                0 <= screen_y < camera_height
            ):
                console.print(
                    x=screen_x,
                    y=screen_y,
                    text=entity.char,
                    fg=entity.color,
                )