from typing import Optional
import tcod.event
from actions import Action, EscapeAction, MovementAction
from tcod.event import KeySym

class EventHandler(tcod.event.EventDispatch[Action]):
    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        raise SystemExit()

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[Action]:
        action: Optional[Action] = None
        key = event.sym

        if key == KeySym.UP:
            action = MovementAction(dx=0, dy=-1)
        elif key == KeySym.DOWN:
            action = MovementAction(dx=0, dy=1)
        elif key == KeySym.LEFT:
            action = MovementAction(dx=-1, dy=0)
        elif key == KeySym.RIGHT:
            action = MovementAction(dx=1, dy=0)

        elif key == KeySym.ESCAPE:
            action = EscapeAction()

        return action