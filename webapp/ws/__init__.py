"""Socket.IO instance — imported by both ws/events.py and web/__init__.py"""
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
        