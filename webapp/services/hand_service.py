from ..models.hand_model import Hand
from ..models.player_model import Player
from ..models.round_model import Round


class HandService:
    @staticmethod
    def get_or_create_hand(round_id, player_token: str, role: str, room_code: str, hand_index: int = 0) -> Hand:
        """ดึง hand ของผู้เล่น หรือสร้างใหม่ถ้ายังไม่มี"""
        hand = Hand.objects(round_id=round_id, player_token=player_token, hand_index=hand_index).first()
        if hand:
            return hand

        player = Player.get_by_token(player_token)
        nickname = player.nickname if player else "ผู้เล่น"

        hand = Hand(
            round_id=round_id,
            room_code=room_code.upper(),
            player_token=player_token,
            hand_index=hand_index,
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
    def add_card_to_player(room_code: str, player_token: str, rank: str, suit: str, hand_id: str = None) -> dict:
        """เพิ่มไพ่ให้ผู้เล่น — ระบุโดย token หรือ hand_id (สำหรับ split)"""
        current_round = Round.get_current_round(room_code)
        if not current_round:
            return {"success": False, "error": "ยังไม่มีรอบที่กำลังเล่น กรุณาให้อาจารย์เริ่มรอบก่อน"}

        player = Player.get_by_token(player_token)
        if not player:
            return {"success": False, "error": "session ไม่ถูกต้อง"}

        # If a specific hand_id was given (split hand), load it directly
        if hand_id:
            hand = Hand.objects(id=hand_id, round_id=current_round.id).first()
            if not hand:
                return {"success": False, "error": "ไม่พบมือที่ระบุ"}
        else:
            hand = HandService.get_or_create_hand(
                round_id=current_round.id,
                player_token=player_token,
                role=player.role,
                room_code=room_code,
                hand_index=0,
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
        """เพิ่มไพ่ให้ dealer (กองกลาง)"""
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
    def split_hand(room_code: str, player_token: str) -> dict:
        """สร้าง split hand ใหม่สำหรับผู้เล่น"""
        current_round = Round.get_current_round(room_code)
        if not current_round:
            return {"success": False, "error": "ยังไม่มีรอบที่กำลังเล่น"}

        player = Player.get_by_token(player_token)
        if not player:
            return {"success": False, "error": "session ไม่ถูกต้อง"}

        # Find how many hands this player already has in this round
        existing_hands = list(Hand.objects(
            round_id=current_round.id,
            player_token=player_token,
            role__in=["player", "teacher"]
        ).order_by("hand_index"))

        if not existing_hands:
            return {"success": False, "error": "ยังไม่มีมือหลัก กรอกไพ่ก่อนแล้วค่อย split"}

        next_index = len(existing_hands)  # e.g., if 1 hand exists, next is index 1

        new_hand = Hand(
            round_id=current_round.id,
            room_code=room_code.upper(),
            player_token=player_token,
            hand_index=next_index,
            nickname=player.nickname,
            role=player.role,
        )
        new_hand.save()

        return {
            "success": True,
            "hand": new_hand.to_dict(visible=True),
            "nickname": player.nickname,
            "role": player.role,
            "all_hands": [h.to_dict(visible=True) for h in existing_hands + [new_hand]],
        }

    @staticmethod
    def undo_last_card(room_code: str, player_token: str, hand_id: str = None) -> dict:
        """ลบไพ่ใบล่าสุดออก (undo) — รองรับทั้ง main hand และ split hand"""
        current_round = Round.get_current_round(room_code)
        if not current_round:
            return {"success": False, "error": "ไม่มีรอบที่กำลังเล่น"}

        if hand_id:
            hand = Hand.objects(id=hand_id, round_id=current_round.id).first()
        else:
            hand = Hand.objects(round_id=current_round.id, player_token=player_token, hand_index=0).first()

        if not hand or not hand.cards:
            return {"success": False, "error": "ไม่มีไพ่ให้ลบ"}

        hand.remove_last_card()
        return {"success": True, "hand": hand.to_dict(visible=True)}

    @staticmethod
    def get_all_hands_for_player(round_id, player_token: str) -> list:
        """ดึง hand ทั้งหมดของผู้เล่นในรอบนี้ (รวม split)"""
        return list(Hand.objects(round_id=round_id, player_token=player_token).order_by("hand_index"))

    @staticmethod
    def get_all_hands_in_round(round_id) -> list:
        """ดึง hand ทั้งหมดในรอบนี้"""
        return list(Hand.objects(round_id=round_id))

    @staticmethod
    def delete_hand(room_code: str, hand_id: str) -> dict:
        """ลบ hand ตาม ID (ใช้ลบ split hand)"""
        current_round = Round.get_current_round(room_code)
        if not current_round:
            return {"success": False, "error": "ไม่มีรอบที่กำลังเล่น"}

        hand = Hand.objects(id=hand_id, round_id=current_round.id).first()
        if not hand:
            return {"success": False, "error": "ไม่พบมือที่ระบุ"}

        if hand.role == "dealer":
            return {"success": False, "error": "ไม่สามารถลบมือเจ้ามือได้"}

        player_token = hand.player_token
        hand.delete()

        # Re-index remaining hands for this player so hand_index is contiguous
        remaining = list(Hand.objects(
            round_id=current_round.id,
            player_token=player_token
        ).order_by("hand_index"))
        for i, h in enumerate(remaining):
            if h.hand_index != i:
                h.hand_index = i
                h.save()

        return {
            "success": True,
            "player_token": player_token,
            "remaining_hands": [h.to_dict(visible=True) for h in remaining],
        }
