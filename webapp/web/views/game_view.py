"""
Game view — game board (player / teacher)
Routes:
  GET  /game/<room_code>          → game board
  POST /game/<room_code>/round/start  → start round (teacher only)
  POST /game/<room_code>/round/end    → end round (teacher only)
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

from ...services.room_service import RoomService
from ...services.round_service import RoundService
from ...services.hand_service import HandService
from ...services.strategy_service import get_advice
from ...models.player_model import Player
from ...models.round_model import Round
from ...models.hand_model import Hand

module = Blueprint("game", __name__, url_prefix="/game")


def _require_session():
    """ตรวจสอบ session — คืน (token, room_code) หรือ None"""
    token = session.get("session_token")
    room_code = session.get("room_code")
    if not token or not room_code:
        return None, None
    return token, room_code


@module.route("/<room_code>", methods=["GET"])
def game_board(room_code: str):
    token, _ = _require_session()
    if not token:
        flash("กรุณาเข้าห้องก่อน", "error")
        return redirect(url_for("lobby.index"))

    state = RoomService.get_room_state(room_code, token)
    if not state["success"]:
        flash(state["error"], "error")
        return redirect(url_for("lobby.index"))

    # operator and teacher both get the teacher/management template
    role = state.get("viewer_role", "player")
    template = (
        "game/game_teacher.html"
        if role in ("teacher", "operator")
        else "game/game_player.html"
    )
    return render_template(template, **state, room_code=room_code, token=token)


@module.route("/<room_code>/round/start", methods=["POST"])
def start_round(room_code: str):
    token, _ = _require_session()
    if not token:
        return jsonify({"success": False, "error": "ไม่มี session"}), 401

    player = Player.get_by_token(token)
    if not player or player.role != "teacher":
        return jsonify({"success": False, "error": "เฉพาะอาจารย์เท่านั้น"}), 403

    result = RoundService.start_round(room_code, dealer_nickname=player.nickname)
    return jsonify(result)


@module.route("/<room_code>/round/end", methods=["POST"])
def end_round(room_code: str):
    token, _ = _require_session()
    if not token:
        return jsonify({"success": False, "error": "ไม่มี session"}), 401

    player = Player.get_by_token(token)
    if not player or player.role != "teacher":
        return jsonify({"success": False, "error": "เฉพาะอาจารย์เท่านั้น"}), 403

    result = RoundService.end_round(room_code)
    return jsonify(result)


@module.route("/<room_code>/advice", methods=["GET"])
def get_player_advice(room_code: str):
    """REST endpoint ขอ advice (fallback จาก Socket.IO)"""
    token, _ = _require_session()
    if not token:
        return jsonify({"error": "ไม่มี session"}), 401

    player = Player.get_by_token(token)
    if not player or player.role != "player":
        return jsonify({"error": "เฉพาะผู้เล่นทั่วไป"}), 403

    current_round = Round.get_current_round(room_code)
    if not current_round:
        return jsonify({"error": "ยังไม่มีรอบ"}), 404

    player_hand = Hand.objects(round_id=current_round.id, player_token=token).first()
    dealer_hand = HandService.get_dealer_hand(current_round.id)

    player_cards = [c.to_dict() for c in player_hand.cards] if player_hand else []
    dealer_upcard = dealer_hand.cards[0].rank if (dealer_hand and dealer_hand.cards) else None

    all_hands = Hand.objects(round_id=current_round.id)
    all_visible = []
    for h in all_hands:
        for c in h.cards:
            all_visible.append({"rank": c.rank, "suit": c.suit})

    advice = get_advice(player_cards, dealer_upcard, all_visible)
    return jsonify(advice)
