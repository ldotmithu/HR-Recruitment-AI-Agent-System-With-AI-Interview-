// dashboard.js — Resume upload, ATS scoring, candidate analytics
// Note: API constant is defined in auth.js (loaded first)
let selectedFiles = [];
let currentInviteCandidate = null;

document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  // Set user in navbar
  const user = getUser();
  const el = document.getElementById('nav-username');
  const av = document.getElementById('nav-avatar');
  if (el) el.textContent = user;
  if (av) av.textContent = user.charAt(0).toUpperCase();

  loadCandidates();
  setupFileInput();
});

// ── File Input Setup ──────────────────────────────

function setupFileInput() {
  const input = document.getElementById('resume-input');
  const zone = document.getElementById('resume-drop-zone');
  if (!input || !zone) return;

  // Click anywhere on zone → open file picker
  zone.addEventListener('click', (e) => {
    if (e.target !== input) input.click();
  });

  input.addEventListener('change', () => {
    const files = Array.from(input.files);
    files.forEach(addFile);
    input.value = '';
  });

  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    Array.from(e.dataTransfer.files).forEach(file => {
      if (file.type === 'application/pdf') addFile(file);
    });
  });
}

function addFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast(`${file.name} is not a PDF file.`, 'error'); return;
  }
  if (selectedFiles.find(f => f.name === file.name)) {
    showToast(`${file.name} already added.`, 'warning'); return;
  }
  selectedFiles.push(file);
  renderFileList();
}

function removeFile(name) {
  selectedFiles = selectedFiles.filter(f => f.name !== name);
  renderFileList();
}

function renderFileList() {
  const list = document.getElementById('file-list');
  if (!list) return;
  list.innerHTML = selectedFiles.map(f => `
    <div class="file-chip">
      📄 <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${f.name}</span>
      <span style="font-size:11px;color:var(--text-muted)">${(f.size / 1024).toFixed(0)} KB</span>
      <button class="remove-file" onclick="removeFile('${f.name.replace(/'/g, "\\'")}')">✕</button>
    </div>
  `).join('');
}

// ── Analyze Resumes ───────────────────────────────

