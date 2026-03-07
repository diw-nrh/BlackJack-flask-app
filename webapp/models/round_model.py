import mongoengine as me
import datetime


class Round(me.Document):
    room_code = me.StringField(required=True)
    round_number = me.IntField(required=True, default=1)
    status = me.StringField(
        required=True,
        default="dealing",
        choices=["dealing", "playing", "finished"],
    )
    started_at = me.DateTimeField(default=datetime.datetime.now)
    ended_at = me.DateTimeField()

    meta = {
        "collection": "rounds",
        "indexes": ["room_code"],
        "ordering": ["-round_number"],
    }

    @classmethod
    def start_new_round(cls, room_code: str):
        """เริ่มรอบใหม่ — หยุดรอบก่อนหน้าก่อน"""
        room_code = room_code.upper()

        # ปิดรอบที่ยังค้างอยู่
        cls.objects(room_code=room_code, status__in=["dealing", "playing"]).update(
            status="finished", ended_at=datetime.datetime.now()
        )

        # หา round_number ถัดไป
        last = cls.objects(room_code=room_code).order_by("-round_number").first()
        next_number = (last.round_number + 1) if last else 1

        new_round = cls(room_code=room_code, round_number=next_number, status="playing")
        new_round.save()
        return new_round

    @classmethod
    def get_current_round(cls, room_code: str):
        """ดึงรอบที่กำลังเล่นอยู่"""
        return cls.objects(
            room_code=room_code.upper(), status="playing"
        ).order_by("-round_number").first()

    def finish(self):
        self.status = "finished"
        self.ended_at = datetime.datetime.now()
        self.save()

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_code": self.room_code,
            "round_number": self.round_number,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
