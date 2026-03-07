"""
Lobby view — สร้างและเข้าห้อง
Routes:
  GET  /           → lobby form
  POST /room/create → สร้างห้องใหม่
  POST /room/join   → เข้าห้อง
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from ...services.room_service import RoomService

module = Blueprint("lobby", __name__, url_prefix="/")


@module.route("/", methods=["GET"])
def index():
    return render_template("lobby/lobby.html")


@module.route("/room/create", methods=["POST"])
def create_room():
    nickname = request.form.get("nickname", "").strip()
    role = request.form.get("role", "player")

    if not nickname:
        flash("กรุณากรอกชื่อเล่น", "error")
        return redirect(url_for("lobby.index"))

    # สร้างห้องก่อน
    room_result = RoomService.create_room()
    room_code = room_result["room_code"]

    # เข้าห้องในฐานะ creator
    join_result = RoomService.join_room(room_code, nickname, role)
    if not join_result["success"]:
        flash(join_result["error"], "error")
        return redirect(url_for("lobby.index"))

    session["session_token"] = join_result["session_token"]
    session["room_code"] = room_code
    session["nickname"] = join_result["nickname"]
    session["role"] = join_result["role"]

    return redirect(url_for("game.game_board", room_code=room_code))


@module.route("/room/join", methods=["POST"])
def join_room():
    nickname = request.form.get("nickname", "").strip()
    role = request.form.get("role", "player")
    room_code = request.form.get("room_code", "").strip().upper()

    if not nickname or not room_code:
        flash("กรุณากรอกชื่อเล่นและรหัสห้อง", "error")
        return redirect(url_for("lobby.index"))

    result = RoomService.join_room(room_code, nickname, role)
    if not result["success"]:
        flash(result["error"], "error")
        return redirect(url_for("lobby.index"))

    session["session_token"] = result["session_token"]
    session["room_code"] = room_code
    session["nickname"] = result["nickname"]
    session["role"] = result["role"]

    return redirect(url_for("game.game_board", room_code=room_code))
