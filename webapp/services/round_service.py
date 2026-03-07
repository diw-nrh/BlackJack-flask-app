from ..models.round_model import Round
from ..models.hand_model import Hand


class RoundService:
    @staticmethod
    def start_round(room_code: str, dealer_nickname: str = "เจ้ามือ") -> dict:
        """เริ่มรอบใหม่ — ล้าง hand เก่า สร้าง dealer hand"""
        room_code = room_code.upper()
        new_round = Round.start_new_round(room_code)

        # สร้าง dealer hand ทันที (player_token=None = dealer)
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
        }

    @staticmethod
    def end_round(room_code: str) -> dict:
        """จบรอบปัจจุบัน"""
        current = Round.get_current_round(room_code)
        if not current:
            return {"success": False, "error": "ไม่มีรอบที่กำลังเล่น"}
        current.finish()
        return {"success": True, "round": current.to_dict()}

    @staticmethod
    def get_current_round(room_code: str):
        return Round.get_current_round(room_code)
