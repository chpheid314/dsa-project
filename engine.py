from __future__ import annotations

from collections import deque
import copy
from typing import TYPE_CHECKING

from tcod.console import Console
from tcod.map import compute_fov

import exceptions
import color
from input_handlers import MainGameEventHandler
from message_log import MessageLog
from render_functions import render_bar, render_names_at_mouse_location

if TYPE_CHECKING:
    from entity import Actor
    from game_map import GameMap
    from input_handlers import EventHandler

class Engine:
    game_map: GameMap

    def __init__(self, player: Actor):
        self.event_handler: EventHandler = MainGameEventHandler(self)
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.player = player

        self.undo_history = deque(maxlen=30)
        self.redo_history = deque(maxlen=30)

    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.

    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=8,
        )
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible
            
    def render(self, console: Console) -> None:
        self.game_map.render(console)

        self.message_log.render(console=console, x=21, y=45, width=40, height=5)

        # HP bar
        render_bar(
            console=console,
            current_value=self.player.fighter.hp,
            maximum_value=self.player.fighter.max_hp,
            total_width=20,
            x = 0,
            y = 45,
            text = f"HP: {self.player.fighter.hp}/{self.player.fighter.max_hp}",
            filled_color=(255, 0, 0), # red!
            empty_color=color.bar_empty
        )

        # Undo bar
        render_bar(
            console=console,
            current_value=len(self.undo_history),
            maximum_value=self.undo_history.maxlen,
            total_width=20,
            x = 0,
            y = 47,
            text = f"Undo: {len(self.undo_history)}/{self.undo_history.maxlen}",
            filled_color=(135, 106, 250), # purple!
            empty_color=color.bar_empty
        )

        # Redo bar
        render_bar(
            console=console,
            current_value=len(self.redo_history),
            maximum_value=self.redo_history.maxlen,
            total_width=20,
            x = 0,
            y = 49,
            text = f"Redo: {len(self.redo_history)}/{self.redo_history.maxlen}",
            filled_color=(100, 180, 255), # blue!
            empty_color=color.bar_empty
        )

        render_names_at_mouse_location(console=console, x=21, y=44, engine=self)


    def __getstate__(self):
        state = self.__dict__.copy()

        state["event_handler"] = None

        state["undo_history"] = deque(maxlen=30)
        state["redo_history"] = deque(maxlen=30)

        return state

    def save_undo_state(self) -> None:
        self.undo_history.append(copy.deepcopy(self))
        self.redo_history.clear()

    def restore_state(self, snapshot: "Engine") -> None:
        self.message_log = copy.deepcopy(snapshot.message_log)
        self.mouse_location = snapshot.mouse_location
        self.player = copy.deepcopy(snapshot.player)
        self.game_map = copy.deepcopy(snapshot.game_map)

        self.game_map.engine = self

        for entity in self.game_map.entities:
            entity.parent = self.game_map

        for entity in self.game_map.entities:
            if entity.name == self.player.name and entity.char == self.player.char:
                self.player = entity
                break

        self.event_handler = MainGameEventHandler(self)

        self.update_fov()

    def undo(self) -> None:
        if not self.undo_history:
            self.message_log.add_message("Nothing to undo.")
            return

        self.redo_history.append(copy.deepcopy(self))
        snapshot = self.undo_history.pop()
        self.restore_state(snapshot)

    def redo(self) -> None:
        if not self.redo_history:
            self.message_log.add_message("Nothing to redo.")
            return

        self.undo_history.append(copy.deepcopy(self))
        snapshot = self.redo_history.pop()
        self.restore_state(snapshot)