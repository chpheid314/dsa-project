from __future__ import annotations

from collections import deque
import copy
from typing import TYPE_CHECKING

from tcod.console import Console
from tcod.map import compute_fov

import time
from leaderboard import ScoreEntry, calculate_score, add_score, load_leaderboard
import procgen
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

        self.current_floor = 1
        self.max_floors = 3

        self.undo_history = deque(maxlen=30)
        self.redo_history = deque(maxlen=30)

        self.user_id = ""

        self.start_time = 0.0
        self.elapsed_before_pause = 0.0
        self.timer_running = False

        self.monsters_killed = 0
        self.cleared_floors = 0
        self.final_score_entry = None
        self.leaderboard = load_leaderboard()
        self.game_finished = False
        self.score_saved = False
        self.restart_requested = False

        self.camera_width = 26
        self.camera_height = 12

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

    def advance_level(self) -> None:
        self.current_floor += 1

        if self.current_floor > self.max_floors:
            self.message_log.add_message("You escaped the dungeon!")
            raise SystemExit()

        self.message_log.add_message(f"You descend to level {self.current_floor}.")

        if self.current_floor == 2:
            max_monsters_per_room = 3
            max_items_per_room = 2

        elif self.current_floor == 3:
            max_monsters_per_room = 3
            max_items_per_room = 2

        else:
            max_monsters_per_room = 2
            max_items_per_room = 1

        self.game_map = procgen.generate_dungeon(
            room_min_size=6,
            room_max_size=12,
            map_width=80,
            map_height=43,
            max_monsters_per_room=max_monsters_per_room,
            max_items_per_room=max_items_per_room,
            engine=self,
            floor_number=self.current_floor,
        )

        # Reset player HP when entering a new level.
        self.player.fighter.hp = self.player.fighter.max_hp

        self.update_fov()

        self.undo_history.clear()
        self.redo_history.clear()

    def get_camera_origin(self) -> tuple[int, int]:
        camera_x = self.player.x - self.camera_width // 2
        camera_y = self.player.y - self.camera_height // 2

        camera_x = max(0, camera_x)
        camera_y = max(0, camera_y)

        camera_x = min(
            camera_x,
            self.game_map.width - self.camera_width,
        )

        camera_y = min(
            camera_y,
            self.game_map.height - self.camera_height,
        )

        return camera_x, camera_y
            
    def render(self, console: Console) -> None:
        self.game_map.render(console)

        ui_y = self.camera_height

        self.message_log.render(
            console=console,
            x=0,
            y=ui_y + 4,
            width=26,
            height=1,
        )
        console.print(
            x=0,
            y=ui_y,
            text=f"Lv:{self.current_floor}"
        )

        timer_text = f"Time: {self.get_elapsed_time_string()}"
        console.print(
            x=console.width - len(timer_text) - 1,
            y=ui_y,
            text=timer_text,
            fg=(255, 255, 255),
        )

        # HP bar
        render_bar(
            console=console,
            current_value=self.player.fighter.hp,
            maximum_value=self.player.fighter.max_hp,
            total_width=20,
            x = 0,
            y = ui_y + 1,
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
            y = ui_y + 2,
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
            y = ui_y + 3,
            text = f"Redo: {len(self.redo_history)}/{self.redo_history.maxlen}",
            filled_color=(100, 180, 255), # blue!
            empty_color=color.bar_empty
        )

        render_names_at_mouse_location(
            console=console,
            x=10,
            y=ui_y,
            engine=self,
        )


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

        self.current_floor = snapshot.current_floor
        self.monsters_killed = snapshot.monsters_killed
        self.cleared_floors = snapshot.cleared_floors
        self.game_finished = snapshot.game_finished
        self.score_saved = snapshot.score_saved
        self.final_score_entry = snapshot.final_score_entry

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

    def start_timer(self) -> None:
        self.start_time = time.time()
        self.elapsed_before_pause = 0.0
        self.timer_running = True


    def pause_timer(self) -> None:
        if self.timer_running:
            self.elapsed_before_pause += time.time() - self.start_time
            self.timer_running = False


    def resume_timer(self) -> None:
        if not self.timer_running and not self.game_finished:
            self.start_time = time.time()
            self.timer_running = True


    def get_elapsed_seconds(self) -> int:
        if self.start_time == 0:
            return 0

        if self.timer_running:
            elapsed = self.elapsed_before_pause + (time.time() - self.start_time)
        else:
            elapsed = self.elapsed_before_pause

        return int(elapsed)


    def get_elapsed_minutes(self) -> int:
        return self.get_elapsed_seconds() // 60


    def get_elapsed_time_string(self) -> str:
        elapsed_seconds = self.get_elapsed_seconds()
        minutes = elapsed_seconds // 60
        seconds = elapsed_seconds % 60
        return f"{minutes:02}:{seconds:02}"


    def get_remaining_healing_items(self) -> int:
        count = 0

        if not hasattr(self.player, "inventory"):
            return 0

        for item in self.player.inventory.items:
            if getattr(item, "consumable", None) is not None:
                count += 1

        return count


    def finish_game(self) -> None:
        if self.score_saved:
            return
        
        self.pause_timer()

        elapsed_minutes = self.get_elapsed_minutes()
        remaining_items = self.get_remaining_healing_items()
        remaining_hp = max(0, self.player.fighter.hp)

        score, overtime_minutes = calculate_score(
            cleared_floors=self.cleared_floors,
            monsters_killed=self.monsters_killed,
            remaining_items=remaining_items,
            remaining_hp=remaining_hp,
            elapsed_minutes=elapsed_minutes,
        )

        entry = ScoreEntry(
            user_id=self.user_id,
            score=score,
            cleared_floors=self.cleared_floors,
            monsters_killed=self.monsters_killed,
            remaining_items=remaining_items,
            remaining_hp=remaining_hp,
            elapsed_minutes=elapsed_minutes,
            overtime_minutes=overtime_minutes,
        )

        self.final_score_entry = entry
        self.leaderboard = add_score(entry)
        self.game_finished = True
        self.score_saved = True