# Dorothy and the Cursed Maze

## 1. References

The core engine infrastructure of this game (including the event dispatch system, console rendering pipeline, and basic memory buffer layout) was developed by referencing and extending the following open-source tutorial code.

- Base Tutorial: [Roguelike Tutorials - Python tcod v2](https://rogueliketutorials.com/tutorials/tcod/v2/)

---

## 2. Game Introduction

- Dorothy must escape from a dungeon maze filled with three types of monsters: a slime, a cactus, and a ghost. The dungeon is implemented as a 2D grid, and Dorothy cannot see the entire map at once. Instead, the camera follows her movement, so she must explore the dungeon step by step and discover new paths as she moves.
- To survive, Dorothy can use up to 30 undo and redo actions, allowing the player to recover from mistakes and plan more carefully. She can also drink two types of potions that restore her health points. The game has three levels that Dorothy must clear, but moving quickly does not always guarantee survival because the player needs strategy, exploration, and careful decision-making.

---

## 3. How to Run

### Environment

- Python 3.12 or later is recommended.
- Developed and tested in the Visual Studio Code environment.

### Install Required Libraries

Run the following command in the project folder.

```bash
pip install tcod numpy
```

### Run the Game

Run the following command in the project root directory.

```bash
python main.py
```

---

## 4. Controls

### Gameplay

| Key     | Function        |
| ------- | --------------- |
| ↑ ↓ ← → | Move the player |
| I       | Open inventory  |
| U       | Undo            |
| R       | Redo            |
| ESC     | Open pause menu |

### Inventory

| Key | Function               |
| --- | ---------------------- |
| A~Z | Select an item         |
| D   | Drop the selected item |
| ESC | Close inventory        |

### Pause Menu and Leaderboard

| Key | Function                                  |
| --- | ----------------------------------------- |
| R   | Resume game                               |
| C   | Clear leaderboard                         |
| F   | Show/Hide score formula                   |
| ↑ ↓ | Scroll leaderboard                        |
| E   | Exit game                                 |
| P   | Restart game (after game over or victory) |

### Mouse Controls

| Action                                   | Function                  |
| ---------------------------------------- | ------------------------- |
| Move the mouse cursor over an entity     | Display the entity's name |
| Move the mouse cursor over an empty tile | Display the timer         |

### Objective

The player must explore a total of three dungeon floors and find the exit to proceed to the next level.

- Defeat enemies and survive.
- Manage health using healing items.
- Clear all three floors to win the game.
- The game ends if the player dies.

At the end of the game, a final score is calculated based on the number of cleared floors, monsters defeated, remaining healing items, remaining HP, and play time. The score is then recorded on the leaderboard.

---

## 5. Core Features Implemented

### Dungeon Map

- Generates a random dungeon floor in the `generate_dungeon()` function of `procgen.py`.
- Operation: Divide the map into multiple regions using the BSP (Binary Space Partitioning) algorithm → Generate a random room in each region → Connect rooms with corridors → Place monsters and items → Generate the exit.
- Features: Uses BSP-based Procedural Generation to automatically create connected dungeons. Room locations and sizes, corridor structures, monster placement, and item placement vary every playthrough, providing high replayability.
- Limitation: The player can descend to lower dungeon floors but cannot return to previous floors.

### Undo System

- Stores snapshots of the entire game state in the `undo_history` and `redo_history` variables of `engine.py`. The `deque` data structure is used, and each variable operates like a stack.
- Operation: Save a snapshot of the game state immediately before a valid player action → Restore a saved snapshot when Undo/Redo is performed.
- Features: Uses the Snapshot-Based Undo algorithm and supports up to 30 Undo/Redo actions.
- Limitation: Actions that do not change the game state (such as attempting to walk into a wall) are not recorded in the Undo history.

### Turn Management

- Manages the turn order of all actors (Player and Enemies) using the `turn_queue` variable in `engine.py`. Implemented using the `deque` data structure in a Queue (FIFO) manner.
- Operation: Register the player and all living enemies in the Turn Queue at the start of the game → Process the player's action → Process enemy actions in queue order → Reinsert actors at the back of the queue after acting → Stop turn processing when the player's turn is reached again.
- Features: Uses a Queue-based Round-Robin scheduling algorithm so that all actors receive fair opportunities to act. Dead actors are automatically excluded from turn processing.
- Limitation: All actors currently have the same action speed, and turn priority or speed attributes are not supported.

### Item Inventory

- Manages items carried by the player using the `Inventory` class in `inventory.py`. Internally uses a List data structure to store items.
- Operation: Add items to the inventory when picked up → Select an item from the inventory screen → Use or Drop the item → Consumable items are automatically removed after use.
- Features: Items are managed as objects, and various consumable items can be used through a unified interface using the `Consumable` interface. Provides an alphabet-based (A–Z) selection interface and can store up to 26 items.
- Limitation: New items cannot be picked up when the inventory is full, and only the player can use the inventory.

### Enemy AI

- Controls enemy behavior using the `HostileEnemy` class in `components/ai.py`. Paths are stored as coordinate lists using the List data structure.
- Operation: When the player enters the enemy's field of view, compute the shortest path using the A\* (A-Star) pathfinding algorithm → Move toward the player → Perform a melee attack when adjacent.
- Features: Uses the A\* algorithm with the Manhattan Distance heuristic. Additional movement costs are applied to tiles occupied by other monsters to reduce excessive crowding in a single location.
- Limitation: No pathfinding is performed when the player is outside the enemy's field of view. All currently implemented enemies (Slime, Cactus, and Ghost) use the same AI logic.

### Leaderboard

- Stores game results and manages rankings in `leaderboard.py`. Score data is stored in a JSON file and internally managed using a Binary Search Tree (BST).
- Operation: Calculate the score using cleared floors, defeated monsters, remaining healing items, remaining HP, and play time at the end of the game → Insert the score into the BST → Sort scores in descending order using Reverse Inorder Traversal → Display them on the leaderboard.
- Features: Uses a BST-based sorting algorithm to prioritize higher scores. Records persist even after restarting the game. Also provides a scrollable ranking screen and a score formula display feature.
- Limitation: No special tie-breaking rules are implemented for identical scores, and rankings are currently stored only in a local JSON file.

---

## 6. Additional Features

### Game Timer

- Measures game play time in `engine.py`.
- Operation: Start the timer when the game begins → Pause time measurement when the game is paused → Resume measurement when the game resumes → Record the final play time when the game ends.
- Features: Calculates elapsed time in minutes and seconds, displays it in real time on the screen, and uses it to determine score bonuses and penalties.
- Limitation: Only active gameplay time is measured; time spent while the game is paused is excluded.

### Pastel Visual Design

- Implements game graphics by modifying a CP437 character-set-based tileset image.
- Operation: Scale the `dejavu10x10_gs_tc.png` tileset to 64×64 resolution → Use Aseprite to manually create custom sprites for the player, monsters, and items on unused character slots → Use the sprites for in-game entity rendering.
- Features: Instead of simply using the original tileset, custom sprites were designed to visually distinguish the player, monsters, and items. All entities are represented using 64×64 graphics.
- Limitation: Since the design reuses character slots within the existing tileset, the number of available sprites is constrained by the tileset structure.

### Camera System

- Implements camera functionality in `engine.py` and `game_map.py`.
- Operation: Calculate the camera center based on the player's position → Determine the visible map region → Render only that region.
- Features: Uses a Follow Camera algorithm that keeps the player centered on the screen, enabling exploration of large dungeons while improving readability by rendering only the visible area.
- Limitation: Camera movement is restricted near map boundaries, and the screen size is fixed.
