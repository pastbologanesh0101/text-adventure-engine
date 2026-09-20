"""
engine.py -- Text Adventure Engine core.

Pure-Python, stdlib-only, data-driven interactive fiction engine.

The engine is deliberately split into two layers:

  * GameEngine: pure game logic (parse_command / execute / get_state).
    It never touches stdin/stdout, so it can be driven entirely by
    feeding it command strings and inspecting the returned dict / state.
  * play.py: a thin CLI loop that reads from stdin, calls the engine,
    and prints the results.

See README.md for the full world-file schema.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional


MSG_UNKNOWN = "I don't understand that command."
MSG_NO_EXIT = "You can't go that way."
MSG_NOTHING_HAPPENS = "Nothing happens."
MSG_DONT_HAVE = "You don't have that."
MSG_DONT_SEE = "You don't see that here."
MSG_TOO_DARK = "It's too dark to see anything."
DEFAULT_DARK_MESSAGE = (
    "It's pitch black and you can't see a thing. "
    "You feel your way back before you get hurt."
)

DIRECTION_SYNONYMS = {
    "n": "north", "north": "north",
    "s": "south", "south": "south",
    "e": "east", "east": "east",
    "w": "west", "west": "west",
    "u": "up", "up": "up",
    "d": "down", "down": "down",
}

VERB_SYNONYMS = {
    "go": "go", "move": "go", "walk": "go", "head": "go",
    "look": "look", "l": "look",
    "take": "take", "get": "take", "grab": "take", "pickup": "take",
    "drop": "drop", "leave": "drop", "discard": "drop",
    "inventory": "inventory", "inv": "inventory", "i": "inventory",
    "use": "use", "apply": "use",
    "examine": "examine", "x": "examine", "exam": "examine", "inspect": "examine",
}


def load_world(path: str) -> Dict[str, Any]:
    """Load and return a world definition from a JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class GameEngine:
    """Pure game-logic engine, driven entirely by command strings/dicts."""

    def __init__(self, world: Dict[str, Any]):
        self.world = world
        # Deep-copy mutable parts so each engine instance owns independent
        # state, even if several engines are built from the same loaded
        # world dict (important for tests).
        self.rooms: Dict[str, Any] = copy.deepcopy(world.get("rooms", {}))
        self.items: Dict[str, Any] = copy.deepcopy(world.get("items", {}))
        self.start_room: str = world["start_room"]
        self.win_condition: Dict[str, Any] = world.get("win", {})
        self.dark_message_default: str = world.get("dark_message", DEFAULT_DARK_MESSAGE)

        self.state: Dict[str, Any] = {
            "room": self.start_room,
            "inventory": [],
            "flags": {},
            "won": False,
            "lost": False,
        }

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse_command(self, raw: str) -> Dict[str, Any]:
        """Parse a raw command string into {'verb': ..., 'args': [...]}.

        Unrecognized/malformed input always yields {'verb': 'unknown'}
        rather than raising an exception.
        """
        if raw is None:
            return {"verb": "unknown", "args": []}
        text = raw.strip().lower()
        if not text:
            return {"verb": "unknown", "args": []}

        tokens = text.split()
        first = tokens[0]

        # Bare direction word used as a command, e.g. "north" or "n".
        if first in DIRECTION_SYNONYMS and len(tokens) == 1:
            return {"verb": "go", "args": [DIRECTION_SYNONYMS[first]]}

        # "look at X" / "look X" -> examine X ; "look" alone -> look
        if first in ("look", "l"):
            rest = tokens[1:]
            if not rest:
                return {"verb": "look", "args": []}
            if rest[0] == "at":
                rest = rest[1:]
            if not rest:
                return {"verb": "look", "args": []}
            return {"verb": "examine", "args": [" ".join(rest)]}

        verb = VERB_SYNONYMS.get(first)
        if verb is None:
            return {"verb": "unknown", "args": []}

        rest = tokens[1:]

        if verb == "go":
            if not rest:
                return {"verb": "unknown", "args": []}
            direction = DIRECTION_SYNONYMS.get(rest[0], rest[0])
            return {"verb": "go", "args": [direction]}

        if verb == "use":
            if not rest:
                return {"verb": "unknown", "args": []}
            if "on" in rest:
                idx = rest.index("on")
                item_name = " ".join(rest[:idx]).strip()
                target = " ".join(rest[idx + 1:]).strip()
                if not item_name:
                    return {"verb": "unknown", "args": []}
                return {"verb": "use", "args": [item_name, target or None]}
            return {"verb": "use", "args": [" ".join(rest), None]}

        if verb in ("take", "drop", "examine"):
            if not rest:
                return {"verb": "unknown", "args": []}
            return {"verb": verb, "args": [" ".join(rest)]}

        if verb in ("look", "inventory"):
            return {"verb": verb, "args": []}

        return {"verb": "unknown", "args": []}

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a parsed command dict, mutating self.state as needed.

        Returns {'success': bool, 'message': str}.
        """
        verb = command.get("verb", "unknown")
        args = command.get("args", []) or []

        if self.state.get("won"):
            return {"success": False, "message": "The adventure is already won! Start a new game to play again."}
        if self.state.get("lost"):
            return {"success": False, "message": "The adventure has ended. Start a new game to play again."}

        try:
            if verb == "go":
                return self._cmd_go(args[0])
            if verb == "look":
                return self._cmd_look()
            if verb == "take":
                return self._cmd_take(args[0])
            if verb == "drop":
                return self._cmd_drop(args[0])
            if verb == "inventory":
                return self._cmd_inventory()
            if verb == "use":
                item_name = args[0] if len(args) > 0 else None
                target = args[1] if len(args) > 1 else None
                if not item_name:
                    return {"success": False, "message": MSG_UNKNOWN}
                return self._cmd_use(item_name, target)
            if verb == "examine":
                return self._cmd_examine(args[0])
        except (IndexError, KeyError):
            return {"success": False, "message": MSG_UNKNOWN}

        return {"success": False, "message": MSG_UNKNOWN}

    def get_state(self) -> Dict[str, Any]:
        """Return a defensive copy of the current game state."""
        return {
            "room": self.state["room"],
            "inventory": list(self.state["inventory"]),
            "flags": dict(self.state["flags"]),
            "won": self.state["won"],
            "lost": self.state["lost"],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_room(self) -> Dict[str, Any]:
        return self.rooms[self.state["room"]]

    def _has_light_source(self) -> bool:
        for item_id in self.state["inventory"]:
            if self.items.get(item_id, {}).get("is_light_source"):
                return True
        return False

    def _room_is_dark_for_player(self, room_id: str) -> bool:
        return bool(self.rooms[room_id].get("dark")) and not self._has_light_source()

    def _match_name(self, query: str, item_id: str) -> bool:
        query = query.strip().lower()
        item = self.items.get(item_id, {})
        id_as_words = item_id.replace("_", " ").lower()
        name = item.get("name", "").lower()
        return query == id_as_words or query == name or query == item_id.lower()

    def _find_item_in(self, query: str, item_ids: List[str]) -> Optional[str]:
        for item_id in item_ids:
            if self._match_name(query, item_id):
                return item_id
        return None

    def _resolve_usable_item(self, query: str) -> Optional[str]:
        """Find an item by name, first in inventory, then in the current room."""
        found = self._find_item_in(query, self.state["inventory"])
        if found:
            return found
        found = self._find_item_in(query, self._current_room().get("items", []))
        return found

    def _check_win(self) -> None:
        if self.state["won"] or not self.win_condition:
            return
        if self.state["room"] != self.win_condition.get("room"):
            return
        required = self.win_condition.get("requires_items", [])
        if all(item_id in self.state["inventory"] for item_id in required):
            self.state["won"] = True

    def _describe_room(self, room_id: str) -> str:
        room = self.rooms[room_id]
        if self._room_is_dark_for_player(room_id):
            return self.dark_message_default
        parts = [room["name"] + ".", room["description"]]
        item_names = [self.items[i]["name"] for i in room.get("items", []) if i in self.items]
        if item_names:
            parts.append("You see: " + ", ".join(item_names) + ".")
        exits = sorted(room.get("exits", {}).keys())
        if exits:
            parts.append("Exits: " + ", ".join(exits) + ".")
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Command implementations
    # ------------------------------------------------------------------
    def _cmd_go(self, direction: str) -> Dict[str, Any]:
        direction = DIRECTION_SYNONYMS.get(direction, direction)
        room = self._current_room()
        exit_ = room.get("exits", {}).get(direction)
        if not exit_:
            return {"success": False, "message": MSG_NO_EXIT}

        if exit_.get("locked"):
            return {"success": False, "message": f"The door to the {direction} is locked."}

        target_room_id = exit_["to"]

        if self._room_is_dark_for_player(target_room_id):
            message = self.rooms[target_room_id].get("dark_message", self.dark_message_default)
            return {"success": False, "message": message}

        self.state["room"] = target_room_id
        self._check_win()
        if self.state["won"]:
            return {"success": True, "message": self.win_condition.get("message", "You win!")}
        return {"success": True, "message": self._describe_room(target_room_id)}

    def _cmd_look(self) -> Dict[str, Any]:
        return {"success": True, "message": self._describe_room(self.state["room"])}

    def _cmd_take(self, name: str) -> Dict[str, Any]:
        room = self._current_room()
        room_items = room.get("items", [])
        item_id = self._find_item_in(name, room_items)
        if not item_id:
            return {"success": False, "message": MSG_DONT_SEE}
        item = self.items.get(item_id, {})
        if not item.get("takeable", False):
            return {"success": False, "message": f"You can't take the {item.get('name', name)}."}
        room_items.remove(item_id)
        self.state["inventory"].append(item_id)
        self._check_win()
        if self.state["won"]:
            return {"success": True, "message": self.win_condition.get("message", "You win!")}
        return {"success": True, "message": f"You take the {item['name']}."}

    def _cmd_drop(self, name: str) -> Dict[str, Any]:
        item_id = self._find_item_in(name, self.state["inventory"])
        if not item_id:
            return {"success": False, "message": MSG_DONT_HAVE}
        self.state["inventory"].remove(item_id)
        self._current_room().setdefault("items", []).append(item_id)
        item = self.items.get(item_id, {})
        return {"success": True, "message": f"You drop the {item.get('name', name)}."}

    def _cmd_inventory(self) -> Dict[str, Any]:
        if not self.state["inventory"]:
            return {"success": True, "message": "You are not carrying anything."}
        names = [self.items[i]["name"] for i in self.state["inventory"] if i in self.items]
        return {"success": True, "message": "You are carrying: " + ", ".join(names) + "."}

    def _cmd_use(self, name: str, target: Optional[str]) -> Dict[str, Any]:
        item_id = self._resolve_usable_item(name)
        if not item_id:
            return {"success": False, "message": MSG_DONT_HAVE}
        item = self.items.get(item_id, {})

        unlocks = item.get("unlocks_exit")
        if unlocks:
            room_id = unlocks.get("room")
            direction = unlocks.get("direction")
            if self.state["room"] != room_id:
                return {"success": False, "message": MSG_NOTHING_HAPPENS}
            if target:
                norm_target = DIRECTION_SYNONYMS.get(target.strip().lower(), target.strip().lower())
                if norm_target != direction:
                    return {"success": False, "message": MSG_NOTHING_HAPPENS}
            exit_ = self.rooms[room_id].get("exits", {}).get(direction)
            if not exit_ or not exit_.get("locked") or exit_.get("key") != item_id:
                return {"success": False, "message": MSG_NOTHING_HAPPENS}
            exit_["locked"] = False
            return {"success": True, "message": f"You unlock the door to the {direction}."}

        # From here on, none of the remaining effects are "targeted": if the
        # caller asked to use this item "on" something and it isn't the
        # unlocks_exit case above, nothing should happen.
        if target:
            return {"success": False, "message": MSG_NOTHING_HAPPENS}

        sets_flag = item.get("sets_flag")
        if sets_flag:
            self.state["flags"][sets_flag] = True
            for _direction, exit_ in self._current_room().get("exits", {}).items():
                if exit_.get("locked") and exit_.get("requires_flag") == sets_flag:
                    exit_["locked"] = False
            return {"success": True, "message": item.get("use_message", MSG_NOTHING_HAPPENS)}

        if item.get("is_light_source"):
            return {"success": True, "message": item.get("use_message", "The light source is ready.")}

        return {"success": False, "message": MSG_NOTHING_HAPPENS}

    def _cmd_examine(self, name: str) -> Dict[str, Any]:
        # Inventory items can always be examined, even in the dark.
        item_id = self._find_item_in(name, self.state["inventory"])
        if item_id:
            return {"success": True, "message": self.items[item_id]["description"]}

        room = self._current_room()
        if self._room_is_dark_for_player(self.state["room"]):
            return {"success": False, "message": MSG_TOO_DARK}

        item_id = self._find_item_in(name, room.get("items", []))
        if item_id:
            return {"success": True, "message": self.items[item_id]["description"]}

        features = room.get("features", {})
        query = name.strip().lower()
        for feature_name, description in features.items():
            if query == feature_name.lower():
                return {"success": True, "message": description}

        return {"success": False, "message": MSG_DONT_SEE}
