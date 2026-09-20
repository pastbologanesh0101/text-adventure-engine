# Text Adventure Engine

A small, data-driven interactive fiction engine written in pure Python
(standard library only, no dependencies). Worlds — rooms, items, NPCs,
locks, and win/lose conditions — are described entirely in a JSON file.
The engine loads that file and lets a player explore it through a
verb-noun command parser.

The game logic (`GameEngine`) is fully decoupled from I/O: it exposes
`parse_command`, `execute`, and `get_state`, so the whole engine can be
driven and tested by feeding it plain command strings, with no real
stdin/stdout required. `play.py` is a thin CLI wrapper around it.

A complete bundled adventure, **"The Manor of Whispering Stone"** (8
rooms), ships in `world.json` and demonstrates every engine feature:
a locked door + key puzzle, a lever/flag puzzle that reveals a hidden
room, a dark room that requires a light source, and a win condition.

## Running it

```bash
python3 play.py world.json
```

(`world.json` is also the default if you omit the argument: `python3 play.py`.)

Type commands at the `>` prompt, e.g. `go north`, `take key`, `use key on east`,
`examine armor`, `inventory`. Type `quit` to exit.

## Running the tests

```bash
python3 -m pytest tests/ -v
# or
python3 -m unittest discover -s tests -v
```

17 unit tests cover movement, locks/keys, item pickup/drop, the
dark-room/light-source puzzle, the flag/lever puzzle, the parser's
synonym handling and error handling, `examine`, and a full scripted
playthrough that reaches the win state.

## World-file format

A world file is a single JSON object:

```json
{
  "title": "The Manor of Whispering Stone",
  "start_room": "entrance_hall",
  "dark_message": "It's pitch black and you can't see a thing...",
  "win": {
    "room": "treasure_room",
    "requires_items": ["gold_crown"],
    "message": "You have found the lost treasure! YOU WIN!"
  },
  "rooms": { "...": "see below" },
  "items": { "...": "see below" }
}
```

| Field | Type | Meaning |
|---|---|---|
| `start_room` | string | Room id the player starts in. |
| `dark_message` | string (optional) | Default message shown when the player tries to enter a `dark` room with no light source. Falls back to a built-in message if omitted. |
| `win` | object | Win condition: `room` (room id the player must be standing in) and `requires_items` (list of item ids that must be in inventory). `message` is shown on victory. |
| `rooms` | object | Map of room id -> room object. |
| `items` | object | Map of item id -> item object. |

### Room object

```json
"cellar": {
  "name": "Cellar",
  "description": "A cold stone cellar...",
  "dark": true,
  "dark_message": "optional per-room override of the global dark_message",
  "exits": {
    "up": {"to": "cellar_stairs"},
    "north": {"to": "treasure_room", "locked": true, "key": "some_key"}
  },
  "items": ["torch"],
  "features": {
    "barrels": "Old wine barrels, long since empty."
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Display name. |
| `description` | string | Shown on `look` / on entering. |
| `dark` | bool (optional) | If true, the room can't be seen/entered without a light-source item in inventory. |
| `exits` | object | Map of direction (`north`/`south`/`east`/`west`/`up`/`down`) -> exit object. |
| `items` | list[string] | Item ids currently lying in the room. |
| `features` | object | Map of inspectable-but-not-takeable feature name -> description, for `examine`. |

**Exit object**: `to` (target room id, required). Optionally `locked: true`
plus **one** of:
- `key`: an item id — the exit unlocks when that item is `use`d on this
  exit while the player is in this room (see `use` below).
- `requires_flag`: a flag name — the exit unlocks automatically the
  moment that flag is set (e.g. by using a lever-like item).

### Item object

```json
"brass_key": {
  "name": "Brass Key",
  "description": "A small tarnished brass key.",
  "takeable": true,
  "unlocks_exit": {"room": "great_hall", "direction": "east"}
}
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Display name. |
| `description` | string | Shown by `examine`. |
| `takeable` | bool | Whether `take`/`drop` work on it. Non-takeable items (like a wall-mounted lever) can still be `use`d while present in the room. |
| `is_light_source` | bool (optional) | Carrying this item lets the player see in / enter `dark` rooms. |
| `unlocks_exit` | object (optional) | `{"room": <room id>, "direction": <direction>}` — using this item while standing in that room unlocks that exit, provided the exit's `key` matches this item's id. |
| `sets_flag` | string (optional) | Using this item sets a world-state flag with this name (and immediately unlocks any exits in the current room whose `requires_flag` matches). |
| `use_message` | string (optional) | Message shown when this item is successfully `use`d (for `is_light_source` / `sets_flag` items). |

