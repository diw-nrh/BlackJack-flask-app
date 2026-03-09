/**
 * BlackJack Advisor — Client-Side JavaScript
 * Socket.IO client for real-time card updates + advice
 */
const BlackJack = (() => {
    let socket;
    let config = {};
    let selectedRank = null;
    let selectedSuit = null;

    // ───────────────────────────────────────────────
    // INIT
    // ───────────────────────────────────────────────
    function init(cfg) {
        config = cfg;
        socket = io({ transports: ['websocket'] });

        // Connection events
        socket.on('connect', () => {
            setConnected(true);
            socket.emit('join_room_ws', {
                room_code: config.roomCode,
                session_token: config.token,
            });

            // Trigger initial advice fetch for the player automatically upon joining
            setTimeout(() => {
                triggerAdviceIfPlayer();
            }, 200);
        });
        socket.on('disconnect', () => setConnected(false));
        socket.on('error', (data) => showToast(data.message, 'error'));

        // Game events
        socket.on('hand_updated', onHandUpdated);
        socket.on('dealer_updated', onDealerUpdated);
        socket.on('advice_response', onAdviceResponse);
        socket.on('round_started', onRoundStarted);
        socket.on('round_ended', onRoundEnded);

        if (config.role === 'player') {
            initPlayerUI();
        } else {
            initTeacherUI();
        }

        // Global Game Controls
        document.getElementById('btn-start-round')?.addEventListener('click', () => {
            if (confirm('คุณต้องการเริ่มรอบใหม่ใช่หรือไม่?\\nไพ่บนโต๊ะทั้งหมดจะถูกล้างทิ้ง')) {
                socket.emit('round_start', {
                    room_code: config.roomCode,
                    session_token: config.token,
                });
            }
        });
    }

    // ───────────────────────────────────────────────
    // PLAYER UI
    // ───────────────────────────────────────────────
    function initPlayerUI() {
        setupCardSelector('rank-grid', 'suit-grid', 'btn-add-card', (rank, suit) => {
            socket.emit('card_add', {
                room_code: config.roomCode,
                session_token: config.token,
                rank, suit,
            });
        });

        document.getElementById('btn-undo')?.addEventListener('click', () => {
            socket.emit('undo_card', {
                room_code: config.roomCode,
                session_token: config.token,
            });
        });

    }

    // ───────────────────────────────────────────────
    // TEACHER UI
    // ───────────────────────────────────────────────
    function initTeacherUI() {
        // My cards
        setupCardSelector('rank-grid-my', 'suit-grid-my', 'btn-add-my-card', (rank, suit) => {
            socket.emit('card_add', {
                room_code: config.roomCode,
                session_token: config.token,
                rank, suit,
            });
        });

        document.getElementById('btn-undo-my')?.addEventListener('click', () => {
            socket.emit('undo_card', {
                room_code: config.roomCode,
                session_token: config.token,
            });
        });

        // Dealer cards
        let selectedDealerRank = null;
        let selectedDealerSuit = null;
        const btnAddDealer = document.getElementById('btn-add-dealer-card');

        document.getElementById('rank-grid-dealer')?.querySelectorAll('.rank-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#rank-grid-dealer .rank-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedDealerRank = btn.dataset.rank;
                updateDealerBtnState();
            });
        });

        document.getElementById('suit-grid-dealer')?.querySelectorAll('.suit-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#suit-grid-dealer .suit-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedDealerSuit = btn.dataset.suit;
                updateDealerBtnState();
            });
        });

        function updateDealerBtnState() {
            if (btnAddDealer) btnAddDealer.disabled = !(selectedDealerRank && selectedDealerSuit);
        }

        btnAddDealer?.addEventListener('click', () => {
            socket.emit('dealer_add', {
                room_code: config.roomCode,
                session_token: config.token,
                rank: selectedDealerRank,
                suit: selectedDealerSuit,
            });
            // reset
            selectedDealerRank = null; selectedDealerSuit = null;
            document.querySelectorAll('#rank-grid-dealer .rank-btn, #suit-grid-dealer .suit-btn')
                .forEach(b => b.classList.remove('selected'));
            updateDealerBtnState();
        });

        document.getElementById('btn-undo-dealer')?.addEventListener('click', () => {
            // Undo dealer card — send as special marker
            socket.emit('undo_dealer', {
                room_code: config.roomCode,
                session_token: config.token,
            });
        });

        document.getElementById('btn-end-round')?.addEventListener('click', () => {
            if (confirm('ยืนยันจบรอบ?')) {
                socket.emit('round_end', {
                    room_code: config.roomCode,
                    session_token: config.token,
                });
            }
        });
    }

    // ───────────────────────────────────────────────
    // CARD SELECTOR HELPER
    // ───────────────────────────────────────────────
    function setupCardSelector(rankGridId, suitGridId, addBtnId, onAdd) {
        let rank = null;
        let suit = null;
        const addBtn = document.getElementById(addBtnId);

        document.getElementById(rankGridId)?.querySelectorAll('.rank-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll(`#${rankGridId} .rank-btn`).forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                rank = btn.dataset.rank;
                if (addBtn) addBtn.disabled = !(rank && suit);
            });
        });

        document.getElementById(suitGridId)?.querySelectorAll('.suit-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll(`#${suitGridId} .suit-btn`).forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                suit = btn.dataset.suit;
                if (addBtn) addBtn.disabled = !(rank && suit);
            });
        });

        addBtn?.addEventListener('click', () => {
            onAdd(rank, suit);
            // reset selection
            rank = null; suit = null;
            document.querySelectorAll(`#${rankGridId} .rank-btn, #${suitGridId} .suit-btn`)
                .forEach(b => b.classList.remove('selected'));
            if (addBtn) addBtn.disabled = true;
        });
    }

    // ───────────────────────────────────────────────
    // ───────────────────────────────────────────────
    // SOCKET EVENT HANDLERS
    // ───────────────────────────────────────────────
    function triggerAdviceIfPlayer() {
        if (config.role === 'player') {
            socket.emit('advice_request', {
                room_code: config.roomCode,
                session_token: config.token,
            });
        }
    }

    function onHandUpdated(data) {
        const { player_token, nickname, role, hand } = data;
        const isMine = player_token === config.token;

        if (config.role === 'teacher' && isMine) {
            // Update my hand on teacher page
            updateHandDisplay('my-hand', hand);
            return;
        }

        if (config.role === 'player') {
            // Find the participant block in the main list
            let found = false;
            document.querySelectorAll('.participant').forEach(el => {
                if (el.dataset.token === player_token) {
                    found = true;
                    const display = el.querySelector('.hand-display');
                    if (display) display.innerHTML = renderHandHTML(hand);
                }
            });

            // Also update the action panel hand if it's mine
            if (isMine) {
                const actionHand = document.getElementById('my-action-hand');
                if (actionHand) {
                    const display = actionHand.querySelector('.hand-display');
                    if (display) {
                        // Directly inject the standardized HTML
                        display.innerHTML = renderHandHTML(hand);
                    } else if (hand && hand.cards && hand.cards.length > 0) {
                        // If it was previously empty, we need to rebuild the structure
                        // Rebuild structure with the native render template
                        actionHand.innerHTML = `
                            <div class="hand-display" style="gap: 4px;">
                                ${renderHandHTML(hand)}
                            </div>
                        `;
                    }
                }
            }

            // If a completely new player joined and added a card, create their box dynamically
            if (!found && config.role === 'player') {
                const section = document.querySelector('.players-section');
                if (section) {
                    const el = document.createElement('div');
                    el.className = 'participant';
                    el.dataset.token = player_token;

                    const roleIcon = role === 'player' ? '👤' : '🎯';
                    const roleBadge = role === 'teacher' ? '<span class="badge badge--teacher">อาจารย์</span>' : '';
                    const youBadge = isMine ? '<span class="badge badge--you">คุณ</span>' : '';

                    el.innerHTML = `
                        <div class="participant-label">
                            ${roleIcon} ${nickname || 'ผู้เล่นใหม่'} ${youBadge} ${roleBadge}
                        </div>
                        <div class="hand-display">
                            ${renderHandHTML(hand)}
                        </div>
                    `;
                    section.appendChild(el);
                }
            }

            // Advice depends on ALL visible cards (card counting), so we request an update whenever ANY hand changes
            triggerAdviceIfPlayer();
        }
    }

    function onDealerUpdated(data) {
        const el = document.getElementById('dealer-hand');
        if (el) el.innerHTML = renderHandHTML(data.hand);

        // Dealer card affects advice, so request update
        triggerAdviceIfPlayer();
    }

    function onAdviceResponse(advice) {
        const body = document.getElementById('advice-body');
        if (!body) return;

        if (advice.error) {
            // Keep the previous UI instead of showing an error when just recalculating passively
            if (body.innerHTML.includes('advice-placeholder')) {
                body.innerHTML = `<div class="advice-placeholder">${advice.error}</div>`;
            }
            return;
        }

        const action = advice.action || 'HIT';
        const winProb = advice.win_probability || 0;
        const actionLabels = { HIT: '🃏สู้', STAND: '✋พอ', DOUBLE: '💰เบิ้ล', BUST: '💥ทะลุ' };

        body.innerHTML = `
      <span class="advice-action--${action}" style="font-weight: bold; margin-right: 6px;">${actionLabels[action] || action}</span>
      <span style="color: var(--text-muted); font-size: 0.8rem;">ชนะ ${winProb}%</span>
    `;
    }

    function onRoundStarted(round) {
        const info = document.getElementById('round-info');
        if (info) info.textContent = `รอบที่ ${round.round_number}`;
        showToast(`▶ เริ่มรอบที่ ${round.round_number} แล้ว!`, 'success');

        // Clear all hands display
        document.querySelectorAll('.hand-display').forEach(el => {
            el.innerHTML = '<div class="hand-empty">ยังไม่มีไพ่</div>';
        });
        const adviceBody = document.getElementById('advice-body');
        if (adviceBody) adviceBody.innerHTML = '<div class="advice-placeholder">กรอกไพ่แล้วกด "วิเคราะห์"</div>';
    }

    function onRoundEnded(data) {
        showToast('■ จบรอบแล้ว', 'info');
    }

    // ───────────────────────────────────────────────
    // HTML RENDERING HELPERS
    // ───────────────────────────────────────────────
    const SUIT_SYMBOLS = { spades: '♠', hearts: '♥', diamonds: '♦', clubs: '♣' };
    const RED_SUITS = ['hearts', 'diamonds'];

    function renderHandHTML(hand) {
        if (!hand || !hand.cards || hand.cards.length === 0) {
            return '<div class="hand-empty">ยังไม่มีไพ่</div>';
        }
        const bustedBadge = hand.is_busted ? '<span class="badge badge--bust" style="font-size: 0.6rem; padding: 2px 4px;">💥</span>' : '';
        const bjBadge = hand.is_blackjack ? '<span class="badge badge--bj" style="font-size: 0.6rem; padding: 2px 4px;">🌟</span>' : '';
        const cardsHTML = hand.cards.map(c => {
            const color = RED_SUITS.includes(c.suit) ? 'red' : 'black';
            return `<div class="playing-card playing-card--${color}" style="width: 32px; height: 46px; padding: 2px;">
        <span class="card-rank" style="font-size: 0.85rem;">${c.rank}</span>
        <span class="card-suit" style="font-size: 0.85rem;">${SUIT_SYMBOLS[c.suit] || c.suit}</span>
      </div>`;
        }).join('');
        return `
      <div class="hand-score" style="font-size: 0.95rem; margin-bottom: 4px;">⭐ ${hand.score} ${bustedBadge}${bjBadge}</div>
      <div class="cards-row" style="flex-wrap: wrap; justify-content: flex-start; gap: 4px;">${cardsHTML}</div>
    `;
    }

    function updateHandDisplay(elId, hand) {
        const el = document.getElementById(elId);
        if (el) el.innerHTML = renderHandHTML(hand);
    }

    // ───────────────────────────────────────────────
    // UTILITIES
    // ───────────────────────────────────────────────
    function setConnected(connected) {
        const dot = document.getElementById('conn-dot');
        if (!dot) return;
        dot.className = 'connection-dot ' + (connected ? 'connected' : 'disconnected');
        dot.title = connected ? 'เชื่อมต่อแล้ว' : 'ขาดการเชื่อมต่อ';
    }

    function showToast(msg, type = 'info') {
        const container = document.querySelector('.flash-container') || (() => {
            const c = document.createElement('div');
            c.className = 'flash-container';
            document.body.appendChild(c);
            return c;
        })();
        const el = document.createElement('div');
        el.className = `flash flash--${type === 'error' ? 'error' : 'success'}`;
        el.textContent = msg;
        container.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    return { init };
})();
