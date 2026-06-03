from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import tcod.event
from tcod.console import Console  # tcod.Console 지원 중단 대응
from tcod.event import KeySym  # 최신 키 상수 열거형

import actions
from actions import (
    Action,
    BumpAction,
    PickupAction,
    WaitAction
)
import color
import exceptions
from leaderboard import clear_leaderboard

if TYPE_CHECKING:
    from engine import Engine
    from entity import Item

# 구형 tcod.event.K_... 구조를 최신 KeySym 구조로 변경
MOVE_KEYS = {
    # Arrow keys.
    KeySym.UP: (0, -1),
    KeySym.DOWN: (0, 1),
    KeySym.LEFT: (-1, 0),
    KeySym.RIGHT: (1, 0),
}

WAIT_KEYS = {
    KeySym.PERIOD,
    KeySym.KP_5,
    KeySym.CLEAR,
}

# HistoryViewer에서 사용할 스크롤 키 매핑도 KeySym으로 수정
CURSOR_Y_KEYS = {
    KeySym.UP: -1,
    KeySym.DOWN: 1,
    KeySym.PAGEUP: -10,
    KeySym.PAGEDOWN: 10,
}


class EventHandler(tcod.event.EventDispatch[Action]):
    def __init__(self, engine: Engine):
        self.engine = engine

    def handle_events(self, event: tcod.event.Event) -> None:
        action = self.dispatch(event)
        self.handle_action(action)

    def handle_action(self, action: Optional[Action]) -> bool:
        """Handle actions returned from event methods.

        Returns True if the action will advance a turn.
        """
        if action is None:
            return False

        self.engine.save_undo_state()

        try:
            turn_taken = action.perform()
        except exceptions.Impossible as exc:
            self.engine.undo_history.pop()
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return False

        if not turn_taken:
            self.engine.undo_history.pop()
            return False

        self.engine.handle_enemy_turns()
        self.engine.update_fov()
        return True

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        tile_x, tile_y = event.integer_position
        if self.engine.game_map.in_bounds(tile_x, tile_y):
            self.engine.mouse_location = tile_x, tile_y

    def ev_pixelsizechanged(self, event: tcod.event.PixelSizeChanged) -> None:
        pass

    def ev_clipboardupdate(self, event: tcod.event.ClipboardUpdate) -> None:
        pass

    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        raise SystemExit()
    
    def on_render(self, console: Console) -> None:
        self.engine.render(console)

class AskUserEventHandler(EventHandler):
    """Handles user input for actions which require special input."""

    def handle_action(self, action: Optional[Action]) -> bool:
        """Return to the main event handler when a valid action was performed."""
        if super().handle_action(action):
            self.engine.event_handler = MainGameEventHandler(self.engine)
            return True
        return False

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:
        """By default any key exits this input handler."""
        if event.sym in {  # Ignore modifier keys.
            KeySym.LSHIFT,
            KeySym.RSHIFT,
            KeySym.LCTRL,
            KeySym.RCTRL,
            KeySym.LALT,
            KeySym.RALT,
        }:
            return None
        return self.on_exit()

    def ev_mousebuttondown(self, event: tcod.event.MouseButtonDown) -> Optional[Action]:
        """By default any mouse click exits this input handler."""
        return self.on_exit()

    def on_exit(self) -> Optional[Action]:
        """Called when the user is trying to exit or cancel an action.

        By default this returns to the main event handler.
        """
        self.engine.event_handler = MainGameEventHandler(self.engine)
        return None

class InventoryEventHandler(AskUserEventHandler):
    """This handler lets the user select an item.

    What happens then depends on the subclass.
    """

    TITLE = "<missing title>"

    def on_render(self, console: tcod.Console) -> None:
        """Render an inventory menu, which displays the items in the inventory, and the letter to select them.
        Will move to a different position based on where the player is located, so the player can always see where
        they are.
        """
        super().on_render(console)
        number_of_items_in_inventory = len(self.engine.player.inventory.items)

        height = number_of_items_in_inventory + 2

        if height <= 3:
            height = 3

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        width = len(self.TITLE) + 4

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=height,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        if number_of_items_in_inventory > 0:
            for i, item in enumerate(self.engine.player.inventory.items):
                item_key = chr(ord("a") + i)
                console.print(x + 1, y + i + 1, f"({item_key}) {item.name}")
        else:
            console.print(x + 1, y + 1, "(Empty)")

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:
        player = self.engine.player
        key = event.sym
        index = key - KeySym.A

        if 0 <= index <= 26:
            try:
                selected_item = player.inventory.items[index]
            except IndexError:
                self.engine.message_log.add_message("Invalid entry.", color.invalid)
                return None
            return self.on_item_selected(selected_item)
        return super().ev_keydown(event)

    def on_item_selected(self, item: Item) -> Optional[Action]:
        """Called when the user selects a valid item."""
        raise NotImplementedError()
    
