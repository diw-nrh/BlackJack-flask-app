"""
Strategy Service — Blackjack AI Advisor
ใช้ Basic Strategy + Hi-Lo Card Counting เพื่อแนะนำผู้เล่นทั่วไป
"""

# -------------------------------------------------------
# Hi-Lo Card Counting values
# -------------------------------------------------------
HI_LO_COUNT = {
    "2": 1, "3": 1, "4": 1, "5": 1, "6": 1,
    "7": 0, "8": 0, "9": 0,
    "10": -1, "J": -1, "Q": -1, "K": -1, "A": -1,
}

# -------------------------------------------------------
# Basic Strategy: (player_score, is_soft) → dealer_upcard_group → action
# - dealer group "weak" = 2-6, "strong" = 7-A
# -------------------------------------------------------
ACTION_HIT = "HIT"
ACTION_STAND = "STAND"
ACTION_DOUBLE = "DOUBLE"
ACTION_SPLIT = "SPLIT"


def _dealer_group(dealer_upcard: str) -> str:
    """จัดกลุ่มไพ่เจ้ามือ: weak (2-6) หรือ strong (7-A)"""
    weak = {"2", "3", "4", "5", "6"}
    return "weak" if dealer_upcard in weak else "strong"


def _basic_strategy(player_score: int, is_soft: bool, dealer_upcard: str, cards: list) -> tuple[str, int]:
    """
    คืนค่า (action, base_confidence)
    is_soft = มี Ace นับเป็น 11 (soft hand)
    cards = list of card dicts
    """
    group = _dealer_group(dealer_upcard)
    can_double_or_split = len(cards) == 2
    
    def _rank_val(r):
        return 10 if r in ["J", "Q", "K"] else (11 if r == "A" else int(r))

    # Split Logic
    if can_double_or_split:
        r1, r2 = cards[0]["rank"], cards[1]["rank"]
        # Allow splitting 10-value cards as equivalent (though standard strategy says never split 10s)
        if _rank_val(r1) == _rank_val(r2):
            val = _rank_val(r1)
            # Always split A and 8
            if val == 11 or val == 8:
                return ACTION_SPLIT, 95
            # Never split 10 and 5
            elif val == 10 or val == 5:
                pass
            # 9 split vs 2-9 except 7
            elif val == 9 and dealer_upcard in ["2", "3", "4", "5", "6", "8", "9"]:
                return ACTION_SPLIT, 80
            # 7 split vs 2-7
            elif val == 7 and dealer_upcard in ["2", "3", "4", "5", "6", "7"]:
                return ACTION_SPLIT, 80
            # 6 split vs 2-6
            elif val == 6 and dealer_upcard in ["2", "3", "4", "5", "6"]:
                return ACTION_SPLIT, 75
            # 4 split vs 5, 6
            elif val == 4 and dealer_upcard in ["5", "6"]:
                return ACTION_SPLIT, 70
            # 2, 3 split vs 2-7
            elif val in [2, 3] and dealer_upcard in ["2", "3", "4", "5", "6", "7"]:
                return ACTION_SPLIT, 75

    # Double Down Logic
    if can_double_or_split:
        if not is_soft:
            if player_score == 11:
                return ACTION_DOUBLE, 90
            if player_score == 10 and dealer_upcard in ["2", "3", "4", "5", "6", "7", "8", "9"]:
                return ACTION_DOUBLE, 85
            if player_score == 9 and dealer_upcard in ["3", "4", "5", "6"]:
                return ACTION_DOUBLE, 80
        else:
            if player_score in [13, 14] and dealer_upcard in ["5", "6"]: return ACTION_DOUBLE, 75
            if player_score in [15, 16] and dealer_upcard in ["4", "5", "6"]: return ACTION_DOUBLE, 75
            if player_score == 17 and dealer_upcard in ["3", "4", "5", "6"]: return ACTION_DOUBLE, 80
            if player_score == 18 and dealer_upcard in ["2", "3", "4", "5", "6"]: return ACTION_DOUBLE, 80

    # Normal Stand/Hit Logic
    # Blackjack/21 is checked in get_advice directly, but as fallback:
    if player_score >= 21:
        return ACTION_STAND, 100

    # Soft hands
    if is_soft:
        if player_score >= 19:
            return ACTION_STAND, 90
        if player_score == 18:
            return ACTION_STAND if group == "weak" else ACTION_HIT, 75
        return ACTION_HIT, 65

    # Hard hands
    if player_score >= 17:
        return ACTION_STAND, 85
    if player_score >= 13:
        return ACTION_STAND if group == "weak" else ACTION_HIT, 70
    if player_score == 12:
        return ACTION_STAND if dealer_upcard in ["4", "5", "6"] else ACTION_HIT, 60
    return ACTION_HIT, 55


