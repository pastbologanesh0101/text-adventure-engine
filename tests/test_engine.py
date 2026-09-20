"""Unit tests for the Text Adventure Engine.

Run with:
    python -m pytest
or:
    python -m unittest discover
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import GameEngine, load_world  # noqa: E402

WORLD_PATH = os.path.join(os.path.dirname(__file__), "..", "world.json")


def make_engine():
    world = load_world(WORLD_PATH)
    return GameEngine(world)


class MovementTests(unittest.TestCase):
    def test_valid_exit_moves_player(self):
        engine = make_engine()
        result = engine.execute(engine.parse_command("go north"))
        self.assertTrue(result["success"])
        self.assertEqual(engine.get_state()["room"], "great_hall")

    def test_invalid_direction_does_not_move_player(self):
        engine = make_engine()
        result = engine.execute(engine.parse_command("go south"))
        self.assertFalse(result["success"])
        self.assertIn("can't go that way", result["message"].lower())
        self.assertEqual(engine.get_state()["room"], "entrance_hall")

    def test_locked_exit_is_blocked_with_clear_message(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))  # -> great_hall
        result = engine.execute(engine.parse_command("go east"))  # -> vault, locked
        self.assertFalse(result["success"])
        self.assertIn("locked", result["message"].lower())
        self.assertEqual(engine.get_state()["room"], "great_hall")

    def test_locked_exit_succeeds_after_correct_key_used(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))  # great_hall
        engine.execute(engine.parse_command("go north"))  # library
        engine.execute(engine.parse_command("take brass key"))
        engine.execute(engine.parse_command("go south"))  # back to great_hall
        engine.execute(engine.parse_command("use brass key on east"))
        result = engine.execute(engine.parse_command("go east"))
        self.assertTrue(result["success"])
        self.assertEqual(engine.get_state()["room"], "vault")

    def test_synonym_commands_produce_identical_results(self):
        engine_a = make_engine()
        engine_b = make_engine()
        result_a = engine_a.execute(engine_a.parse_command("n"))
        result_b = engine_b.execute(engine_b.parse_command("north"))
        self.assertEqual(result_a["success"], result_b["success"])
        self.assertEqual(result_a["message"], result_b["message"])
        self.assertEqual(engine_a.get_state()["room"], engine_b.get_state()["room"])


class ItemTests(unittest.TestCase):
    def test_take_item_adds_to_inventory_and_removes_from_room(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))
        engine.execute(engine.parse_command("go north"))  # library, has brass_key + lever
        result = engine.execute(engine.parse_command("take brass key"))
        self.assertTrue(result["success"])
        self.assertIn("brass_key", engine.get_state()["inventory"])
        self.assertNotIn("brass_key", engine.rooms["library"]["items"])

    def test_drop_item_removes_from_inventory_and_adds_to_room(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))
        engine.execute(engine.parse_command("go north"))
        engine.execute(engine.parse_command("take brass key"))
        result = engine.execute(engine.parse_command("drop brass key"))
        self.assertTrue(result["success"])
        self.assertNotIn("brass_key", engine.get_state()["inventory"])
        self.assertIn("brass_key", engine.rooms["library"]["items"])

    def test_using_key_on_locked_exit_unlocks_it(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))
        engine.execute(engine.parse_command("go north"))
        engine.execute(engine.parse_command("take brass key"))
        engine.execute(engine.parse_command("go south"))
        result = engine.execute(engine.parse_command("use brass key on east"))
        self.assertTrue(result["success"])
        self.assertFalse(engine.rooms["great_hall"]["exits"]["east"]["locked"])

    def test_using_wrong_item_on_lock_does_not_unlock(self):
        engine = make_engine()
        # Get the torch instead of the key, and try to use it on the vault door.
        engine.execute(engine.parse_command("go north"))  # great_hall
        engine.execute(engine.parse_command("go north"))  # library
        engine.execute(engine.parse_command("use lever"))
        engine.execute(engine.parse_command("go down"))  # secret_room
        engine.execute(engine.parse_command("take torch"))
        engine.execute(engine.parse_command("go up"))  # library
        engine.execute(engine.parse_command("go south"))  # great_hall
        result = engine.execute(engine.parse_command("use torch on east"))
        self.assertFalse(result["success"])
        self.assertTrue(engine.rooms["great_hall"]["exits"]["east"]["locked"])


class DarkRoomTests(unittest.TestCase):
    def test_entering_dark_room_without_light_source_fails_cleanly(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))  # great_hall
        engine.execute(engine.parse_command("go west"))  # cellar_stairs
        result = engine.execute(engine.parse_command("go down"))  # cellar (dark)
        self.assertFalse(result["success"])
        self.assertNotEqual(engine.get_state()["room"], "cellar")
        self.assertEqual(engine.get_state()["room"], "cellar_stairs")
        self.assertTrue(len(result["message"]) > 0)

    def test_entering_dark_room_with_light_source_works(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))  # great_hall
        engine.execute(engine.parse_command("go north"))  # library
        engine.execute(engine.parse_command("use lever"))
        engine.execute(engine.parse_command("go down"))  # secret_room
        engine.execute(engine.parse_command("take torch"))
        engine.execute(engine.parse_command("go up"))  # library
        engine.execute(engine.parse_command("go south"))  # great_hall
        engine.execute(engine.parse_command("go west"))  # cellar_stairs
        result = engine.execute(engine.parse_command("go down"))  # cellar, now lit
        self.assertTrue(result["success"])
        self.assertEqual(engine.get_state()["room"], "cellar")


class ParserTests(unittest.TestCase):
    def test_unknown_command_returns_dont_understand(self):
        engine = make_engine()
        result = engine.execute(engine.parse_command("xyzzy the frobnicator"))
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "I don't understand that command.")

    def test_malformed_empty_command_does_not_crash(self):
        engine = make_engine()
        result = engine.execute(engine.parse_command(""))
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "I don't understand that command.")

    def test_examine_returns_correct_description(self):
        engine = make_engine()
        result = engine.execute(engine.parse_command("examine carpet"))
        self.assertTrue(result["success"])
        self.assertIn("carpet", result["message"].lower())

    def test_examine_item_in_room(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))
        engine.execute(engine.parse_command("go north"))  # library
        result = engine.execute(engine.parse_command("examine brass key"))
        self.assertTrue(result["success"])
        self.assertIn("key", result["message"].lower())


class WinConditionTests(unittest.TestCase):
    def test_win_does_not_trigger_prematurely(self):
        engine = make_engine()
        engine.execute(engine.parse_command("go north"))  # great_hall
        engine.execute(engine.parse_command("go north"))  # library
        engine.execute(engine.parse_command("take brass key"))
        engine.execute(engine.parse_command("go south"))  # great_hall
        engine.execute(engine.parse_command("use brass key on east"))
        engine.execute(engine.parse_command("go east"))  # vault (has crown, not taken yet)
        self.assertFalse(engine.get_state()["won"])

    def test_full_scripted_playthrough_reaches_win_state(self):
        engine = make_engine()
        commands = [
            "go north",          # entrance_hall -> great_hall
            "go north",          # great_hall -> library
            "take brass key",
            "use lever",
            "go down",           # library -> secret_room
            "take torch",
            "go up",             # secret_room -> library
            "go south",          # library -> great_hall
            "use brass key on east",
            "go east",           # great_hall -> vault
            "take gold crown",
            "go west",           # vault -> great_hall
            "go west",           # great_hall -> cellar_stairs
            "go down",           # cellar_stairs -> cellar (lit by torch)
            "go north",          # cellar -> treasure_room -> WIN
        ]
        last_result = None
        for cmd in commands:
            last_result = engine.execute(engine.parse_command(cmd))

        state = engine.get_state()
        self.assertTrue(state["won"])
        self.assertEqual(state["room"], "treasure_room")
        self.assertIn("gold_crown", state["inventory"])
        self.assertTrue(last_result["success"])


if __name__ == "__main__":
    unittest.main()
