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

        document.getElementById('btn-advice')?.addEventListener('click', () => {
            socket.emit('advice_request', {
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

        // Round controls
        document.getElementById('btn-start-round')?.addEventListener('click', () => {
            socket.emit('round_start', {
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
    // SOCKET EVENT HANDLERS
    // ───────────────────────────────────────────────
    function onHandUpdated(data) {
        const { player_token, hand } = data;
        const isMine = player_token === config.token;

        if (config.role === 'teacher' && isMine) {
            // Update my hand on teacher page
            updateHandDisplay('my-hand', hand);
            return;
        }

        if (config.role === 'player') {
            // Find the participant block and update
            document.querySelectorAll('.participant').forEach(el => {
                if (el.dataset.token === player_token) {
                    const display = el.querySelector('.hand-display');
                    if (display) display.innerHTML = renderHandHTML(hand);
                }
            });

            // If it's my own hand, auto-request advice
            if (isMine && hand.cards?.length > 0) {
                socket.emit('advice_request', {
                    room_code: config.roomCode,
                    session_token: config.token,
                });
            }
        }
    }

    function onDealerUpdated(data) {
        const el = document.getElementById('dealer-hand');
        if (el) el.innerHTML = renderHandHTML(data.hand);
    }

    function onAdviceResponse(advice) {
        const body = document.getElementById('advice-body');
        if (!body) return;

        if (advice.error) {
            body.innerHTML = `<div class="advice-placeholder">${advice.error}</div>`;
            return;
        }

        const action = advice.action || 'HIT';
        const winProb = advice.win_probability || 0;
        const actionLabels = { HIT: '🃏 HIT — หยิบเพิ่ม', STAND: '✋ STAND — หยุด', DOUBLE: '💰 DOUBLE — เพิ่มเดิมพัน', BUST: '💥 BUST!' };

        body.innerHTML = `
      <div class="advice-result">
        <div class="advice-action advice-action--${action}">${actionLabels[action] || action}</div>
        <div class="advice-win">โอกาสชนะ: <strong>${winProb}%</strong></div>
        <div class="win-bar"><div class="win-bar__fill" style="width: ${winProb}%"></div></div>
        <div class="advice-reason">${advice.reason || ''}</div>
        <div class="advice-meta">
          <span>คะแนน: ${advice.player_score}</span>
          <span>Count: ${advice.true_count >= 0 ? '+' : ''}${advice.true_count}</span>
        </div>
      </div>
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
        const bustedBadge = hand.is_busted ? '<span class="badge badge--bust">BUST</span>' : '';
        const bjBadge = hand.is_blackjack ? '<span class="badge badge--bj">BJ!</span>' : '';
        const cardsHTML = hand.cards.map(c => {
            const color = RED_SUITS.includes(c.suit) ? 'red' : 'black';
            return `<div class="playing-card playing-card--${color}">
        <span class="card-rank">${c.rank}</span>
        <span class="card-suit">${SUIT_SYMBOLS[c.suit] || c.suit}</span>
      </div>`;
        }).join('');
        return `
      <div class="hand-score">${hand.score} คะแนน ${bustedBadge}${bjBadge}</div>
      <div class="cards-row">${cardsHTML}</div>
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
