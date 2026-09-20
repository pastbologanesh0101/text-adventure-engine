#!/usr/bin/env python3
"""
play.py -- interactive CLI runner for the Text Adventure Engine.

Usage:
    python play.py [world.json]

If no world file is given, defaults to "world.json" in the current
directory (the bundled adventure).
"""

import sys

from engine import GameEngine, load_world


def main(argv):
    world_path = argv[1] if len(argv) > 1 else "world.json"
    try:
        world = load_world(world_path)
    except (OSError, ValueError) as exc:
        print(f"Could not load world file '{world_path}': {exc}")
        return 1

    engine = GameEngine(world)
    title = world.get("title", "Text Adventure")
    print("=" * len(title))
    print(title)
    print("=" * len(title))
    print()
    print(engine._describe_room(engine.state["room"]))
    print()
    print("Type commands like: look, go north, take key, use key on east, "
          "examine statue, inventory, quit")
    print()

    while True:
        try:
            raw = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            print("Goodbye.")
            return 0

        if raw.strip().lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            return 0

        command = engine.parse_command(raw)
        result = engine.execute(command)
        print(result["message"])

        state = engine.get_state()
        if state["won"]:
            print()
            print("*** THE END ***")
            return 0
        if state["lost"]:
            print()
            print("*** GAME OVER ***")
            return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