## Commands and synonyms

| Command | Synonyms | Notes |
|---|---|---|
| `look` | `l` | Redescribes the current room. |
| `go <direction>` | `move`, `walk`, `head`; or just the bare direction (`north`, `n`, ...) | Directions: `north`/`n`, `south`/`s`, `east`/`e`, `west`/`w`, `up`/`u`, `down`/`d`. |
| `take <item>` | `get`, `grab`, `pickup` | Moves item from room to inventory (if `takeable`). |
| `drop <item>` | `leave`, `discard` | Moves item from inventory to room. |
| `inventory` | `inv`, `i` | Lists what you're carrying. |
| `use <item> [on <target>]` | `apply` | Applies the item's effect; `<target>` is typically a direction, e.g. `use brass key on east`. |
| `examine <item or feature>` | `x`, `exam`, `inspect`, `look <thing>`, `look at <thing>` | Describes an item (in inventory or room) or a room feature. |

Any input that doesn't parse into one of the above (unknown verb, missing
argument, gibberish, empty string) returns exactly:

```
I don't understand that command.
```

— the engine never raises an exception on bad input.

## The bundled adventure: The Manor of Whispering Stone

8 rooms: `entrance_hall`, `great_hall`, `library`, `secret_room`,
`cellar_stairs`, `cellar` (dark), `vault` (locked), `treasure_room` (win room).

Puzzle chain:
1. **Locked door + key**: the `vault` (east of `great_hall`) is locked;
   the `brass_key` is in the `library`. `use brass key on east` from the
   Great Hall unlocks it.
2. **Lever/flag puzzle**: the `library` has a non-takeable `lever`. Using
   it (`use lever`) sets the `lever_pulled` flag, which unlocks the
   `down` exit to the `secret_room`, where the `torch` (light source)
   is found.
3. **Dark room + light source**: the `cellar` (west of `great_hall`, down
   from `cellar_stairs`) is `dark`. Entering it without the `torch` fails
   with a clear message and leaves you in `cellar_stairs`; carrying the
   torch lets you enter normally.
4. **Win condition**: reach `treasure_room` (north of `cellar`) while
   carrying the `gold_crown` (found in the `vault`).

### Example playthrough transcript

```
=============================
The Manor of Whispering Stone
=============================

Entrance Hall. A grand entrance hall with a faded red carpet leading
north. Cobwebs cling to the corners of the ceiling. Exits: north.

> go north
Great Hall. A vast hall with a suit of armor standing guard and a
dust-covered chandelier overhead. Exits: east, north, south, west.

> go north
Library. Dusty shelves of forgotten books line every wall. A rusty
lever protrudes from the wall near the fireplace. You see: Brass Key,
Lever. Exits: down, south.

> take brass key
You take the Brass Key.

> use lever
You pull the lever. Somewhere in the manor, stone grinds against stone.

> go down
Secret Room. A hidden room revealed by the lever. A single torch rests
on a stone pedestal. You see: Torch. Exits: up.

> take torch
You take the Torch.

> go up
Library. ... Exits: down, south.

> go south
Great Hall. ... Exits: east, north, south, west.

> use brass key on east
You unlock the door to the east.

> go east
Vault. A small stone vault. A golden crown rests on a velvet cushion.
You see: Gold Crown. Exits: west.

> take gold crown
You take the Gold Crown.

> go west
Great Hall. ... Exits: east, north, south, west.

> go west
Cellar Stairs. Rickety wooden stairs descend into darkness below.
Exits: down, east.

> go down
Cellar. A cold stone cellar. Your torchlight flickers over old barrels
and crates. Exits: north, up.

> go north
The crown gleams in your hands. You have found the lost treasure of
Whispering Stone. YOU WIN!

*** THE END ***
```

## Project layout

```
engine.py               # GameEngine core: parse_command / execute / get_state
play.py                 # Interactive CLI loop (I/O only, no game logic)
world.json              # Bundled adventure: "The Manor of Whispering Stone"
tests/test_engine.py    # 17 unit tests
.github/workflows/tests.yml
LICENSE
```

## License

MIT — see [LICENSE](LICENSE).
