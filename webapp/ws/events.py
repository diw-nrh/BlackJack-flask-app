"""
Socket.IO Event Handlers
- join_room_ws   : ผู้เล่นเข้าร่วม room channel
- card_add       : เพิ่มไพ่ผู้เล่น → broadcast hand:updated
- dealer_add     : เพิ่มไพ่เจ้ามือ → broadcast dealer:updated
- advice_request : ขอ advice → emit กลับเฉพาะผู้ขอ
- round_start    : เริ่มรอบใหม่ → broadcast round:started
- round_end      : จบรอบ → broadcast round:ended
"""
from flask_socketio import join_room, emit
from . import socketio
from ..services.hand_service import HandService
from ..services.round_service import RoundService
from ..services.room_service import RoomService
from ..services.strategy_service import get_advice
from ..models.player_model import Player
from ..models.round_model import Round
from ..models.hand_model import Hand


def _get_all_visible_cards(round_id) -> list:
    """รวบรวมไพ่ทั้งหมดในรอบสำหรับ card counting"""
    all_hands = Hand.objects(round_id=round_id)
    cards = []
    for hand in all_hands:
        for c in hand.cards:
            cards.append({"rank": c.rank, "suit": c.suit})
    return cards


@socketio.on("join_room_ws")
def on_join_room(data):
    """ผู้เล่นเข้า Socket.IO room channel"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    player = Player.get_by_token(session_token)
    if not player or player.room_code != room_code:
        emit("error", {"message": "session ไม่ถูกต้อง"})
        return
    join_room(room_code)
    emit("joined", {"room_code": room_code, "nickname": player.nickname, "role": player.role})
    # operator is invisible — don't broadcast their presence to player list
    if player.role in ("operator", "teacher"):
        return
    # Broadcast to room so others can update their player list in real-time
    socketio.emit(
        "player_joined",
        {"token": player.session_token, "nickname": player.nickname, "role": player.role},
        room=room_code,
    )


@socketio.on("card_add")
def on_card_add(data):
    """ผู้เล่นเพิ่มไพ่ตัวเอง"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    target_token = data.get("target_token", session_token)
    hand_id = data.get("hand_id", None)  # for targeting a specific split hand
    rank = data.get("rank", "")
    suit = data.get("suit", "")

    result = HandService.add_card_to_player(room_code, target_token, rank, suit, hand_id=hand_id)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    # broadcast ให้ทุกคนในห้อง
    socketio.emit(
        "hand_updated",
        {
            "player_token": target_token,
            "hand_id": result["hand"]["id"],
            "hand_index": result["hand"]["hand_index"],
            "hand": result["hand"],
            "card": result["card"],
            "nickname": result["nickname"],
            "role": result["role"],
        },
        room=room_code,
    )


@socketio.on("dealer_add")
def on_dealer_add(data):
    """อาจารย์เพิ่มไพ่กองกลาง"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    rank = data.get("rank", "")
    suit = data.get("suit", "")

    # Allow any authenticated player to add dealer cards (not teacher-only)
    player = Player.get_by_token(session_token)
    if not player:
        emit("error", {"message": "เซสชั่นไม่ถูกต้อง"})
        return

    result = HandService.add_card_to_dealer(room_code, rank, suit)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    socketio.emit("dealer_updated", {"hand": result["hand"]}, room=room_code)


@socketio.on("advice_request")
def on_advice_request(data):
    """ขอ advice — ทุกคนในห้องทำได้ ระบุ target_token เพื่อดู advice ของมือที่เลือก"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    target_token = data.get("target_token") or session_token  # default: own hand

    caller = Player.get_by_token(session_token)
    if not caller:
        emit("error", {"message": "session ไม่ถูกต้อง"})
        return

    current_round = Round.get_current_round(room_code)
    if not current_round:
        emit("advice_response", {"error": "ยังไม่มีรอบที่กำลังเล่น"})
        return

    player_hand = Hand.objects(
        round_id=current_round.id, player_token=target_token
    ).first()
    dealer_hand = HandService.get_dealer_hand(current_round.id)

    player_cards = [c.to_dict() for c in player_hand.cards] if player_hand else []
    dealer_upcard = dealer_hand.cards[0].rank if (dealer_hand and dealer_hand.cards) else None
    all_visible = _get_all_visible_cards(current_round.id)

    advice = get_advice(player_cards, dealer_upcard, all_visible)
    emit("advice_response", advice)


