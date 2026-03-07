import mongoengine as me
import datetime


RANK_VALUES = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 10, "Q": 10, "K": 10,
    "A": 11,  # จะปรับเป็น 1 ถ้า bust
}


def calculate_score(cards: list) -> int:
    """คำนวณคะแนน Blackjack — จัดการ Ace อัตโนมัติ"""
    total = 0
    aces = 0
    for card in cards:
        val = RANK_VALUES.get(card.rank, 0)
        if card.rank == "A":
            aces += 1
        total += val
    # ลด Ace จาก 11 → 1 ถ้า bust
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


class Card(me.EmbeddedDocument):
    rank = me.StringField(
        required=True,
        choices=["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"],
    )
    suit = me.StringField(
        required=True,
        choices=["spades", "hearts", "diamonds", "clubs"],
    )
    seq = me.IntField(default=0)
    added_at = me.DateTimeField(default=datetime.datetime.now)

    def value(self) -> int:
        return RANK_VALUES.get(self.rank, 0)

    def to_dict(self):
        return {
            "rank": self.rank,
            "suit": self.suit,
            "seq": self.seq,
        }


class Hand(me.Document):
    round_id = me.ObjectIdField(required=True)
    room_code = me.StringField(required=True)
    # player_token=None หมายถึง dealer/กองกลาง
    player_token = me.StringField()
    nickname = me.StringField(default="เจ้ามือ")
    role = me.StringField(
        required=True,
        choices=["player", "teacher", "dealer"],
    )
    cards = me.EmbeddedDocumentListField(Card)
    is_busted = me.BooleanField(default=False)
    is_blackjack = me.BooleanField(default=False)
    score = me.IntField(default=0)
    updated_at = me.DateTimeField(default=datetime.datetime.now)

    meta = {
        "collection": "hands",
        "indexes": ["round_id", "room_code", "player_token"],
    }

    def add_card(self, rank: str, suit: str):
        """เพิ่มไพ่ใหม่ คำนวณ score และเช็ค bust / blackjack"""
        card = Card(rank=rank, suit=suit, seq=len(self.cards) + 1)
        self.cards.append(card)
        self.score = calculate_score(self.cards)
        self.is_busted = self.score > 21
        self.is_blackjack = (
            len(self.cards) == 2
            and self.score == 21
            and any(c.rank == "A" for c in self.cards)
        )
        self.updated_at = datetime.datetime.now()
        self.save()
        return card

    def remove_last_card(self):
        """ลบไพ่ใบล่าสุด (undo)"""
        if self.cards:
            self.cards.pop()
            self.score = calculate_score(self.cards)
            self.is_busted = self.score > 21
            self.is_blackjack = False
            self.save()

    def to_dict(self, visible=True):
        """แปลงเป็น dict — visible=False ซ่อนไพ่ (ใช้สำหรับ teacher)"""
        return {
            "id": str(self.id),
            "player_token": self.player_token,
            "nickname": self.nickname,
            "role": self.role,
            "score": self.score if visible else None,
            "is_busted": self.is_busted if visible else None,
            "is_blackjack": self.is_blackjack if visible else None,
            "cards": [c.to_dict() for c in self.cards] if visible else [],
            "card_count": len(self.cards),
        }
