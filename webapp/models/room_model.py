import mongoengine as me
import datetime
import random
import string


def generate_room_code(length=6):
    """สร้าง room code แบบสุ่ม 6 ตัวอักษรพิมพ์ใหญ่"""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


class Room(me.Document):
    room_code = me.StringField(required=True, unique=True, max_length=8)
    status = me.StringField(
        required=True,
        default="waiting",
        choices=["waiting", "playing", "finished"],
    )
    created_at = me.DateTimeField(default=datetime.datetime.now)

    meta = {"collection": "rooms", "indexes": ["room_code"]}

    @classmethod
    def create_room(cls):
        """สร้างห้องใหม่พร้อม room_code ที่ไม่ซ้ำ"""
        for _ in range(10):
            code = generate_room_code()
            if not cls.objects(room_code=code).first():
                room = cls(room_code=code)
                room.save()
                return room
        raise ValueError("ไม่สามารถสร้าง room_code ได้ กรุณาลองใหม่")

    @classmethod
    def get_by_code(cls, room_code: str):
        return cls.objects(room_code=room_code.upper()).first()

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_code": self.room_code,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }
