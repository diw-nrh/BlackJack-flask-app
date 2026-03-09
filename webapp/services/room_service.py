from ..models.room_model import Room
from ..models.player_model import Player
from ..models.round_model import Round
from ..models.hand_model import Hand


class RoomService:
    @staticmethod
    def create_room() -> dict:
        """สร้างห้องใหม่ คืนค่า room_code"""
        room = Room.create_room()
        return {"success": True, "room_code": room.room_code, "room": room.to_dict()}

    @staticmethod
    def join_room(room_code: str, nickname: str, role: str) -> dict:
        """เข้าร่วมห้อง — สร้าง Player + session_token"""
        room = Room.get_by_code(room_code)
        if not room:
            return {"success": False, "error": f"ไม่พบห้อง '{room_code}'"}

        if room.status == "finished":
            return {"success": False, "error": "ห้องนี้จบเกมแล้ว"}

        player = Player.create_player(
            room_code=room.room_code,
            nickname=nickname,
            role=role,
        )
        return {
            "success": True,
            "room_code": room.room_code,
            "session_token": player.session_token,
            "nickname": player.nickname,
            "role": player.role,
        }

    @staticmethod
    def get_room_state(room_code: str, viewer_token: str) -> dict:
        """ดึง state ของห้องทั้งหมด — กรอง visibility ตาม role"""
        room = Room.get_by_code(room_code)
        if not room:
            return {"success": False, "error": "ไม่พบห้อง"}

        viewer = Player.get_by_token(viewer_token)
        if not viewer:
            return {"success": False, "error": "session ไม่ถูกต้อง"}

        current_round = Round.get_current_round(room_code)
        round_id = current_round.id if current_round else None

        players = Player.get_room_players(room_code)
        all_hands = Hand.objects(round_id=round_id) if round_id else []

        # สร้าง dict ของ hand ตาม player_token
        hand_map = {str(h.player_token): h for h in all_hands}
        dealer_hand = next((h for h in all_hands if h.role == "dealer"), None)

        players_data = []
        for p in players:
            h = hand_map.get(p.session_token)
            is_self = p.session_token == viewer_token

            # ผู้เล่นทั่วไปเห็นทุกคน, อาจารย์เห็นแค่ตัวเอง
            can_see = viewer.role == "player" or is_self

            players_data.append({
                "nickname": p.nickname,
                "token": p.session_token,
                "role": p.role,
                "is_self": is_self,
                "hand": h.to_dict(visible=can_see) if h else None,
            })

        return {
            "success": True,
            "room": room.to_dict(),
            "viewer_role": viewer.role,
            "viewer_nickname": viewer.nickname,
            "round": current_round.to_dict() if current_round else None,
            "players": players_data,
            "dealer_hand": dealer_hand.to_dict(visible=True) if dealer_hand else None,
        }
