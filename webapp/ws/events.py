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


@socketio.on("card_add")
def on_card_add(data):
    """ผู้เล่นเพิ่มไพ่ตัวเอง"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")
    rank = data.get("rank", "")
    suit = data.get("suit", "")

    result = HandService.add_card_to_player(room_code, session_token, rank, suit)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    # broadcast ให้ทุกคนในห้อง
    socketio.emit(
        "hand_updated",
        {
            "player_token": session_token,
            "nickname": result["nickname"],
            "role": result["role"],
            "hand": result["hand"],
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

    # ตรวจสอบว่าเป็น teacher
    player = Player.get_by_token(session_token)
    if not player or player.role != "teacher":
        emit("error", {"message": "เฉพาะอาจารย์เท่านั้นที่กรอกไพ่กองกลางได้"})
        return

    result = HandService.add_card_to_dealer(room_code, rank, suit)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    socketio.emit("dealer_updated", {"hand": result["hand"]}, room=room_code)


@socketio.on("advice_request")
def on_advice_request(data):
    """ผู้เล่นขอ advice — ส่งกลับเฉพาะคนนั้น"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")

    player = Player.get_by_token(session_token)
    if not player or player.role != "player":
        emit("error", {"message": "เฉพาะผู้เล่นทั่วไปเท่านั้น"})
        return

    current_round = Round.get_current_round(room_code)
    if not current_round:
        emit("advice_response", {"error": "ยังไม่มีรอบที่กำลังเล่น"})
        return

    player_hand = Hand.objects(
        round_id=current_round.id, player_token=session_token
    ).first()
    dealer_hand = HandService.get_dealer_hand(current_round.id)

    player_cards = [c.to_dict() for c in player_hand.cards] if player_hand else []
    dealer_upcard = dealer_hand.cards[0].rank if (dealer_hand and dealer_hand.cards) else None
    all_visible = _get_all_visible_cards(current_round.id)

    advice = get_advice(player_cards, dealer_upcard, all_visible)
    emit("advice_response", advice)


@socketio.on("round_start")
def on_round_start(data):
    """อาจารย์เริ่มรอบใหม่"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")

    player = Player.get_by_token(session_token)
    if not player or player.role != "teacher":
        emit("error", {"message": "เฉพาะอาจารย์เท่านั้นที่เริ่มรอบได้"})
        return

    result = RoundService.start_round(room_code, dealer_nickname=player.nickname)
    socketio.emit("round_started", result["round"], room=room_code)


@socketio.on("round_end")
def on_round_end(data):
    """อาจารย์จบรอบ"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")

    player = Player.get_by_token(session_token)
    if not player or player.role != "teacher":
        emit("error", {"message": "เฉพาะอาจารย์เท่านั้นที่จบรอบได้"})
        return

    result = RoundService.end_round(room_code)
    socketio.emit("round_ended", result, room=room_code)


@socketio.on("undo_card")
def on_undo_card(data):
    """ลบไพ่ใบล่าสุด"""
    room_code = data.get("room_code", "").upper()
    session_token = data.get("session_token", "")

    result = HandService.undo_last_card(room_code, session_token)
    if not result["success"]:
        emit("error", {"message": result["error"]})
        return

    socketio.emit(
        "hand_updated",
        {"player_token": session_token, "hand": result["hand"]},
        room=room_code,
    )
