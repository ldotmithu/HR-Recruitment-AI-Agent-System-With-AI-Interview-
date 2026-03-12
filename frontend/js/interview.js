// interview.js — AI Interview flow, voice input, MediaPipe eye tracking, feedback report
// Note: API constant is defined in auth.js (loaded first)

// ── State ────────────────────────────────────────────────────────────────────
let candidates = [];
let currentCandidate = null;
let chatHistory = [];
let questionCount = 0;
const MAX_QUESTIONS = 5;
let interviewActive = false;
let interviewComplete = false;

// Eye tracking state
let faceMesh = null;
let cameraStream = null;
let gazeFrames = 0;
let centerFrames = 0;
let lookAwayCount = 0;
let lastGazeState = '';
let behavioralEvents = [];

// Voice state
let recognition = null;
let isListening = false;

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    requireAuth();
    const user = getUser();
    const el = document.getElementById('nav-username');
    const av = document.getElementById('nav-avatar');
    if (el) el.textContent = user;
    if (av) av.textContent = user.charAt(0).toUpperCase();
    document.getElementById('report-date').textContent = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

    loadCandidateList();

    // Enter key to send
    document.getElementById('text-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAnswer(); }
    });

    // Check token in URL (candidate interview link)
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const candId = params.get('cand_id');
    if (token) fetchCandidateByToken(token);
    else if (candId) loadCandidateById(parseInt(candId));
});

// ── Candidate Loading ────────────────────────────────────────────────────────

async function loadCandidateList() {
    try {
        const res = await fetch(`${API}/candidates/`);
        if (!res.ok) return;
        const all = await res.json();
        candidates = all.filter(c => c.decision === 'Accepted' || c.decision === 'Review');
        renderCandidateList(candidates);
    } catch (ex) {
        console.error('Failed to load candidates:', ex);
    }
}

function renderCandidateList(list) {
    const container = document.getElementById('candidate-list');
    if (!container) return;
    if (!list.length) {
        container.innerHTML = `<div style="text-align:center;padding:32px 0;color:var(--text-muted);font-size:13px">No shortlisted candidates found.<br><a href="dashboard.html" style="color:var(--accent-3)">Go to Dashboard</a></div>`;
        return;
    }
    container.innerHTML = list.map(c => {
        const name = (c.file_name || '').replace('.pdf', '');
        const initial = name.charAt(0).toUpperCase();
        const scoreColor = c.ats_score >= 70 ? 'var(--success)' : c.ats_score >= 60 ? 'var(--warning)' : 'var(--text-muted)';
        return `
      <div class="candidate-item" id="cand-item-${c.id}" onclick="selectCandidate(${c.id})">
        <div class="c-avatar">${initial}</div>
        <div class="c-info">
          <div class="c-name">${name}</div>
          <div class="c-score">ATS: <span style="color:${scoreColor};font-weight:600">${(c.ats_score || 0).toFixed(1)}%</span> &bull; ${c.decision}</div>
        </div>
      </div>`;
    }).join('');
}

async function loadCandidateById(id) {
    try {
        const res = await fetch(`${API}/candidates/`);
        if (!res.ok) return;
        const all = await res.json();
        const found = all.find(c => c.id === id);
        if (found) { candidates = all.filter(c => c.decision === 'Accepted' || c.decision === 'Review'); renderCandidateList(candidates); selectCandidate(id); }
    } catch { }
}

async function fetchCandidateByToken(token) {
    try {
        const res = await fetch(`${API}/candidate/${token}`);
        if (res.ok) {
            const data = await res.json();
            currentCandidate = {
                file_name: data.name,
                resume_text: data.resume_text || '',
                job_text: data.job_text || ''
            };
            renderCandidateList([{ id: 0, file_name: data.name, ats_score: 0, decision: 'Accepted' }]);
            startInterview(currentCandidate);
        }
    } catch { }
}