async function analyzeResumes() {
  const jd = document.getElementById('jd-input')?.value?.trim();
  const btn = document.getElementById('btn-analyze');

  if (!selectedFiles.length) { showToast('Please upload at least one PDF resume.', 'error'); return; }
  if (!jd) { showToast('Please enter a job description.', 'error'); return; }

  btn.disabled = true;
  btn.innerHTML = '<div class="spinner" style="width:18px;height:18px"></div> Analyzing…';

  const progressWrap = document.getElementById('analyze-progress-wrap');
  const progressBar = document.getElementById('analyze-progress-bar');
  const statusEl = document.getElementById('analyze-status');

  progressWrap.classList.remove('hidden');
  statusEl.classList.remove('hidden');

  const results = [];

  for (let i = 0; i < selectedFiles.length; i++) {
    const file = selectedFiles[i];
    statusEl.textContent = `Processing ${i + 1} of ${selectedFiles.length}: ${file.name}`;
    progressBar.style.width = `${Math.round(((i) / selectedFiles.length) * 100)}%`;

    try {
      const formData = new FormData();
      formData.append('resume_file', file);
      formData.append('job_description', jd);

      const res = await fetch(`${API}/process_resume/`, { method: 'POST', body: formData });
      const data = await res.json();

      if (res.ok) {
        const score = parseFloat(data.ats_score || 0);
        let decision = 'Rejected';
        if (score >= 70) decision = 'Accepted';
        else if (score >= 50) decision = 'Review';
        data.decision = decision;
        data.file_name = file.name;

        // Save to DB
        await fetch(`${API}/candidates/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_name: data.file_name,
            email: data.email || '',
            ats_score: score,
            decision,
            summary: data.resume_summary || '',
            resume_text: data.resume_text || '',
            job_description: jd,
            skill_match: data.skill_match || 0,
            experience_match: data.experience_match || 0,
            missing_keywords: data.missing_keywords || ''
          })
        });
        results.push(data);
      } else {
        results.push({ file_name: file.name, ats_score: 0, decision: 'Rejected', error: data.detail || 'Error' });
      }
    } catch (ex) {
      results.push({ file_name: file.name, ats_score: 0, decision: 'Rejected', error: ex.message });
    }
  }

  progressBar.style.width = '100%';
  statusEl.textContent = `✅ Completed processing ${results.length} resume(s)`;
  setTimeout(() => {
    progressWrap.classList.add('hidden');
    statusEl.classList.add('hidden');
  }, 2500);

  showToast(`Analyzed ${results.length} resume(s) successfully!`, 'success');
  selectedFiles = [];
  renderFileList();
  btn.disabled = false;
  btn.innerHTML = '🚀 Analyze Candidates';

  loadCandidates();
}

// ── Load & Render Candidates ──────────────────────

async function loadCandidates() {
  try {
    const res = await fetch(`${API}/candidates/`);
    if (!res.ok) return;
    const candidates = await res.json();
    renderCandidates(candidates);
  } catch (ex) {
    console.error('Failed to load candidates:', ex);
  }
}

function renderCandidates(candidates) {
  const tbody = document.getElementById('candidates-tbody');
  const metricsRow = document.getElementById('metrics-row');
  const tableCard = document.getElementById('table-card');
  const emptyState = document.getElementById('empty-state');

  if (!candidates || !candidates.length) {
    metricsRow.style.display = 'none';
    tableCard.style.display = 'none';
    emptyState.style.display = 'block';
    return;
  }

  emptyState.style.display = 'none';
  metricsRow.style.display = 'grid';
  tableCard.style.display = 'block';

  // Metrics
  const total = candidates.length;
  const short = candidates.filter(c => c.decision === 'Accepted').length;
  const review = candidates.filter(c => c.decision === 'Review').length;
  const reject = candidates.filter(c => c.decision === 'Rejected').length;
  const avgAts = candidates.reduce((a, c) => a + (c.ats_score || 0), 0) / total;

  document.getElementById('m-total').textContent = total;
  document.getElementById('m-shortlisted').textContent = short;
  document.getElementById('m-review').textContent = review;
  document.getElementById('m-rejected').textContent = reject;
  document.getElementById('m-avg-ats').textContent = avgAts.toFixed(1);

  // Table rows
  tbody.innerHTML = candidates.map((c, i) => {
    const decision = c.decision || 'Rejected';
    const badgeClass = decision === 'Accepted' ? 'badge-success' : decision === 'Review' ? 'badge-warning' : 'badge-danger';
    const badgeText = decision === 'Accepted' ? '✅ Shortlisted' : decision === 'Review' ? '🔍 Review' : '❌ Rejected';
    const ats = (c.ats_score || 0).toFixed(1);
    const skill = (c.skill_match || 0).toFixed(1);
    const exp = (c.experience_match || 0).toFixed(1);
    const name = (c.file_name || '').replace('.pdf', '');
    const missing = (c.missing_keywords || '—').split(',').slice(0, 3).join(', ');

    const showInvite = (decision === 'Accepted' || decision === 'Review') ? '' : 'style="display:none"';
    return `
      <tr class="animate-in">
        <td class="td-muted">${i + 1}</td>
        <td>
          <div style="display:flex;align-items:center;gap:10px">
            <div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,var(--accent-1),var(--accent-2));display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0">
              ${name.charAt(0).toUpperCase()}
            </div>
            <div>
              <div style="font-weight:600;font-size:14px">${name}</div>
              <div style="font-size:11px;color:var(--text-muted)">${c.file_name || ''}</div>
            </div>
          </div>
        </td>
        <td class="td-muted">${c.email || '<span style="color:var(--text-muted)">—</span>'}</td>
        <td>
          <div class="score-bar-cell">
            <span class="score-num-small" style="color:${ats >= 70 ? 'var(--success)' : ats >= 60 ? 'var(--warning)' : 'var(--danger)'}">${ats}%</span>
            <div class="progress-bar-wrapper">
              <div class="progress-bar-fill" style="width:${Math.min(parseFloat(ats), 100)}%"></div>
            </div>
          </div>
        </td>
        <td>
          <div class="score-bar-cell">
            <span class="score-num-small">${skill}%</span>
            <div class="progress-bar-wrapper">
              <div class="progress-bar-fill" style="width:${Math.min(parseFloat(skill), 100)}%;background:linear-gradient(90deg,#3b82f6,#60a5fa)"></div>
            </div>
          </div>
        </td>
        <td>
          <div class="score-bar-cell">
            <span class="score-num-small">${exp}%</span>
            <div class="progress-bar-wrapper">
              <div class="progress-bar-fill" style="width:${Math.min(parseFloat(exp), 100)}%;background:linear-gradient(90deg,#10b981,#34d399)"></div>
            </div>
          </div>
        </td>
        <td class="td-muted" style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px" title="${c.missing_keywords || ''}">${missing}</td>
        <td><span class="badge ${badgeClass}">${badgeText}</span></td>
        <td>
          <button class="btn btn-primary btn-sm" ${showInvite}
            onclick='openInviteModal(${c.id}, "${(c.file_name || '').replace(/"/g, '&quot;')}", "${(c.email || '').replace(/"/g, '&quot;')}") '>
            📧 Invite
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// ── Invite Modal ──────────────────────────────────

function openInviteModal(id, name, email) {
  currentInviteCandidate = { id, name, email };
  document.getElementById('invite-cand-name').textContent = name.replace('.pdf', '');
  document.getElementById('invite-email').value = email || '';
  document.getElementById('invite-link-result').classList.add('hidden');
  document.getElementById('invite-modal').classList.remove('hidden');
}

function closeInviteModal() {
  document.getElementById('invite-modal').classList.add('hidden');
  currentInviteCandidate = null;
}

async function sendInvite() {
  if (!currentInviteCandidate) return;
  const emailInput = document.getElementById('invite-email');
  const dateInput = document.getElementById('invite-date');
  const timeInput = document.getElementById('invite-time');
  const email = emailInput.value.trim();
  const date = dateInput.value;
  const time = timeInput.value;

  if (!email || !email.includes('@')) {
    showToast('Please enter a valid email address.', 'error'); return;
  }
  if (!date || !time) {
    showToast('Please select interview date and time.', 'error'); return;
  }

  const btn = document.getElementById('btn-send-invite');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div> Sending…';

  try {
    const res = await fetch(`${API}/invite_candidate/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: currentInviteCandidate.id,
        name: currentInviteCandidate.name.replace('.pdf', ''),
        email,
        interview_date: date,
        interview_time: time
      })
    });

    if (res.ok) {
      const data = await res.json();
      showToast('Interview invite sent successfully!', 'success');
      const linkResult = document.getElementById('invite-link-result');
      const linkAnchor = document.getElementById('invite-link-anchor');
      linkAnchor.href = data.link || '#';
      linkAnchor.textContent = data.link || 'Link generated';
      linkResult.classList.remove('hidden');
    } else {
      const err = await res.json();
      showToast(err.detail || 'Failed to send invite.', 'error');
    }
  } catch (ex) {
    // If email not configured, still generate a local link
    showToast('Email service not configured — generating local link.', 'warning');
    const linkResult = document.getElementById('invite-link-result');
    const linkAnchor = document.getElementById('invite-link-anchor');
    const link = `http://localhost:5500/interview.html?cand_id=${currentInviteCandidate.id}`;
    linkAnchor.href = link;
    linkAnchor.textContent = link;
    linkResult.classList.remove('hidden');
  }

  btn.disabled = false;
  btn.innerHTML = 'Send Invite 📨';
}

// ── Reset Dashboard ───────────────────────────────

async function resetDash() {
  if (!confirm('Are you sure you want to delete all candidate data? This cannot be undone.')) return;
  try {
    await fetch(`${API}/reset-dashboard/`, { method: 'POST' });
    showToast('All candidate data cleared.', 'info');
    loadCandidates();
  } catch (ex) {
    showToast('Failed to reset dashboard.', 'error');
  }
}
