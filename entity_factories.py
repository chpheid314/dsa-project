from components.ai import HostileEnemy
from components.consumable import HealingConsumable
from components.fighter import Fighter
from components.inventory import Inventory
from entity import Actor, Item

player = Actor(
    char="║",
    color=(255, 255, 255),
    name="Player",
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=30, defense=2, power=5),
    inventory=Inventory(capacity=26),
)

slime = Actor(
    char="═",
    color=(255, 255, 255),
    name="Slime",
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=10, defense=0, power=3),
    inventory=Inventory(capacity=0),
)
cactus = Actor(
    char="╬",
    color=(255, 255, 255),
    name="Cactus",
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=16, defense=1, power=4),
    inventory=Inventory(capacity=0),
)

ghost = Actor(
    char="╣",
    color=(255, 255, 255),
    name="Ghost",
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=18, defense=1, power=5),
    inventory=Inventory(capacity=0),
)

hp_potion = Item(
    char="╩",
    color=(255, 255, 255),
    name="HP Potion",
    consumable=HealingConsumable(amount=4),
)

strong_hp_potion = Item(
    char="╠",
    color=(255, 255, 255),
    name="Strong HP Potion",
    consumable=HealingConsumable(amount=8),
)