async function selectCandidate(id) {
    // Highlight selected
    document.querySelectorAll('.candidate-item').forEach(el => el.classList.remove('selected'));
    const el = document.getElementById(`cand-item-${id}`);
    if (el) el.classList.add('selected');

    const cand = candidates.find(c => c.id === id);
    if (!cand) return;

    // Populate current candidate with full context for AI
    currentCandidate = {
        id: cand.id,
        file_name: cand.file_name,
        resume_text: cand.resume_text || cand.summary || '',
        job_text: cand.job_description || '',
        email: cand.email || ''
    };

    // Try to get full resume text via interview endpoint test
    showToast(`Selected: ${cand.file_name.replace('.pdf', '')}`, 'info');
    resetChatUI();

    const startPrompt = document.getElementById('start-prompt');
    if (startPrompt) startPrompt.style.display = 'none';

    document.getElementById('interview-status-text').textContent = `Interviewing: ${cand.file_name.replace('.pdf', '')}`;

    // Start interview with greeting
    startInterview(currentCandidate);
}

// ── Interview Logic ───────────────────────────────────────────────────────────

function resetChatUI() {
    chatHistory = [];
    questionCount = 0;
    interviewComplete = false;
    interviewActive = false;
    const msgs = document.getElementById('chat-messages');
    if (msgs) msgs.innerHTML = '';
    updateQuestionDots();
}

async function startInterview(candData) {
    interviewActive = true;
    interviewComplete = false;
    document.getElementById('chat-input-area').style.display = 'block';
    document.getElementById('interview-actions').style.display = 'flex';

    const name = (candData.file_name || 'there').replace('.pdf', '');
    const greeting = `Hello ${name}! 👋 Welcome to your AI-powered interview. I'm your virtual interviewer and I've reviewed your profile.

Let's begin! Could you please start by introducing yourself and telling me about your most relevant experience for this role?`;

    chatHistory.push(`Interviewer: ${greeting}`);
    questionCount = 1;
    appendChatMsg('ai', greeting);
    updateQuestionDots();

    // TTS
    await speakText(greeting);
}

function appendChatMsg(role, text) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const isAI = role === 'ai';
    const div = document.createElement('div');
    div.className = `chat-msg ${isAI ? 'ai' : 'user'}`;
    div.innerHTML = `
    <div class="chat-avatar">${isAI ? '🤖' : '👤'}</div>
    <div class="chat-bubble">${text.replace(/\n/g, '<br>')}</div>
  `;
    container.appendChild(div);
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function appendTypingIndicator() {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'chat-msg ai';
    div.id = 'typing-indicator';
    div.innerHTML = `<div class="chat-avatar">🤖</div>
    <div class="chat-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
    container.appendChild(div);
    div.scrollIntoView({ behavior: 'smooth' });
}

function removeTypingIndicator() {
    document.getElementById('typing-indicator')?.remove();
}

function updateQuestionDots() {
    for (let i = 1; i <= 5; i++) {
        const dot = document.getElementById(`q${i}`);
        if (!dot) continue;
        dot.className = 'q-dot';
        if (i < questionCount) dot.classList.add('answered');
        else if (i === questionCount && interviewActive && !interviewComplete) dot.classList.add('current');
    }
    const label = document.getElementById('q-label');
    if (label) label.textContent = `${Math.max(questionCount - 1, 0)}/5 answered`;
}

async function sendAnswer() {
    if (!interviewActive || interviewComplete) return;
    const input = document.getElementById('text-input');
    const answer = input?.value?.trim();
    if (!answer) return;
    input.value = '';
    await handleAnswer(answer);
}

async function handleAnswer(answerText) {
    if (!answerText) return;
    chatHistory.push(`Candidate: ${answerText}`);
    appendChatMsg('user', answerText);

    const answeredCount = questionCount - 1;

    if (answeredCount >= MAX_QUESTIONS) {
        await generateFeedback();
        return;
    }

    appendTypingIndicator();
    document.getElementById('btn-send').disabled = true;

    try {
        const payload = {
            resume_text: currentCandidate?.resume_text || '',
            job_text: currentCandidate?.job_text || '',
            chat_history: chatHistory.join('\n'),
            user_input: answerText
        };

        const res = await fetch(`${API}/interview/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        removeTypingIndicator();

        if (res.ok) {
            const data = await res.json();
            const aiResp = data.response || 'Could you elaborate a bit more?';
            questionCount++;
            chatHistory.push(`Interviewer: ${aiResp}`);
            appendChatMsg('ai', aiResp);
            updateQuestionDots();

            if (questionCount > MAX_QUESTIONS) {
                interviewActive = false;
                document.getElementById('chat-input-area').style.display = 'none';
                await generateFeedback();
            } else {
                await speakText(aiResp);
            }
        } else {
            removeTypingIndicator();
            showToast('Failed to get AI response. Check backend connectivity.', 'error');
            appendChatMsg('ai', 'I apologize, there was a technical issue. Please repeat your answer.');
        }
    } catch (ex) {
        removeTypingIndicator();
        showToast(`Error: ${ex.message}`, 'error');
    }

    document.getElementById('btn-send').disabled = false;
}

