/**
 * BlackJack Advisor — Client-Side JavaScript
 * Unified real-time card game management client
 */
const BlackJack = (() => {
    let socket;
    let config = {};

    // ─── Target Selection State ────────────────────────────────────────
    let currentTarget = {
        token: null,    // player token (null = dealer)
        handId: null,   // specific hand id (null = use token's main hand)
        handIndex: 0,
        isDealer: false,
        name: '',
        hand: null,     // cached hand data for the action panel preview
    };

    // ─── Local player registry ─────────────────────────────────────────
    // Maps token -> { nickname, role, hands: { handId: handData } }
    const playerRegistry = {};

    // ─── Edit mode (gear icon) ─────────────────────────────────────────
    let editMode = false;

    // ───────────────────────────────────────────────
    // INIT
    // ───────────────────────────────────────────────
    function init(cfg) {
        config = cfg;
        socket = io({ transports: ['websocket'] });

        socket.on('connect', () => {
            setConnected(true);
            socket.emit('join_room_ws', { room_code: config.roomCode, session_token: config.token });
            setTimeout(() => triggerAdviceIfPlayer(), 300);
        });
        socket.on('disconnect', () => setConnected(false));
        socket.on('error', (data) => showToast(data.message, 'error'));

        socket.on('hand_updated', onHandUpdated);
        socket.on('dealer_updated', onDealerUpdated);
        socket.on('advice_response', onAdviceResponse);
        socket.on('round_started', onRoundStarted);
        socket.on('round_ended', onRoundEnded);
        socket.on('player_joined', onPlayerJoined);
        socket.on('hand_split', onHandSplit);
        socket.on('hand_deleted', onHandDeleted);
        socket.on('player_kicked', onPlayerKicked);
        socket.on('player_renamed', onPlayerRenamed);

        // Set default target
        if (config.role === 'teacher') {
            currentTarget = { token: null, handId: null, handIndex: 0, isDealer: true, name: 'เจ้ามือ', hand: null };
        } else {
            currentTarget = { token: config.token, handId: null, handIndex: 0, isDealer: false, name: `คุณ (${config.nickname})`, hand: null };
        }

        // ── Pre-populate playerRegistry from server-rendered HTML ──────
        document.querySelectorAll('.participant[data-token]').forEach(el => {
            const token = el.dataset.token;
            const nickname = el.dataset.name || '';
            const handId = el.dataset.handId || null;

            if (!playerRegistry[token]) {
                playerRegistry[token] = { nickname, role: 'player', hands: {} };
            }

            // Parse initial hand data from Jinja2-rendered JSON attribute
            try {
                const handJson = el.dataset.handJson;
                if (handJson && handJson !== 'null') {
                    const hand = JSON.parse(handJson);
                    if (hand && hand.id) {
                        playerRegistry[token].hands[hand.id] = hand;
                    }
                }
            } catch (e) { /* ignore parse errors */ }
        });

        initUniversalUI();
        updateTargetVisuals();
        // Show initial preview of the default target
        updateActionPanelPreview();

        document.getElementById('btn-start-round')?.addEventListener('click', () => {
            if (confirm('คุณต้องการเริ่มรอบใหม่ใช่หรือไม่?\nไพ่บนโต๊ะทั้งหมดจะถูกล้างทิ้ง')) {
                socket.emit('round_start', { room_code: config.roomCode, session_token: config.token });
            }
        });
    }

    // ───────────────────────────────────────────────
    // UNIVERSAL UI LOGIC
    // ───────────────────────────────────────────────
    function initUniversalUI() {
        // Card input
        setupCardSelector('rank-grid', 'suit-grid', 'btn-add-card', (rank, suit) => {
            if (currentTarget.isDealer) {
                socket.emit('dealer_add', { room_code: config.roomCode, session_token: config.token, rank, suit });
            } else {
                socket.emit('card_add', {
                    room_code: config.roomCode, session_token: config.token,
                    target_token: currentTarget.token, hand_id: currentTarget.handId, rank, suit,
                });
            }
        });

        // Undo
        document.getElementById('btn-undo-card')?.addEventListener('click', () => {
            if (currentTarget.isDealer) {
                socket.emit('undo_dealer', { room_code: config.roomCode, session_token: config.token });
            } else {
                socket.emit('undo_card', {
                    room_code: config.roomCode, session_token: config.token,
                    target_token: currentTarget.token, hand_id: currentTarget.handId,
                });
            }
        });

        // Split
        document.getElementById('btn-split-hand')?.addEventListener('click', () => {
            if (currentTarget.isDealer) { showToast('ไม่สามารถ split มือเจ้ามือได้', 'error'); return; }
            socket.emit('split_hand', {
                room_code: config.roomCode, session_token: config.token,
                target_token: currentTarget.token,
            });
        });

        // Delete current selected hand
        document.getElementById('btn-delete-hand')?.addEventListener('click', () => {
            if (currentTarget.isDealer || !currentTarget.handId) {
                showToast('เลือกมือที่ต้องการลบก่อน', 'error'); return;
            }
            if (confirm('ยืนยันลบมือนี้?')) {
                socket.emit('delete_hand', {
                    room_code: config.roomCode, session_token: config.token,
                    hand_id: currentTarget.handId,
                });
            }
        });

        // Rename self
        document.getElementById('btn-rename-self')?.addEventListener('click', () => {
            const newName = prompt('ชื่อใหม่:', config.nickname);
            if (newName && newName.trim()) {
                socket.emit('rename_player', {
                    room_code: config.roomCode, session_token: config.token,
                    nickname: newName.trim(),
                });
            }
        });

        // End round
        document.getElementById('btn-end-round')?.addEventListener('click', () => {
            if (confirm('ยืนยันจบรอบ?')) {
                socket.emit('round_end', { room_code: config.roomCode, session_token: config.token });
            }
        });

        bindSelectableTargets();
        document.getElementById('btn-edit-mode')?.addEventListener('click', toggleEditMode);
        // Wire add-player buttons
        document.getElementById('btn-add-player')?.addEventListener('click', () => promptAddPlayer('player'));
        document.getElementById('btn-add-dealer')?.addEventListener('click', () => promptAddPlayer('dealer'));
    }

    function bindSelectableTargets() {
        document.querySelectorAll('.selectable-target').forEach(el => {
            if (el.dataset.targetBound) return;
            el.dataset.targetBound = '1';
            el.addEventListener('click', () => onTargetClick(el));
        });
    }

    // ─── Edit Mode ──────────────────────────────────────────────────────
    function toggleEditMode() {
        editMode = !editMode;
        const gearBtn = document.getElementById('btn-edit-mode');
        if (gearBtn) {
            gearBtn.style.background = editMode ? 'rgba(56,189,248,0.2)' : 'rgba(255,255,255,0.08)';
            gearBtn.style.borderColor = editMode ? 'var(--primary)' : 'var(--border)';
            gearBtn.style.color = editMode ? 'var(--primary)' : 'var(--text-secondary)';
        }
        applyEditMode();
        if (editMode) showToast('⚙️ โหมดแก้ไข เปิดแล้ว — กด ⚙️ อีกครั้งเพื่อปิด', 'info');
    }

    function applyEditMode() {
        document.querySelectorAll('.edit-action').forEach(el => {
            el.style.display = editMode ? 'flex' : 'none';
        });
        const addBar = document.getElementById('add-player-bar');
        if (addBar) addBar.style.display = editMode ? 'flex' : 'none';
    }

    function promptAddPlayer(role) {
        if (role === 'dealer') {
            const dealerExists = Object.values(playerRegistry).some(p => p.role === 'dealer');
            if (dealerExists) {
                showToast('ห้องนี้มีดีลเลอร์แล้ว ลบดีลเลอร์เก่าก่อน', 'error');
                return;
            }
        }
        const count = Object.keys(playerRegistry).length;
        const defaultName = role === 'dealer' ? 'ดีลเลอร์' : `ผู้เล่น ${count + 1}`;
        const name = prompt(`ชื่อ${role === 'dealer' ? 'ดีลเลอร์' : 'ผู้เล่น'}ใหม่:`, defaultName);
        if (name && name.trim()) {
            socket.emit('add_player', {
                room_code: config.roomCode,
                session_token: config.token,
                nickname: name.trim(),
                role,
            });
        }
    }

    function onTargetClick(el) {
        const isDealer = el.dataset.isDealer === 'true';
        if (isDealer) {
            currentTarget = { token: null, handId: null, handIndex: 0, isDealer: true, name: 'เจ้ามือ', hand: null };
        } else {
            const token = el.dataset.token;
            const handIndex = parseInt(el.dataset.handIndex || '0');
            const baseName = el.dataset.name || '';
            const handLabel = handIndex > 0 ? ` มือ ${handIndex + 1}` : '';
            const name = `${baseName}${handLabel}`;

            // Resolve hand data — prefer element attribute, then registry
            let hand = null;
            let handId = el.dataset.handId || null;

            try {
                const raw = el.dataset.handJson;
                if (raw && raw !== 'null') hand = JSON.parse(raw);
            } catch (e) { }

            if (!hand && handId && playerRegistry[token]?.hands[handId]) {
                hand = playerRegistry[token].hands[handId];
            }

            if (!hand && playerRegistry[token]) {
                // Find any hand with matching hand_index from registry
                const allHands = Object.values(playerRegistry[token].hands);
                hand = allHands.find(h => h.hand_index === handIndex) || allHands[0] || null;
                if (hand) handId = hand.id;
            }

            currentTarget = { token, handId, handIndex, isDealer: false, name, hand };
        }
        updateTargetVisuals();
        updateActionPanelPreview();
        triggerAdviceIfPlayer();
    }

    function updateTargetVisuals() {
        document.querySelectorAll('.selectable-target').forEach(el => {
            el.style.borderColor = 'transparent';
            el.style.boxShadow = 'none';
        });

        let targetEl = null;
        if (currentTarget.isDealer) {
            targetEl = document.getElementById('dealer-target');
        } else if (currentTarget.handId) {
            targetEl = document.querySelector(`.participant[data-hand-id="${currentTarget.handId}"]`);
        } else {
            targetEl = document.querySelector(`.participant[data-token="${currentTarget.token}"][data-hand-index="0"]`)
                || document.querySelector(`.participant[data-token="${currentTarget.token}"]`);
        }

        if (targetEl) {
            const color = currentTarget.isDealer ? 'var(--gold)' : 'var(--primary)';
            const glow = currentTarget.isDealer ? 'rgba(255,215,0,0.25)' : 'rgba(56,189,248,0.25)';
            targetEl.style.borderColor = color;
            targetEl.style.boxShadow = `0 0 0 2px ${glow}`;
        }

        const titleEl = document.getElementById('action-target-title');
        if (titleEl) {
            titleEl.innerHTML = currentTarget.isDealer
                ? '🎯 กรอกไพ่ให้: 🎰 เจ้ามือ'
                : `🎯 กรอกไพ่ให้: 👤 ${currentTarget.name}`;
            titleEl.style.color = currentTarget.isDealer ? 'var(--gold)' : 'var(--primary)';
        }
    }

    /** Update the action panel hand preview to show the currently selected target's cards */
    function updateActionPanelPreview() {
        // Works for both templates: game_player.html has #action-hand-preview, game_teacher.html too
        const preview = document.getElementById('action-hand-preview') || document.getElementById('my-action-hand');
        if (!preview) return;
        preview.innerHTML = renderHandHTML(currentTarget.hand);
    }

    // ───────────────────────────────────────────────
    // PLAYER & HAND DOM MANAGEMENT
    // ───────────────────────────────────────────────

    /**
     * Re-render all hand rows for a player token.
     * groups all hands under one player block.
     */
    function rerenderPlayerHands(token) {
        const section = document.querySelector('.players-section');
        if (!section) return;

        // Remove all existing rows for this player
        section.querySelectorAll(`[data-token="${token}"]`).forEach(el => el.remove());

        const player = playerRegistry[token];
        if (!player) return;

        const handIds = Object.keys(player.hands).sort((a, b) => {
            return (player.hands[a]?.hand_index || 0) - (player.hands[b]?.hand_index || 0);
        });

        // If player has no hands yet, show a single empty placeholder
        if (handIds.length === 0) {
            const el = buildParticipantEl(token, player.nickname, null, 0, null);
            section.appendChild(el);
        } else {
            handIds.forEach((handId, i) => {
                const hand = player.hands[handId];
                const el = buildParticipantEl(token, player.nickname, hand, hand.hand_index, handId);
                section.appendChild(el);
            });
        }

        bindSelectableTargets();
    }

    function buildParticipantEl(token, nickname, hand, handIndex, handId) {
        const el = document.createElement('div');
        el.className = 'participant selectable-target';
        el.dataset.token = token;
        el.dataset.name = nickname;
        el.dataset.handIndex = String(handIndex);
        el.dataset.handJson = hand ? JSON.stringify(hand) : 'null';
        if (handId) el.dataset.handId = handId;

        const handBadge = handIndex > 0
            ? `<span style="font-size:0.7rem;color:var(--text-muted);margin-left:2px;">มือ ${handIndex + 1}</span>` : '';

        // Count total hands for this player to know if we should show kick vs delete-hand
        const totalHands = Object.keys(playerRegistry[token]?.hands || {}).length;
        const isLastHand = totalHands <= 1;

        el.style.cssText = 'background: var(--bg-hover); padding: 8px; border-radius: 6px; border: 2px solid transparent; transition: all 0.2s; cursor: pointer;';
        el.innerHTML = `
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                <div class="participant-label" style="font-size: 0.85rem; display:flex; align-items:center; gap:4px;">
                    ${nickname} ${handBadge}
                </div>
                <div class="edit-action" style="display:${editMode ? '' : 'none'}; gap:4px; align-items:center;">
                    ${handId ? `<button class="btn-del-hand" data-hand-id="${handId}" data-is-last="${isLastHand}" style="background:none;border:none;color:#ef4444;cursor:pointer;font-size:0.8rem;padding:2px 4px;" title="${isLastHand ? 'ลบผู้เล่น' : 'ลบมือนี้'}">${isLastHand ? '🚫' : '✕'}</button>` : ''}
                    <button class="btn-rename" data-token="${token}" data-name="${nickname}" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:0.75rem;padding:2px 4px;" title="เปลี่ยนชื่อ">✏️</button>
                </div>
            </div>
            <div class="hand-display" style="gap: 4px;">
                ${renderHandHTML(hand)}
            </div>
        `;

        // Wire up inline buttons
        el.querySelector('.btn-del-hand')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const hid = e.currentTarget.dataset.handId;
            const isLast = e.currentTarget.dataset.isLast === 'true';
            if (isLast) {
                if (confirm(`ลบ "${nickname}" ออกจากห้อง? (มือสุดท้าย)`)) {
                    socket.emit('kick_player', { room_code: config.roomCode, session_token: config.token, target_token: token });
                }
            } else {
                if (confirm('ยืนยันลบมือนี้?')) {
                    socket.emit('delete_hand', { room_code: config.roomCode, session_token: config.token, hand_id: hid });
                }
            }
        });

        el.querySelector('.btn-rename')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const tkn = e.currentTarget.dataset.token;
            const nm = e.currentTarget.dataset.name;
            const newName = prompt('ชื่อใหม่:', nm);
            if (newName && newName.trim()) {
                socket.emit('rename_player', {
                    room_code: config.roomCode,
                    session_token: config.token,
                    target_token: tkn,
                    nickname: newName.trim(),
                });
            }
        });

        return el;
    }

    // ───────────────────────────────────────────────
    // CARD SELECTOR HELPER
    // ───────────────────────────────────────────────
    function setupCardSelector(rankGridId, suitGridId, addBtnId, onAdd) {
        let rank = null, suit = null;
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
            rank = null; suit = null;
            document.querySelectorAll(`#${rankGridId} .rank-btn, #${suitGridId} .suit-btn`).forEach(b => b.classList.remove('selected'));
            if (addBtn) addBtn.disabled = true;
        });
    }

    // ───────────────────────────────────────────────
    // SOCKET EVENT HANDLERS
    // ───────────────────────────────────────────────
    function triggerAdviceIfPlayer() {
        // Request advice for whoever is currently selected (skip dealer, skip empty hands)
        if (currentTarget.isDealer) return;
        if (!currentTarget.token) return;
        if (!currentTarget.hand || !currentTarget.hand.cards || currentTarget.hand.cards.length === 0) return;

        socket.emit('advice_request', {
            room_code: config.roomCode,
            session_token: config.token,
            target_token: currentTarget.token,
        });
    }

    function onPlayerJoined(data) {
        const { token, nickname, role } = data;
        if (role === 'teacher') return;

        if (role === 'dealer') {
            // Update dealer display name if it changed; dealer is static in DOM
            showToast(`🎰 ดีลเลอร์ "${nickname}" เพิ่มแล้ว`, 'success');
            // Register in registry so promptAddPlayer knows a dealer exists
            if (!playerRegistry[token]) {
                playerRegistry[token] = { nickname, role: 'dealer', hands: {} };
            }
            return;
        }

        if (playerRegistry[token]) return; // already known

        playerRegistry[token] = { nickname, role, hands: {} };
        rerenderPlayerHands(token);
        // Apply current edit mode to newly added row
        applyEditMode();
        showToast(`👤 ${nickname} เข้าร่วมแล้ว`, 'success');
    }

    function onHandUpdated(data) {
        const { player_token, hand_id, hand_index, nickname, role, hand } = data;

        // Update registry
        if (!playerRegistry[player_token]) {
            playerRegistry[player_token] = { nickname: nickname || '', role: role || 'player', hands: {} };
        }
        if (hand && hand_id) {
            playerRegistry[player_token].hands[hand_id] = hand;
        }

        // Re-render the player rows
        rerenderPlayerHands(player_token);

        // Update the action panel preview if this hand is the current target
        const isTargetedPlayer = currentTarget.token === player_token && !currentTarget.isDealer;
        const isTargetedHand = currentTarget.handId === hand_id   // exact match
            || (!currentTarget.handId && hand_index === 0);         // default main hand

        if (isTargetedPlayer && isTargetedHand) {
            currentTarget.hand = hand;
            // Also persist the hand_id so future operations are targeted correctly
            if (!currentTarget.handId && hand_id) currentTarget.handId = hand_id;
            updateActionPanelPreview();
        }

        // Re-apply selection highlight
        updateTargetVisuals();
        triggerAdviceIfPlayer();
    }

    function onHandSplit(data) {
        const { player_token, nickname, new_hand, all_hands } = data;

        if (!playerRegistry[player_token]) {
            playerRegistry[player_token] = { nickname, role: 'player', hands: {} };
        }
        // Rebuild hands in registry
        playerRegistry[player_token].hands = {};
        all_hands.forEach(h => { playerRegistry[player_token].hands[h.id] = h; });

        rerenderPlayerHands(player_token);
        showToast(`✂️ ${nickname} เพิ่มมือที่ ${new_hand.hand_index + 1} แล้ว!`, 'success');

        // Auto-select the new split hand
        const splitLabel = player_token === config.token
            ? `คุณ (${nickname}) มือ ${new_hand.hand_index + 1}`
            : `${nickname} มือ ${new_hand.hand_index + 1}`;
        currentTarget = { token: player_token, handId: new_hand.id, handIndex: new_hand.hand_index, isDealer: false, name: splitLabel, hand: new_hand };
        updateTargetVisuals();
        updateActionPanelPreview();
    }

    function onHandDeleted(data) {
        const { player_token, deleted_hand_id, remaining_hands } = data;

        // Rebuild registry for this player
        if (playerRegistry[player_token]) {
            playerRegistry[player_token].hands = {};
            remaining_hands.forEach(h => { playerRegistry[player_token].hands[h.id] = h; });
        }

        rerenderPlayerHands(player_token);

        // If we were targeting the deleted hand, reset to main hand
        if (currentTarget.handId === deleted_hand_id) {
            const mainHand = remaining_hands.find(h => h.hand_index === 0) || null;
            const player = playerRegistry[player_token];
            const name = player_token === config.token ? `คุณ (${player?.nickname || ''})` : (player?.nickname || '');
            currentTarget = { token: player_token, handId: mainHand?.id || null, handIndex: 0, isDealer: false, name, hand: mainHand };
            updateTargetVisuals();
            updateActionPanelPreview();
        }

        showToast('🗑️ ลบมือแล้ว', 'info');
    }

    function onPlayerKicked(data) {
        const { token, nickname } = data;
        // Remove all rows for this player
        document.querySelectorAll(`[data-token="${token}"]`).forEach(el => el.remove());
        delete playerRegistry[token];

        // If we were targeting this player, reset
        if (currentTarget.token === token) {
            currentTarget = { token: null, handId: null, handIndex: 0, isDealer: true, name: 'เจ้ามือ', hand: null };
            updateTargetVisuals();
            updateActionPanelPreview();
        }
        showToast(`🚫 ${nickname} ถูกลบออกจากห้อง`, 'info');
    }

    function onPlayerRenamed(data) {
        const { token, nickname } = data;
        if (playerRegistry[token]) {
            playerRegistry[token].nickname = nickname;
        }
        if (token === config.token) {
            config.nickname = nickname;
        }
        // Re-render their rows with new name
        rerenderPlayerHands(token);

        // Update target name if we're targeting them
        if (currentTarget.token === token) {
            const handLabel = currentTarget.handIndex > 0 ? ` มือ ${currentTarget.handIndex + 1}` : '';
            currentTarget.name = token === config.token ? `คุณ (${nickname})${handLabel}` : `${nickname}${handLabel}`;
            updateTargetVisuals();
        }
    }

    function onDealerUpdated(data) {
        const { hand } = data;
        // Update inline list display (teacher left panel)
        const listEl = document.getElementById('dealer-hand');
        if (listEl) listEl.innerHTML = renderHandHTML(hand);
        // Update action preview if dealer is currently selected
        if (currentTarget.isDealer) {
            currentTarget.hand = hand;
            updateActionPanelPreview();
        }
        triggerAdviceIfPlayer();
    }

    function onAdviceResponse(advice) {
        const body = document.getElementById('advice-body');
        if (!body) return;
        if (advice.error) { return; }
        const action = advice.action || 'HIT';
        const winProb = advice.win_probability || 0;
        const actionLabels = { HIT: '🃏สู้', STAND: '✋พอ', DOUBLE: '💰เบิ้ล', BUST: '💥ทะลุ' };
        body.innerHTML = `
            <span class="advice-action--${action}" style="font-weight:bold;margin-right:6px;">${actionLabels[action] || action}</span>
            <span style="color:var(--text-muted);font-size:0.8rem;">ชนะ ${winProb}%</span>
        `;
    }

    function onRoundStarted(round) {
        const info = document.getElementById('round-info');
        if (info) info.textContent = `รอบที่ ${round.round_number}`;
        showToast(`▶ เริ่มรอบที่ ${round.round_number} แล้ว!`, 'success');

        // Clear all hand data from registry and DOM
        Object.keys(playerRegistry).forEach(token => { playerRegistry[token].hands = {}; });
        document.querySelectorAll('.hand-display').forEach(el => {
            el.innerHTML = '<div class="hand-empty">ยังไม่มีไพ่</div>';
        });

        // Remove split rows — keep only index=0
        const section = document.querySelector('.players-section');
        if (section) {
            const seen = new Set();
            section.querySelectorAll('.participant').forEach(el => {
                const key = el.dataset.token;
                if (seen.has(key)) { el.remove(); return; }
                seen.add(key);
                el.dataset.handId = '';
                el.dataset.handIndex = '0';
            });
        }

        const adviceBody = document.getElementById('advice-body');
        if (adviceBody) adviceBody.innerHTML = '';

        // Reset target to default
        if (config.role === 'teacher') {
            currentTarget = { token: null, handId: null, handIndex: 0, isDealer: true, name: 'เจ้ามือ', hand: null };
        } else {
            currentTarget = { token: config.token, handId: null, handIndex: 0, isDealer: false, name: `คุณ (${config.nickname})`, hand: null };
        }
        updateTargetVisuals();
        updateActionPanelPreview();
    }

    function onRoundEnded(data) { showToast('■ จบรอบแล้ว', 'info'); }

    // ───────────────────────────────────────────────
    // HTML RENDERING HELPERS
    // ───────────────────────────────────────────────
    const SUIT_SYMBOLS = { spades: '♠', hearts: '♥', diamonds: '♦', clubs: '♣' };
    const RED_SUITS = ['hearts', 'diamonds'];

    function renderHandHTML(hand) {
        if (!hand || !hand.cards || hand.cards.length === 0) {
            return '<div class="hand-empty">ยังไม่มีไพ่</div>';
        }
        const bustedBadge = hand.is_busted ? '<span class="badge badge--bust" style="font-size:0.6rem;padding:2px 4px;">💥</span>' : '';
        const bjBadge = hand.is_blackjack ? '<span class="badge badge--bj" style="font-size:0.6rem;padding:2px 4px;">🌟</span>' : '';
        const cardsHTML = hand.cards.map(c => {
            const color = RED_SUITS.includes(c.suit) ? 'red' : 'black';
            return `<div class="playing-card playing-card--${color}" style="width:32px;height:46px;padding:2px;">
                <span class="card-rank" style="font-size:0.85rem;">${c.rank}</span>
                <span class="card-suit" style="font-size:0.85rem;">${SUIT_SYMBOLS[c.suit] || c.suit}</span>
            </div>`;
        }).join('');
        return `
            <div class="hand-score" style="font-size:0.95rem;margin-bottom:4px;">⭐ ${hand.score} ${bustedBadge}${bjBadge}</div>
            <div class="cards-row" style="flex-wrap:wrap;justify-content:flex-start;gap:4px;">${cardsHTML}</div>
        `;
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
            const c = document.createElement('div'); c.className = 'flash-container';
            document.body.appendChild(c); return c;
        })();
        const el = document.createElement('div');
        el.className = `flash flash--${type === 'error' ? 'error' : 'success'}`;
        el.textContent = msg;
        container.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    return { init };
})();
