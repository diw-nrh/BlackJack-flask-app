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

    # -------------------------------------------------------------
    # Shoe & Discard State
    # -------------------------------------------------------------
    # Number of decks configured for this room (1, 2, 4, 6, 8)
    total_decks = me.IntField(default=6, choices=[1, 2, 3, 4, 6, 8])
    # Array of remaining cards (dict: rank, suit)
    shoe = me.ListField(me.DictField())
    # Array of played cards
    discard_pile = me.ListField(me.DictField())

    meta = {"collection": "rooms", "indexes": ["room_code"]}

    def shuffle_shoe(self):
        """Clear discard pile, generate configured decks, shuffle, and overwrite shoe."""
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        suits = ["spades", "hearts", "diamonds", "clubs"]
        
        new_shoe = []
        for _ in range(self.total_decks):
            for rank in ranks:
                for suit in suits:
                    new_shoe.append({"rank": rank, "suit": suit})
        
        random.shuffle(new_shoe)
        self.shoe = new_shoe
        self.discard_pile = []
        self.save()

    def get_penetration_percentage(self) -> float:
        """Return percentage of shoe that has been dealt (0.0 to 1.0)."""
        total_cards = len(self.shoe) + len(self.discard_pile)
        if total_cards == 0:
            return 0.0
        return len(self.discard_pile) / total_cards

    def pop_card(self, target_rank: str, target_suit: str) -> dict:
        """
        Pop a specific card from the shoe based on instructor input.
        We search the remaining shoe for this card, remove it, and return it.
        If the exact card isn't found (e.g., shoe is empty or out of that specific card), 
        we just return the requested card (fallback gracefully).
        """
        for i, card in enumerate(self.shoe):
            if card["rank"] == target_rank and card["suit"] == target_suit:
                popped = self.shoe.pop(i)
                self.save()
                return popped
        
        # Fallback: exact card not found in shoe (should rarely happen if tracked correctly)
        # But we don't want to block the game if physical cards don't match digital perfectly.
        return {"rank": target_rank, "suit": target_suit}

    def get_shoe_stats(self) -> dict:
        """คำนวณสถิติของ Shoe ปัจจุบัน สำหรับหน้า Dashboard ของ Teacher"""
        stats = {
            "total_cards": self.total_decks * 52,
            "cards_remaining": len(self.shoe),
            "decks_remaining": round(len(self.shoe) / 52.0, 1),
            "aces": 0,
            "high": 0,  # 10, J, Q, K
            "neutral": 0,  # 7, 8, 9
            "low": 0,    # 2, 3, 4, 5, 6
            "running_count": 0,
        }

        for card in self.shoe:
            rank = card["rank"]
            if rank == "A":
                stats["aces"] += 1
            elif rank in ["10", "J", "Q", "K"]:
                stats["high"] += 1
            elif rank in ["7", "8", "9"]:
                stats["neutral"] += 1
            elif rank in ["2", "3", "4", "5", "6"]:
                stats["low"] += 1

        # Hi-Lo Running Count of the remaining shoe
        rc_shoe = stats["low"] - (stats["high"] + stats["aces"])
        
        # Running Count of all cards DEALT (discard pile + on table)
        # Because a full shoe (any number of decks) has RC = 0.
        stats["running_count"] = -rc_shoe
        
        # True Count = Running Count / Decks Remaining
        decks_rem = max(stats["decks_remaining"], 0.5) # Prevent division by 0 and over-inflation at very end
        stats["true_count"] = round(stats["running_count"] / decks_rem, 1) if stats["cards_remaining"] > 0 else 0
        
        # 10-Value Probability
        if stats["cards_remaining"] > 0:
            stats["ten_probability"] = round((stats["high"] / stats["cards_remaining"]) * 100, 1)
        else:
            stats["ten_probability"] = 0.0

        return stats

    @classmethod
    def create_room(cls, total_decks: int = 6):
        """สร้างห้องใหม่พร้อม room_code ที่ไม่ซ้ำ และสับไพ่เริ่มต้น"""
        for _ in range(10):
            code = generate_room_code()
            if not cls.objects(room_code=code).first():
                room = cls(room_code=code, total_decks=total_decks)
                room.shuffle_shoe()  # Includes save()
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
            "total_decks": self.total_decks,
            "shoe_count": len(self.shoe),
            "discard_count": len(self.discard_pile),
            "shoe_stats": self.get_shoe_stats(),
        }