@socketio.on("round_start")
def on_round_start(data):
    """เริ่มรอบใหม่ — ทุกคนในห้องทำได้"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")

    player = Player.get_by_token(session_token)
    if not player:
        emit("error", {"message": "session ไม่ถูกต้อง"})
        return

    result = RoundService.start_round(room_code, dealer_nickname="เจ้ามือ")
    socketio.emit("round_started", result["round"], room=room_code)


@socketio.on("round_end")
def on_round_end(data):
    """จบรอบ — ทุกคนในห้องทำได้"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")

    player = Player.get_by_token(session_token)
    if not player:
        emit("error", {"message": "session ไม่ถูกต้อง"})
        return

    result = RoundService.end_round(room_code)
    socketio.emit("round_ended", result, room=room_code)


@socketio.on("undo_card")
def on_undo_card(data):
    """ลบไพ่ใบล่าสุด"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    target_token = data.get("target_token", session_token)
    hand_id = data.get("hand_id", None)

    result = HandService.undo_last_card(room_code, target_token, hand_id=hand_id)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    socketio.emit(
        "hand_updated",
        {"player_token": target_token, "hand_id": result["hand"]["id"], "hand_index": result["hand"]["hand_index"], "hand": result["hand"]},
        room=room_code,
    )


@socketio.on("split_hand")
def on_split_hand(data):
    """สร้าง split hand ใหม่ให้ผู้เล่น"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    target_token = data.get("target_token", session_token)

    result = HandService.split_hand(room_code, target_token)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    # Broadcast the new split hand to everyone
    socketio.emit(
        "hand_split",
        {
            "player_token": target_token,
            "nickname": result["nickname"],
            "role": result["role"],
            "new_hand": result["hand"],
            "all_hands": result["all_hands"],
        },
        room=room_code,
    )


@socketio.on("delete_hand")
def on_delete_hand(data):
    """ลบมือ (split hand) ออก"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    hand_id = data.get("hand_id", "")

    player = Player.get_by_token(session_token)
    if not player:
        emit("error", {"message": "session ไม่ถูกต้อง"})
        return

    result = HandService.delete_hand(room_code, hand_id)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    socketio.emit(
        "hand_deleted",
        {
            "player_token": result["player_token"],
            "deleted_hand_id": hand_id,
            "remaining_hands": result["remaining_hands"],
        },
        room=room_code,
    )


@socketio.on("kick_player")
def on_kick_player(data):
    """ลบผู้เล่นออกจากห้อง"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    target_token = data.get("target_token", "")

    result = RoomService.kick_player(room_code, target_token)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    socketio.emit(
        "player_kicked",
        {"token": target_token, "nickname": result["nickname"]},
        room=room_code,
    )


@socketio.on("rename_player")
def on_rename_player(data):
    """เปลี่ยนชื่อผู้เล่น — ใช้ target_token เพื่อให้ teacher เปลี่ยนชื่อผู้อื่นได้"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    target_token = data.get("target_token", session_token)  # default: rename self
    new_nickname = data.get("nickname", "").strip()

    if not new_nickname:
        emit("error", {"message": "กรุณากรอกชื่อ"})
        return

    result = RoomService.rename_player(target_token, new_nickname)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    socketio.emit(
        "player_renamed",
        {"token": target_token, "nickname": result["nickname"]},
        room=room_code,
    )


@socketio.on("add_player")
def on_add_player(data):
    """เพิ่มผู้เล่นใหม่จากในห้อง — ทุกคนทำได้"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    nickname = data.get("nickname", "").strip()
    role = data.get("role", "player")

    # Validate caller
    caller = Player.get_by_token(session_token)
    if not caller:
        emit("error", {"message": "session ไม่ถูกต้อง"})
        return

    if not nickname:
        # Auto-assign nickname
        from ..models.player_model import Player as PlayerModel
        count = PlayerModel.objects(room_code=room_code).count()
        nickname = f"ดีลเลอร์" if role == "dealer" else f"ผู้เล่น {count + 1}"

    # Enforce single dealer rule
    if role == "dealer":
        existing_dealer = Player.objects(room_code=room_code, role="dealer", is_active=True).first()
        if existing_dealer:
            emit("error", {"message": "ห้องนี้มีดีลเลอร์แล้ว"})
            return

    result = RoomService.join_room(room_code, nickname, role)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    new_token = result["session_token"]
    socketio.emit(
        "player_joined",
        {"token": new_token, "nickname": result["nickname"], "role": role},
        room=room_code,
    )