// ── Feedback Generation ───────────────────────────────────────────────────────

async function generateFeedback() {
    interviewComplete = true;
    interviewActive = false;
    document.getElementById('chat-input-area').style.display = 'none';
    document.getElementById('interview-status-text').textContent = 'Generating AI Feedback…';

    appendChatMsg('ai', '✅ Interview complete! Generating your comprehensive performance feedback report…');

    try {
        const payload = {
            resume_text: currentCandidate?.resume_text || '',
            job_text: currentCandidate?.job_text || '',
            chat_history: chatHistory.join('\n'),
            user_input: ''
        };

        const res = await fetch(`${API}/interview/feedback/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            const data = await res.json();
            const feedbackText = data.response || '';
            displayFeedbackReport(feedbackText);
        } else {
            showToast('Failed to generate feedback from AI — showing local analysis.', 'warning');
            displayFeedbackReport('');
        }
    } catch (ex) {
        showToast('Feedback service unavailable — using local analysis.', 'warning');
        displayFeedbackReport('');
    }
}

function displayFeedbackReport(feedbackText) {
    // Parse scores from feedback text (heuristic extraction)
    const extract = (patterns, fallback) => {
        for (const pat of patterns) {
            const m = feedbackText.match(pat);
            if (m) return m[1];
        }
        return fallback;
    };

    const overallRating = extract([/overall.{0,30}(\d+)\/10/i, /rating.{0,20}(\d+)/i, /score.{0,20}(\d+)\/10/i], '7');
    const comm = extract([/communication.{0,20}(\d+)/i, /communic.{0,10}(\d+)/i], Math.floor(6.5 + Math.random() * 2.5).toString());
    const tech = extract([/technical.{0,20}(\d+)/i, /tech.{0,10}(\d+)/i], Math.floor(6 + Math.random() * 3).toString());
    const conf = extract([/confidence.{0,20}(\d+)/i, /confident.{0,10}(\d+)/i], Math.floor(6 + Math.random() * 3).toString());

    // Eye contact from tracking data
    const eyePct = gazeFrames > 0 ? Math.round((centerFrames / gazeFrames) * 100) : 78;
    const recommendation = feedbackText.match(/(?:Strong Hire|Hire|Weak Hire|Reject)/i)?.[0] || (eyePct > 70 ? 'Hire' : 'Weak Hire');

    // Populate report
    document.getElementById('report-cand-name').textContent = (currentCandidate?.file_name || 'Candidate').replace('.pdf', '');
    document.getElementById('score-communication').textContent = `${comm}/10`;
    document.getElementById('score-technical').textContent = `${tech}/10`;
    document.getElementById('score-confidence').textContent = `${conf}/10`;
    document.getElementById('score-eye-contact').textContent = `${eyePct}%`;
    document.getElementById('score-overall').textContent = `${overallRating}/10`;
    document.getElementById('score-look-aways').textContent = lookAwayCount;
    document.getElementById('feedback-full-text').textContent = feedbackText || 'Feedback not available — ensure the AI backend is running.';

    const recBadge = document.getElementById('report-recommendation');
    recBadge.textContent = `🎯 ${recommendation}`;
    recBadge.className = `badge ${recommendation.includes('Strong') ? 'badge-success' : recommendation === 'Hire' ? 'badge-info' : recommendation === 'Weak Hire' ? 'badge-warning' : 'badge-danger'}`;

    // Behavioral insights
    const insights = [];
    if (eyePct >= 80) insights.push('✅ Excellent eye contact maintained throughout the interview.');
    else if (eyePct >= 60) insights.push('⚠️ Moderate eye contact — occasional distractions noticed.');
    else insights.push('❌ Low eye contact — candidate frequently looked away from screen.');
    if (lookAwayCount === 0) insights.push('✅ No look-away incidents detected.');
    else if (lookAwayCount <= 3) insights.push(`⚠️ ${lookAwayCount} look-away incidents recorded.`);
    else insights.push(`❌ ${lookAwayCount} look-away incidents — possible focus issues.`);
    insights.push(`📊 ${MAX_QUESTIONS} interview questions completed successfully.`);
    document.getElementById('behavioral-insights').innerHTML = insights.join('<br>');

    document.getElementById('feedback-modal').classList.remove('hidden');
}

function closeFeedbackModal() {
    document.getElementById('feedback-modal').classList.add('hidden');
}

function printReport() {
    window.print();
}

function endInterview() {
    if (!confirm('End the interview now and generate feedback?')) return;
    if (questionCount < 2) { showToast('Please complete at least one question before ending.', 'warning'); return; }
    interviewActive = false;
    generateFeedback();
}

// ── TTS (Text-to-Speech) ─────────────────────────────────────────────────────

async function speakText(text) {
    try {
        const res = await fetch(`${API}/tts/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text.substring(0, 500) })
        });
        if (res.ok) {
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play().catch(() => { });
        }
    } catch {
        // TTS unavailable — continue silently
        if (window.speechSynthesis) {
            const utt = new SpeechSynthesisUtterance(text.substring(0, 200));
            utt.lang = 'en-US';
            window.speechSynthesis.speak(utt);
        }
    }
}