def _is_soft_hand(cards: list) -> bool:
    """ตรวจสอบว่าเป็น soft hand (Ace นับ 11 โดยไม่ bust)"""
    total = sum(11 if c["rank"] == "A" else (10 if c["rank"] in {"J", "Q", "K"} else int(c["rank"])) for c in cards)
    has_ace = any(c["rank"] == "A" for c in cards)
    return has_ace and total <= 21


def _calculate_running_count(all_visible_cards: list) -> int:
    """คำนวณ running count จากไพ่ที่เห็นทั้งหมด"""
    return sum(HI_LO_COUNT.get(c["rank"], 0) for c in all_visible_cards)


def _estimate_true_count(running_count: int, cards_seen: int) -> float:
    """ประมาณ true count — สมมติใช้ 6 สำรับ"""
    total_cards = 6 * 52
    decks_remaining = max((total_cards - cards_seen) / 52, 0.5)
    return round(running_count / decks_remaining, 1)


def _win_probability(action: str, player_score: int, dealer_upcard: str, true_count: float, cards: list) -> int:
    """
    ประมาณ % โอกาสชนะ
    """
    if player_score > 21: return 0

    dealer_bust = {
        "2": 35, "3": 37, "4": 40, "5": 42, "6": 42,
        "7": 26, "8": 24, "9": 23, "10": 20, "J": 20, "Q": 20, "K": 20, "A": 17,
    }
    bust_chance = dealer_bust.get(dealer_upcard, 25)

    if player_score == 21:
        base = 92 if dealer_upcard in ["10", "J", "Q", "K", "A"] else 98
    elif player_score == 20:
        base = 85 if dealer_upcard in ["10", "J", "Q", "K", "A"] else 90
    elif player_score == 19:
        base = 75 if dealer_upcard in ["10", "J", "Q", "K", "A"] else 80
    elif player_score == 18:
        base = 60 if dealer_upcard in ["9", "10", "J", "Q", "K", "A"] else 70
    elif player_score == 17:
        base = 45 if dealer_upcard in ["9", "10", "J", "Q", "K", "A"] else 55
    else:
        base = bust_chance

    # ปรับตาม true count
    count_bonus = true_count * 0.5
    final_prob = int(base + count_bonus)

    return max(0, min(100, final_prob))


def _count_adjustment_reason(true_count: float) -> str:
    if true_count >= 3:
        return f"deck มีไพ่ใหญ่เหลือมาก (count: +{true_count:.1f})"
    if true_count <= -3:
        return f"deck มีไพ่เล็กเหลือมาก (count: {true_count:.1f})"
    return ""


def _dealer_group_reason(dealer_upcard: str) -> str:
    weak = {"2", "3", "4", "5", "6"}
    return "เจ้ามือมีไพ่อ่อน" if dealer_upcard in weak else "เจ้ามือมีไพ่แข็ง"


