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

        self.engine.handle_turns_after_player()
        self.engine.update_fov()
        return True

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        screen_x, screen_y = event.integer_position

        camera_x, camera_y = self.engine.get_camera_origin()

        world_x = screen_x + camera_x
        world_y = screen_y + camera_y

        if self.engine.game_map.in_bounds(world_x, world_y):
            self.engine.mouse_location = (world_x, world_y)

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

        width = min(
            console.width - 2,
            max(len(self.TITLE) + 4, 20)
        )

        x = (console.width - width) // 2

        y = 0

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

        title = "Enter Player ID"
        id_text = f"ID: {self.current_text}_"
        help_text = "Press ENTER"

        title_x = (console.width - len(title)) // 2
        id_x = (console.width - len(id_text)) // 2
        help_x = (console.width - len(help_text)) // 2

        center_y = console.height // 2

        console.print(
            x=title_x,
            y=center_y - 2,
            text=title,
            fg=(255, 255, 255),
        )

        console.print(
            x=id_x,
            y=center_y,
            text=id_text,
            fg=(255, 255, 0),
        )

        console.print(
            x=help_x,
            y=center_y + 2,
            text=help_text,
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
    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.top_index = 0
        self.show_formula = False

    def on_render(self, console: Console) -> None:
        console.clear()

        console.print(
            x=1,
            y=0,
            text="=== LEADERBOARD ===",
            fg=(255, 255, 0),
        )

        if self.show_formula:
            console.print(
                x=1,
                y=3,
                text="Score Formula",
                fg=(255, 255, 0),
            )

            console.print(
                x=2,
                y=4,
                text="=Cleared Floors*1000",
                fg=(180, 180, 180),
            )

            console.print(
                x=3,
                y=5,
                text="+Monsters Killed*50",
                fg=(180, 180, 180),
            )

            console.print(
                x=3,
                y=6,
                text="+Remaining HP Items*70",
                fg=(180, 180, 180),
            )

            console.print(
                x=3,
                y=7,
                text="+Remaining HP*10",
                fg=(180, 180, 180),
            )

            console.print(
                x=3,
                y=8,
                text = "-Overtime Minutes*300",
                fg=(180, 180, 180),
            )
        else:
            entries = self.engine.leaderboard.to_sorted_list()

            y = 2

            visible_entries = entries[
                self.top_index : self.top_index + 3
            ]

            for rank, entry in enumerate(
                visible_entries,
                start=self.top_index + 1,
            ):
                console.print(
                    x=0,
                    y=y,
                    text=f"{rank}. {entry.user_id}",
                    fg=(255,255,255),
                )

                y += 1

                console.print(
                    x=2,
                    y=y,
                    text=f"Score:{entry.score}",
                    fg=(180,180,180),
                )

                y += 2

                if self.top_index > 0:
                    console.print(
                        x=22,
                        y=1,
                        text="^",
                        fg=(255,255,255),
                    )

                if self.top_index + 3 < len(entries):
                    console.print(
                        x=22,
                        y=9,
                        text="v",
                        fg=(255,255,255),
                    )

        if self.engine.final_score_entry:
            entry = self.engine.final_score_entry

            y = 11

            console.print(
                x=0,
                y=y,
                text="Your Result",
                fg=(255,255,0),
            )

            y += 1

            console.print(
                x=0,
                y=y,
                text=f"{entry.user_id}",
                fg=(255,255,255),
            )

            y += 1

            console.print(
                x=0,
                y=y,
                text=f"Score:{entry.score}",
                fg=(255,255,255),
            )

        if self.engine.game_finished:
            console.print(
                x=0,
                y=16,
                text="P:Replay C:Clear F:Formula",
                fg=(255,255,255),
            )
        else:
            console.print(
                x=0,
                y=16,
                text="R:Resume C:Clear F:Formula",
                fg=(255,255,255),
            )

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:        
        key = event.sym

        entries = self.engine.leaderboard.to_sorted_list()

        if key == KeySym.UP and not self.show_formula:
            self.top_index = max(0, self.top_index - 1)
            return None

        elif key == KeySym.DOWN and not self.show_formula:
            max_index = max(0, len(entries) - 3)

            self.top_index = min(
                max_index,
                self.top_index + 1,
            )
            return None
        elif key == KeySym.E:
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
        
        elif key == KeySym.F:
            self.show_formula = not self.show_formula

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

        log_console = Console(console.width - 2, console.height - 2)

        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print(
            x=0,
            y=0,
            text="Message history Log",
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
        log_console.blit(console, 1, 1)

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