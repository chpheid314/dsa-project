from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import tcod.event
from tcod.console import Console  # tcod.Console 지원 중단 대응
from tcod.event import KeySym  # 최신 키 상수 열거형

from actions import Action, BumpAction, EscapeAction, WaitAction

if TYPE_CHECKING:
    from engine import Engine

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

    def handle_events(self, context: tcod.context.Context) -> None:
        for event in tcod.event.wait():
            event = context.convert_event(event)
            self.dispatch(event)

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        tile_x, tile_y = event.integer_position
        if self.engine.game_map.in_bounds(tile_x, tile_y):
            self.engine.mouse_location = tile_x, tile_y

    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        raise SystemExit()
    
    def on_render(self, console: Console) -> None:
        self.engine.render(console)


class MainGameEventHandler(EventHandler):
    def handle_events(self, context: tcod.context.Context) -> None:
        for event in tcod.event.wait():
            event = context.convert_event(event)
            action = self.dispatch(event)

            if action is None:
                continue

            action.perform()
            self.engine.handle_enemy_turns()
            self.engine.update_fov()

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
            action = EscapeAction(player)
        elif key == KeySym.V:
            self.engine.event_handler = HistoryViewer(self.engine)

        return action
    

class GameOverEventHandler(EventHandler):
    def handle_events(self, context: tcod.context.Context) -> None:
        for event in tcod.event.wait():
            event = context.convert_event(event)
            action = self.dispatch(event)

            if action is None:
                continue

            action.perform()

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:
        action: Optional[Action] = None
        key = event.sym

        if key == KeySym.ESCAPE:
            action = EscapeAction(self.engine.player)

        return action


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