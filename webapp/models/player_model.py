import mongoengine as me
import datetime
import uuid


class Player(me.Document):
    room_code = me.StringField(required=True)
    nickname = me.StringField(required=True, max_length=30)
    role = me.StringField(
        required=True,
        choices=["player", "teacher"],
    )
    session_token = me.StringField(required=True, unique=True)
    joined_at = me.DateTimeField(default=datetime.datetime.now)
    is_active = me.BooleanField(default=True)

    meta = {
        "collection": "players",
        "indexes": ["room_code", "session_token"],
    }

    @classmethod
    def create_player(cls, room_code: str, nickname: str, role: str):
        """สร้างผู้เล่นใหม่พร้อม session_token"""
        token = str(uuid.uuid4())
        player = cls(
            room_code=room_code.upper(),
            nickname=nickname.strip(),
            role=role,
            session_token=token,
        )
        player.save()
        return player

    @classmethod
    def get_by_token(cls, token: str):
        return cls.objects(session_token=token, is_active=True).first()

    @classmethod
    def get_room_players(cls, room_code: str):
        """ดึงผู้เล่นทั้งหมดในห้อง"""
        return cls.objects(room_code=room_code.upper(), is_active=True)

    @classmethod
    def get_room_teachers(cls, room_code: str):
        return cls.objects(room_code=room_code.upper(), role="teacher", is_active=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_code": self.room_code,
            "nickname": self.nickname,
            "role": self.role,
            "session_token": self.session_token,
            "joined_at": self.joined_at.isoformat(),
        }