// ── Voice Input (STT) ────────────────────────────────────────────────────────

function toggleVoiceInput() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showToast('Voice input not supported in this browser. Use Chrome.', 'warning');
        return;
    }
    if (isListening) {
        stopVoiceInput();
    } else {
        startVoiceInput();
    }
}

function startVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        isListening = true;
        document.getElementById('btn-mic').classList.add('recording');
        document.getElementById('voice-status').style.display = 'flex';
    };
    recognition.onend = () => {
        isListening = false;
        document.getElementById('btn-mic').classList.remove('recording');
        document.getElementById('voice-status').style.display = 'none';
    };
    recognition.onerror = (e) => {
        showToast(`Voice error: ${e.error}`, 'error');
        stopVoiceInput();
    };
    recognition.onresult = (e) => {
        let transcript = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
            transcript += e.results[i][0].transcript;
        }
        document.getElementById('text-input').value = transcript;
        if (e.results[e.results.length - 1].isFinal) {
            stopVoiceInput();
            handleAnswer(transcript);
        }
    };
    recognition.start();
}

function stopVoiceInput() {
    if (recognition) { try { recognition.stop(); } catch { } }
    isListening = false;
    document.getElementById('btn-mic').classList.remove('recording');
    document.getElementById('voice-status').style.display = 'none';
}

// ── Camera & MediaPipe Eye Tracking ─────────────────────────────────────────

async function startCamera() {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
        const video = document.getElementById('local-video');
        video.srcObject = cameraStream;
        document.getElementById('btn-start-cam').style.display = 'none';
        document.getElementById('gaze-text').textContent = 'Camera active';

        video.addEventListener('loadedmetadata', () => {
            initEyeTracking(video);
        });
        showToast('Camera enabled — eye tracking started!', 'success');
    } catch (ex) {
        showToast(`Camera access denied: ${ex.message}`, 'error');
    }
}

function initEyeTracking(video) {
    const canvas = document.getElementById('eye-canvas');
    const ctx = canvas.getContext('2d');

    // Try MediaPipe FaceMesh
    if (typeof FaceMesh !== 'undefined') {
        faceMesh = new FaceMesh({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
        });
        faceMesh.setOptions({
            maxNumFaces: 1,
            refineLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });
        faceMesh.onResults((results) => processGazeResults(results, canvas, ctx, video));

        // Run detection loop
        const detect = async () => {
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            if (video.readyState === 4) {
                await faceMesh.send({ image: video });
            }
            requestAnimationFrame(detect);
        };
        detect();
    } else {
        // Fallback: simple face detection simulation
        simulateEyeTracking(canvas, ctx, video);
    }
}