def get_advice(player_cards: list, dealer_upcard: str | None, true_count: float = 0.0) -> dict:
    """
    Main advisor function

    Args:
        player_cards: list of {"rank": "K", "suit": "spades"}
        dealer_upcard: rank ของไพ่เจ้ามือที่เห็น (None ถ้ายังไม่รู้)
        true_count: True Count จริงจากเกม

    Returns:
        dict พร้อม action, confidence, win_probability, reason
    """
    if not player_cards:
        effective_upcard = dealer_upcard if dealer_upcard else "7"
        group = _dealer_group(effective_upcard)
        base = 48 if group == "weak" else 42
        final_prob = max(0, min(100, int(base + (true_count * 0.5))))

        return {
            "action": ACTION_HIT,
            "confidence": 0,
            "win_probability": final_prob,
            "reason": "กรุณากรอกไพ่ในมือก่อน",
            "player_score": 0,
            "dealer_upcard": dealer_upcard,
            "true_count": true_count,
        }

    # คำนวณ player score
    from ..models.hand_model import calculate_score
    from ..models.hand_model import Card as CardModel

    # สร้าง Card objects ชั่วคราวเพื่อใช้ calculate_score
    class _TmpCard:
        def __init__(self, rank):
            self.rank = rank

    tmp_cards = [_TmpCard(c["rank"]) for c in player_cards]
    player_score = calculate_score(tmp_cards)
    is_soft = _is_soft_hand(player_cards)

    # ถ้าไม่รู้ไพ่เจ้ามือ ใช้ "7" เป็น worst-case neutral
    effective_upcard = dealer_upcard if dealer_upcard else "7"

    # Bust / 21
    if player_score > 21:
        return {
            "action": "BUST",
            "confidence": 100,
            "win_probability": 0,
            "reason": f"คะแนนรวม {player_score} — bust แล้ว!",
            "player_score": player_score,
            "dealer_upcard": dealer_upcard,
            "true_count": 0.0,
        }
    if player_score == 21:
        is_blackjack = len(player_cards) == 2
        return {
            "action": "BLACKJACK" if is_blackjack else "STAND",
            "confidence": 100,
            "win_probability": 99 if is_blackjack else 95,
            "reason": "ได้แบล็คแจ็ค!" if is_blackjack else f"คะแนนรวม 21 — ยืนอยู่",
            "player_score": player_score,
            "dealer_upcard": dealer_upcard,
            "true_count": true_count,
        }

    # Basic strategy
    action, base_confidence = _basic_strategy(player_score, is_soft, effective_upcard, player_cards)
    reason_prefix = ""

    # ปรับ action ตาม count (Illustrious 18)
    if not is_soft:
        if player_score == 16 and effective_upcard in ["9", "10", "A"] and true_count >= 0:
            if action == ACTION_HIT:
                action = ACTION_STAND
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 85
        elif player_score == 15 and effective_upcard == "10" and true_count >= 4:
            if action == ACTION_HIT:
                action = ACTION_STAND
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 80
        elif player_score == 12 and effective_upcard == "3" and true_count >= 2:
            if action == ACTION_HIT:
                action = ACTION_STAND
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 75
        elif player_score == 12 and effective_upcard == "2" and true_count >= 3:
            if action == ACTION_HIT:
                action = ACTION_STAND
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 75
        elif player_score == 11 and effective_upcard == "A" and true_count >= 1:
            if action != ACTION_DOUBLE:
                action = ACTION_DOUBLE
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 90
        elif player_score == 10 and effective_upcard in ["10", "A"] and true_count >= 4:
            if action != ACTION_DOUBLE:
                action = ACTION_DOUBLE
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 85
        elif player_score == 9 and effective_upcard == "2" and true_count >= 1:
            if action != ACTION_DOUBLE:
                action = ACTION_DOUBLE
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 80
        elif player_score == 9 and effective_upcard == "7" and true_count >= 3:
            if action != ACTION_DOUBLE:
                action = ACTION_DOUBLE
                reason_prefix = f"[Deviation applied due to True Count {true_count}] "
                base_confidence = 80

    win_prob = _win_probability(action, player_score, effective_upcard, true_count, player_cards)

    # สร้างเหตุผล
    reasons = []
    if reason_prefix:
        reasons.append(reason_prefix.strip())
    soft_label = " (soft)" if is_soft else ""
    reasons.append(f"คะแนนของคุณ: {player_score}{soft_label}")
    if dealer_upcard:
        reasons.append(f"{_dealer_group_reason(effective_upcard)} ({effective_upcard})")
    else:
        reasons.append("ยังไม่ทราบไพ่เจ้ามือ")

    return {
        "action": action,
        "confidence": base_confidence,
        "win_probability": win_prob,
        "reason": " — ".join(reasons),
        "player_score": player_score,
        "is_soft": is_soft,
        "dealer_upcard": dealer_upcard,
        "true_count": true_count,
    }
