from flask_mongoengine import MongoEngine
from flask import Flask

db = MongoEngine()


def init_db(app: Flask):
    db.init_app(app)
    # Register models
    from .room_model import Room  # noqa: F401
    from .player_model import Player  # noqa: F401
    from .round_model import Round  # noqa: F401
    from .hand_model import Hand, Card  # noqa: F401
