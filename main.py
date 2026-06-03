import copy
import traceback

import tcod

import color
from engine import Engine
import entity_factories
from procgen import generate_dungeon
from input_handlers import IDInputEventHandler


def new_game() -> Engine:
    map_width = 80
    map_height = 43

    room_max_size = 12
    room_min_size = 6

    max_monsters_per_room = 2
    max_items_per_room = 2

    player = copy.deepcopy(entity_factories.player)

    engine = Engine(player=player)

    engine.game_map = generate_dungeon(
        room_min_size=room_min_size,
        room_max_size=room_max_size,
        map_width=map_width,
        map_height=map_height,
        max_monsters_per_room=max_monsters_per_room,
        max_items_per_room=max_items_per_room,
        engine=engine,
        floor_number=1,
    )

    engine.update_fov()

    engine.message_log.add_message(
        "Hello and welcome, adventurer, to yet another dungeon!",
        color.welcome_text,
    )

    engine.event_handler = IDInputEventHandler(engine)

    return engine


def main() -> None:
    screen_width = 26
    screen_height = 17

    tileset = tcod.tileset.load_tilesheet(
        "dejavu64x64_gs_tc_modification.png",
        32,
        8,
        tcod.tileset.CHARMAP_TCOD,
    )

    engine = new_game()

    with tcod.context.new(
        columns=screen_width,
        rows=screen_height,
        tileset=tileset,
        title="DSA Project",
        vsync=True,
    ) as context:
        root_console = tcod.console.Console(screen_width, screen_height, order="F")

        while True:
            if engine.restart_requested:
                engine = new_game()

            root_console.clear()
            engine.event_handler.on_render(console=root_console)
            context.present(root_console)

            try:
                for event in tcod.event.wait(timeout=0.05):
                    event = context.convert_event(event)
                    engine.event_handler.handle_events(event)

                    if engine.restart_requested:
                        break

            except Exception:
                traceback.print_exc()
                engine.message_log.add_message(traceback.format_exc(), color.error)


if __name__ == "__main__":
    main()