from ..models.round_model import Round
from ..models.hand_model import Hand
from ..models.room_model import Room

# Reshuffle when fewer than 25% of the total cards remain in the shoe.
PENETRATION_PERCENTAGE = 0.25

class RoundService:
    @staticmethod
    def start_round(room_code: str, dealer_nickname: str = "เจ้ามือ") -> dict:
        """เริ่มรอบใหม่ — ตรวจสอบ Shoe และสร้าง dealer hand"""
        room_code = room_code.upper()
        
            # 1. Check Shoe Penetration
        room = Room.get_by_code(room_code)
        if room:
            # If shoe is empty or below threshold (e.g. 25% of total decks), reshuffle
            threshold_cards = max(1, int((room.total_decks * 52) * PENETRATION_PERCENTAGE))
            if len(room.shoe) < threshold_cards:
                room.shuffle_shoe()
                
        # 2. Start new Round (archives old round)
        new_round = Round.start_new_round(room_code)

        # 3. สร้าง dealer hand ทันที (player_token=None = dealer)
        Hand(
            round_id=new_round.id,
            room_code=room_code,
            player_token=None,
            nickname=dealer_nickname,
            role="dealer",
        ).save()

        return {
            "success": True,
            "round": new_round.to_dict(),
            "shoe_shuffled": len(room.shoe) == (room.total_decks * 52) if room else False,
        }

    @staticmethod
    def end_round(room_code: str) -> dict:
        """จบรอบปัจจุบัน และย้ายไพ่ทั้งหมดของรอบนี้ลง discard_pile"""
        current = Round.get_current_round(room_code)
        if not current:
            return {"success": False, "error": "ไม่มีรอบที่กำลังเล่น"}
            
        # 1. Gather all cards played in this round
        hands_in_round = Hand.objects(round_id=current.id)
        cards_to_discard = []
        for hand in hands_in_round:
            for card in hand.cards:
                cards_to_discard.append({"rank": card.rank, "suit": card.suit})
                
        # 2. Append to Room discard pile
        room = Room.get_by_code(room_code)
        if room and cards_to_discard:
            room.discard_pile.extend(cards_to_discard)
            room.save()

        # 3. Mark round as finished
        current.finish()
        
        return {"success": True, "round": current.to_dict()}

    @staticmethod
    def get_current_round(room_code: str):
        return Round.get_current_round(room_code)
