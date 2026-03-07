from ..models.hand_model import Hand
from ..models.player_model import Player
from ..models.round_model import Round


class HandService:
    @staticmethod
    def get_or_create_hand(round_id, player_token: str, role: str, room_code: str) -> Hand:
        """ดึง hand ของผู้เล่น หรือสร้างใหม่ถ้ายังไม่มี"""
        hand = Hand.objects(round_id=round_id, player_token=player_token).first()
        if hand:
            return hand

        player = Player.get_by_token(player_token)
        nickname = player.nickname if player else "ผู้เล่น"

        hand = Hand(
            round_id=round_id,
            room_code=room_code.upper(),
            player_token=player_token,
            nickname=nickname,
            role=role,
        )
        hand.save()
        return hand

    @staticmethod
    def get_dealer_hand(round_id) -> Hand:
        """ดึง dealer hand ของรอบนั้น"""
        return Hand.objects(round_id=round_id, role="dealer").first()

    @staticmethod
    def add_card_to_player(room_code: str, player_token: str, rank: str, suit: str) -> dict:
        """เพิ่มไพ่ให้ผู้เล่น — ระบุโดย token"""
        current_round = Round.get_current_round(room_code)
        if not current_round:
            return {"success": False, "error": "ยังไม่มีรอบที่กำลังเล่น กรุณาให้อาจารย์เริ่มรอบก่อน"}

        player = Player.get_by_token(player_token)
        if not player:
            return {"success": False, "error": "session ไม่ถูกต้อง"}

        hand = HandService.get_or_create_hand(
            round_id=current_round.id,
            player_token=player_token,
            role=player.role,
            room_code=room_code,
        )

        if hand.is_busted:
            return {"success": False, "error": "bust แล้ว ไม่สามารถหยิบไพ่เพิ่มได้"}

        card = hand.add_card(rank=rank, suit=suit)
        return {
            "success": True,
            "card": card.to_dict(),
            "hand": hand.to_dict(visible=True),
            "nickname": player.nickname,
            "role": player.role,
        }

    @staticmethod
    def add_card_to_dealer(room_code: str, rank: str, suit: str) -> dict:
        """เพิ่มไพ่ให้ dealer (กองกลาง) — ใช้โดยอาจารย์"""
        current_round = Round.get_current_round(room_code)
        if not current_round:
            return {"success": False, "error": "ยังไม่มีรอบที่กำลังเล่น"}

        hand = HandService.get_dealer_hand(current_round.id)
        if not hand:
            return {"success": False, "error": "ไม่พบ dealer hand กรุณาเริ่มรอบใหม่"}

        card = hand.add_card(rank=rank, suit=suit)
        return {
            "success": True,
            "card": card.to_dict(),
            "hand": hand.to_dict(visible=True),
        }

    @staticmethod
    def undo_last_card(room_code: str, player_token: str) -> dict:
        """ลบไพ่ใบล่าสุดออก (undo)"""
        current_round = Round.get_current_round(room_code)
        if not current_round:
            return {"success": False, "error": "ไม่มีรอบที่กำลังเล่น"}

        hand = Hand.objects(round_id=current_round.id, player_token=player_token).first()
        if not hand or not hand.cards:
            return {"success": False, "error": "ไม่มีไพ่ให้ลบ"}

        hand.remove_last_card()
        return {"success": True, "hand": hand.to_dict(visible=True)}

    @staticmethod
    def get_all_hands_in_round(round_id) -> list:
        """ดึง hand ทั้งหมดในรอบนี้"""
        return list(Hand.objects(round_id=round_id))