class InventoryActivateHandler(InventoryEventHandler):
    """Handle using an inventory item."""

    TITLE = "Select an item to use"

    def on_item_selected(self, item: Item) -> Optional[Action]:
        """Return the action for the selected item."""
        return item.consumable.get_action(self.engine.player)

class InventoryDropHandler(InventoryEventHandler):
    """Handle dropping an inventory item."""

    TITLE = "Select an item to drop"

    def on_item_selected(self, item: Item) -> Optional[Action]:
        """Drop this item."""
        return actions.DropItem(self.engine.player, item)

class IDInputEventHandler(EventHandler):
    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.current_text = ""

    def on_render(self, console: Console) -> None:
        console.clear()

        console.print(
            x=25,
            y=15,
            string="Enter Player ID",
            fg=(255, 255, 255),
        )

        console.print(
            x=25,
            y=17,
            string=f"ID: {self.current_text}",
            fg=(255, 255, 0),
        )

        console.print(
            x=25,
            y=20,
            string="Type your ID, then press ENTER",
            fg=(180, 180, 180),
        )

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:
        key = event.sym

        if key == KeySym.RETURN:
            if self.current_text.strip():
                self.engine.user_id = self.current_text.strip()
                self.engine.start_timer()
                self.engine.event_handler = MainGameEventHandler(self.engine)
            return None

        elif key == KeySym.BACKSPACE:
            self.current_text = self.current_text[:-1]
            return None

        elif key == KeySym.ESCAPE:
            raise SystemExit()

        # Letters A-Z
        elif KeySym.A <= key <= KeySym.Z:
            letter = chr(ord("a") + (key - KeySym.A))

            if event.mod & tcod.event.Modifier.SHIFT:
                letter = letter.upper()

            if len(self.current_text) < 12:
                self.current_text += letter

            return None

        # Numbers 0-9
        elif ord("0") <= int(key) <= ord("9"):
            number = chr(int(key))

            if len(self.current_text) < 12:
                self.current_text += number

            return None

        # Space, underscore, hyphen
        elif key == KeySym.SPACE:
            if len(self.current_text) < 12:
                self.current_text += " "
            return None

        elif key == KeySym.MINUS:
            if len(self.current_text) < 12:
                self.current_text += "-"
            return None

        return None

