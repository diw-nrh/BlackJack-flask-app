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


def _dealer_group(dealer_upcard: str) -> str:
    """จัดกลุ่มไพ่เจ้ามือ: weak (2-6) หรือ strong (7-A)"""
    weak = {"2", "3", "4", "5", "6"}
    return "weak" if dealer_upcard in weak else "strong"


def _basic_strategy(player_score: int, is_soft: bool, dealer_upcard: str) -> tuple[str, int]:
    """
    คืนค่า (action, base_confidence)
    is_soft = มี Ace นับเป็น 11 (soft hand)
    """
    group = _dealer_group(dealer_upcard)

    # Blackjack
    if player_score == 21:
        return ACTION_STAND, 99

    # Soft hands (มี Ace = 11)
    if is_soft:
        if player_score >= 19:
            return ACTION_STAND, 90
        if player_score == 18:
            return ACTION_DOUBLE if group == "weak" else ACTION_HIT, 75
        if player_score == 17:
            return ACTION_DOUBLE if group == "weak" else ACTION_HIT, 70
        return ACTION_HIT, 65

    # Hard hands
    if player_score >= 17:
        return ACTION_STAND, 85
    if player_score >= 13:
        return ACTION_STAND if group == "weak" else ACTION_HIT, 70
    if player_score == 12:
        return ACTION_STAND if group == "weak" else ACTION_HIT, 60
    if player_score == 11:
        return ACTION_DOUBLE, 88
    if player_score == 10:
        return ACTION_DOUBLE if group == "weak" else ACTION_HIT, 80
    if player_score == 9:
        return ACTION_DOUBLE if group == "weak" else ACTION_HIT, 70
    # ≤ 8
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


def _win_probability(action: str, player_score: int, dealer_upcard: str, true_count: float) -> int:
    """
    ประมาณ % โอกาสชนะ จาก basic strategy odds + count adjustment
    ตัวเลขอิง empirical blackjack probability tables
    """
    # Base win % จาก dealer upcard
    dealer_base = {
        "2": 64, "3": 66, "4": 68, "5": 71, "6": 73,  # weak dealer
        "7": 57, "8": 55, "9": 52, "10": 48, "J": 48, "Q": 48, "K": 48, "A": 45,
    }
    base = dealer_base.get(dealer_upcard, 50)

    # ปรับตาม player score
    if player_score >= 20:
        base += 20
    elif player_score >= 18:
        base += 10
    elif player_score >= 17:
        base += 5
    elif player_score <= 11:
        base -= 5

    # ปรับตาม true count
    count_bonus = int(true_count * 2)
    base += count_bonus

    # ปรับตาม action
    if action == ACTION_DOUBLE:
        base += 5
    elif action == ACTION_STAND and player_score <= 14:
        base -= 10

    return max(10, min(95, base))


def _count_adjustment_reason(true_count: float) -> str:
    if true_count >= 3:
        return f"deck มีไพ่ใหญ่เหลือมาก (count: +{true_count:.1f})"
    if true_count <= -3:
        return f"deck มีไพ่เล็กเหลือมาก (count: {true_count:.1f})"
    return ""


def _dealer_group_reason(dealer_upcard: str) -> str:
    weak = {"2", "3", "4", "5", "6"}
    return "เจ้ามือมีไพ่อ่อน" if dealer_upcard in weak else "เจ้ามือมีไพ่แข็ง"


def get_advice(player_cards: list, dealer_upcard: str | None, all_visible_cards: list) -> dict:
    """
    Main advisor function

    Args:
        player_cards: list of {"rank": "K", "suit": "spades"}
        dealer_upcard: rank ของไพ่เจ้ามือที่เห็น (None ถ้ายังไม่รู้)
        all_visible_cards: ไพ่ทุกใบที่เห็นในรอบนี้ (สำหรับ counting)

    Returns:
        dict พร้อม action, confidence, win_probability, reason
    """
    if not player_cards:
        return {
            "action": ACTION_HIT,
            "confidence": 0,
            "win_probability": 0,
            "reason": "กรุณากรอกไพ่ในมือก่อน",
            "player_score": 0,
            "dealer_upcard": dealer_upcard,
            "true_count": 0.0,
            "running_count": 0,
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

    # Bust แล้ว
    if player_score > 21:
        return {
            "action": "BUST",
            "confidence": 100,
            "win_probability": 0,
            "reason": f"คะแนนรวม {player_score} — bust แล้ว!",
            "player_score": player_score,
            "dealer_upcard": dealer_upcard,
            "true_count": 0.0,
            "running_count": 0,
        }

    # Hi-Lo counting
    running_count = _calculate_running_count(all_visible_cards)
    true_count = _estimate_true_count(running_count, len(all_visible_cards))

    # Basic strategy
    action, base_confidence = _basic_strategy(player_score, is_soft, effective_upcard)

    # ปรับ action ตาม count
    if true_count >= 3 and action == ACTION_HIT and player_score >= 9:
        action = ACTION_DOUBLE
        base_confidence = min(base_confidence + 8, 95)
    elif true_count <= -3 and action == ACTION_DOUBLE:
        action = ACTION_HIT
        base_confidence = max(base_confidence - 5, 50)

    win_prob = _win_probability(action, player_score, effective_upcard, true_count)

    # สร้างเหตุผล
    reasons = []
    soft_label = " (soft)" if is_soft else ""
    reasons.append(f"คะแนนของคุณ: {player_score}{soft_label}")
    if dealer_upcard:
        reasons.append(f"{_dealer_group_reason(effective_upcard)} ({effective_upcard})")
    else:
        reasons.append("ยังไม่ทราบไพ่เจ้ามือ")

    count_reason = _count_adjustment_reason(true_count)
    if count_reason:
        reasons.append(count_reason)

    return {
        "action": action,
        "confidence": base_confidence,
        "win_probability": win_prob,
        "reason": " — ".join(reasons),
        "player_score": player_score,
        "is_soft": is_soft,
        "dealer_upcard": dealer_upcard,
        "true_count": true_count,
        "running_count": running_count,
    }