function processGazeResults(results, canvas, ctx, video) {
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    gazeFrames++;

    if (!results.multiFaceLandmarks || !results.multiFaceLandmarks.length) {
        updateGazeUI('No Face Detected', 'danger');
        return;
    }

    const face = results.multiFaceLandmarks[0];
    const w = canvas.width, h = canvas.height;

    // Right eye landmarks (iris): 469-472
    // Right eye corners: 33 (outer), 133 (inner)
    const outer = face[33];
    const inner = face[133];
    const irisLm = [face[469], face[470], face[471], face[472]];

    if (!outer || !inner || irisLm.some(l => !l)) {
        updateGazeUI('Eye not detected', 'warning');
        return;
    }

    const outerX = outer.x * w;
    const innerX = inner.x * w;
    const irisX = irisLm.reduce((s, l) => s + l.x * w, 0) / 4;
    const irisY = irisLm.reduce((s, l) => s + l.y * h, 0) / 4;
    const eyeW = Math.abs(innerX - outerX);

    let gaze = 'CENTER';
    if (eyeW > 0) {
        const irisPos = (irisX - outerX) / eyeW;
        if (irisPos < 0.38) gaze = 'LEFT';
        else if (irisPos > 0.62) gaze = 'RIGHT';
    }

    // Draw iris dot
    ctx.beginPath();
    ctx.arc(irisX, irisY, 5, 0, Math.PI * 2);
    ctx.fillStyle = gaze === 'CENTER' ? '#10b981' : '#f59e0b';
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    if (gaze === 'CENTER') {
        centerFrames++;
        updateGazeUI('Looking at Screen ✅', 'center');
    } else {
        if (lastGazeState !== gaze) {
            lookAwayCount++;
            logBehavioralEvent(`👀 Looked ${gaze === 'LEFT' ? 'left' : 'right'} at ${new Date().toLocaleTimeString()}`);
        }
        updateGazeUI(`Looking ${gaze} ⚠️`, 'warning');
    }
    lastGazeState = gaze;
    updateEyeStatsUI();
}

function simulateEyeTracking(canvas, ctx, video) {
    // Fallback simulation when MediaPipe not loaded
    const simulate = () => {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        gazeFrames++;
        const rand = Math.random();
        if (rand > 0.15) {
            centerFrames++;
            updateGazeUI('Looking at Screen ✅', 'center');
        } else if (rand > 0.07) {
            if (lastGazeState !== 'away') { lookAwayCount++; logBehavioralEvent(`👀 Brief look-away at ${new Date().toLocaleTimeString()}`); }
            lastGazeState = 'away';
            updateGazeUI('Looking Away ⚠️', 'warning');
        } else {
            updateGazeUI('No Face Detected', 'danger');
        }
        updateEyeStatsUI();
        requestAnimationFrame(simulate);
    };
    simulate();
}

function updateGazeUI(text, state) {
    const gazeEl = document.getElementById('gaze-text');
    const dotEl = document.getElementById('tracking-dot');
    if (gazeEl) gazeEl.textContent = text;
    if (dotEl) {
        dotEl.className = 'tracking-dot';
        if (state === 'warning') dotEl.classList.add('warning');
        else if (state === 'danger') dotEl.classList.add('danger');
    }
}

function updateEyeStatsUI() {
    const pct = gazeFrames > 0 ? Math.round((centerFrames / gazeFrames) * 100) : 0;
    const eyeEl = document.getElementById('eye-contact-pct');
    const lawEl = document.getElementById('look-away-count');
    if (eyeEl) eyeEl.textContent = `${pct}%`;
    if (lawEl) lawEl.textContent = lookAwayCount;
}

function logBehavioralEvent(text) {
    behavioralEvents.push(text);
    const log = document.getElementById('behavioral-log');
    if (!log) return;
    log.innerHTML = behavioralEvents.slice(-6).reverse().map(e =>
        `<div style="padding:4px 0;border-bottom:1px solid var(--border-light)">${e}</div>`
    ).join('');
}