class LeaderboardEventHandler(EventHandler):
    def on_render(self, console: Console) -> None:
        console.clear()
        console.print(
            x=2,
            y=1,
            string="LEADERBOARD",
            fg=(255, 255, 0),
        )
        console.print(
            x=2,
            y=3,
            string="Score Formula:",
            fg=(255, 255, 0),
        )
        console.print(
            x=4,
            y=4,
            string="Score = Cleared Floors * 1000",
            fg=(180, 180, 180),
        )
        console.print(
            x=12,
            y=5,
            string="+ Monsters Killed * 50",
            fg=(180, 180, 180),
        )
        console.print(
            x=12,
            y=6,
            string="+ Remaining Healing Items * 70",
            fg=(180, 180, 180),
        )
        console.print(
            x=12,
            y=7,
            string="+ Remaining HP * 10",
            fg=(180, 180, 180),
        )
        console.print(
            x=12,
            y=8,
            string="- Overtime Minutes * 300",
            fg=(180, 180, 180),
        )
        console.print(
            x=2,
            y=10,
            string="Rank  ID          Score   Floors  Kills  Items  HP  Time  Overtime",
            fg=(255, 255, 255),
        )

        entries = self.engine.leaderboard.to_sorted_list()

        y = 12

        for rank, entry in enumerate(entries[:10], start=1):
            console.print(
                x=2,
                y=y,
                string=(
                    f"{rank:<5} "
                    f"{entry.user_id:<11} "
                    f"{entry.score:<7} "
                    f"{entry.cleared_floors:<7} "
                    f"{entry.monsters_killed:<6} "
                    f"{entry.remaining_items:<6} "
                    f"{entry.remaining_hp:<3} "
                    f"{entry.elapsed_minutes:<5} "
                    f"{entry.overtime_minutes:<8}"
                ),
                fg=(220, 220, 220),
            )
            y += 1

        y += 2

        if self.engine.final_score_entry:
            entry = self.engine.final_score_entry

            console.print(x=2, y=y, string="Your Result", fg=(255, 255, 0))
            y += 2

            console.print(x=2, y=y, string=f"Player ID: {entry.user_id}", fg=(255, 255, 255))
            y += 1
            console.print(x=2, y=y, string=f"Final Score: {entry.score}", fg=(255, 255, 255))
            y += 2

            console.print(
                x=2,
                y=y,
                string=f"Cleared Floors: {entry.cleared_floors} x 1000 = {entry.cleared_floors * 1000}",
                fg=(200, 200, 200),
            )
            y += 1

            console.print(
                x=2,
                y=y,
                string=f"Monsters Killed: {entry.monsters_killed} x 50 = {entry.monsters_killed * 50}",
                fg=(200, 200, 200),
            )
            y += 1

            console.print(
                x=2,
                y=y,
                string=f"Remaining Healing Items: {entry.remaining_items} x 70 = {entry.remaining_items * 70}",
                fg=(200, 200, 200),
            )
            y += 1

            console.print(
                x=2,
                y=y,
                string=f"Remaining HP: {entry.remaining_hp} x 10 = {entry.remaining_hp * 10}",
                fg=(200, 200, 200),
            )
            y += 1

            console.print(
                x=2,
                y=y,
                string=f"Overtime Penalty: {entry.overtime_minutes} x 300 = -{entry.overtime_minutes * 300}",
                fg=(200, 200, 200),
            )

        if self.engine.game_finished:
            console.print(
                x=2,
                y=46,
                string="Press P to play again, C to clear scores, E to exit",
                fg=(255, 255, 255),
            )
        else:
            console.print(
                x=2,
                y=46,
                string="Press R to resume, C to clear scores, E to exit",
                fg=(255, 255, 255),
            )

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:
        key = event.sym

        if key == KeySym.E:
            raise SystemExit()

        elif key == KeySym.R:
            if not self.engine.game_finished:
                self.engine.resume_timer()
                self.engine.event_handler = MainGameEventHandler(self.engine)

        elif key == KeySym.P:
            if self.engine.game_finished:
                self.engine.restart_requested = True

        elif key == KeySym.C:
            self.engine.leaderboard = clear_leaderboard()
            self.engine.final_score_entry = None

        return None


class MainGameEventHandler(EventHandler):
    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:
        action: Optional[Action] = None
        key = event.sym
        player = self.engine.player

        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            action = BumpAction(player, dx, dy)
        elif key in WAIT_KEYS:
            action = WaitAction(player)
        elif key == KeySym.ESCAPE:
            raise SystemExit()
        elif key == KeySym.V:
            self.engine.event_handler = HistoryViewer(self.engine)
        elif key == KeySym.G:
            action = PickupAction(player)
        elif key == KeySym.I:
            self.engine.event_handler = InventoryActivateHandler(self.engine)
        elif key == KeySym.D:
            self.engine.event_handler = InventoryDropHandler(self.engine)
        elif key == KeySym.U:
            self.engine.undo()
            return None
        elif key == KeySym.R:
            self.engine.redo()
            return None
        elif key == KeySym.L:
            self.engine.pause_timer()
            self.engine.event_handler = LeaderboardEventHandler(self.engine)
            return None

        # No valid key was pressed
        return action
    

class GameOverEventHandler(EventHandler):
    def ev_keydown(self, event: tcod.event.KeyDown) -> None:
        if event.sym == tcod.event.KeySym.ESCAPE:
            raise SystemExit()

class HistoryViewer(EventHandler):
    """Print the history on a larger window which can be navigated."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, console: Console) -> None:
        super().on_render(console)

        log_console = Console(console.width - 6, console.height - 6)

        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print(
            x=0,
            y=0,
            text="┤Message history├",
            width=log_console.width,
            height=1,
            alignment=tcod.CENTER,
        )

        self.engine.message_log.render_messages(
            log_console,
            1,
            1,
            log_console.width - 2,
            log_console.height - 2,
            self.engine.message_log.messages[: self.cursor + 1],
        )
        log_console.blit(console, 3, 3)

    def ev_keydown(self, event: tcod.event.KeyDown) -> None:
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                self.cursor = 0
            else:
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == KeySym.HOME:
            self.cursor = 0
        elif event.sym == KeySym.END:
            self.cursor = self.log_length - 1
        else:
            self.engine.event_handler = MainGameEventHandler(self.engine)