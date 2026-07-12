/**
 * app.js — Highlight Extractor frontend logic
 * Milestone 11 — full annotation extractor.
 */

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  highlights: [],
  summary: null,
  viewMode: 'location',
  selectedFormat: 'pdf',
  fileName: '',
  sourceFormat: '',       // 'pdf' | 'docx' detected from uploaded file
  filters: { type: 'all', color: 'all', pageFrom: null, pageTo: null },
  isDemoFile: false,      // true when demo PDF is loaded
};

// ── Auth ─────────────────────────────────────────────────────────────────────
function getAuthHeader() {
  const key = localStorage.getItem('APP_API_KEY');
  return key ? { 'X-API-Key': key } : {};
}

// ── DOM helpers ────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const views = {
  upload:     $('view-upload'),
  processing: $('view-processing'),
  error:      $('view-error'),
  results:    $('view-results'),
};

function showView(name) {
  Object.entries(views).forEach(([k, el]) => el.classList.toggle('hidden', k !== name));
}

// ── Upload zone ────────────────────────────────────────────────────────────
const uploadZone = $('upload-zone');
const fileInput  = $('file-input');

uploadZone.addEventListener('click', (e) => {
  if (!e.target.closest('button') && !e.target.closest('input')) fileInput.click();
});
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });
$('btn-browse').addEventListener('click', e => { e.stopPropagation(); fileInput.click(); });

// ── Demo file button ────────────────────────────────────────────────────────
$('btn-demo').addEventListener('click', async (e) => {
  e.stopPropagation();
  $('btn-demo').disabled = true;
  $('btn-demo').textContent = '⏳ Loading…';
  try {
    const res = await fetch('/static/demo.pdf');
    const blob = await res.blob();
    const file = new File([blob], 'demo-annotations.pdf', { type: 'application/pdf' });
    state.isDemoFile = true;   // mark as demo before handleFile clears it
    await handleFile(file);
  } catch (err) {
    alert('Could not load demo file: ' + err.message);
  } finally {
    $('btn-demo').disabled = false;
    $('btn-demo').textContent = '🧪 Try demo file';
  }
});

// ── File handling ──────────────────────────────────────────────────────────
async function handleFile(file) {
  state._lastFile = file;   // store for DOCX re-extraction
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) {
    showError('Unsupported file type', `Only PDF and DOCX files are supported. Got ".${ext}".`);
    return;
  }

  state.fileName = file.name;
  state.sourceFormat = ext;
  // Preserve isDemoFile flag if it was set by btn-demo before calling this
  // (we only clear it for non-demo user files)
  if (file.name !== 'demo-annotations.pdf') state.isDemoFile = false;
  state.highlights = [];
  state.summary = null;
  state.viewMode = 'location';
  state.filters = { type: 'all', color: 'all', pageFrom: null, pageTo: null };

  $('processing-filename').textContent = file.name;
  showView('processing');

  const formData = new FormData();
  formData.append('file', file);
  // Formatting is handled reactively after results — always send false initially
  formData.append('include_formatting', false);

  try {
    const res = await fetch('/extract', {
      method: 'POST',
      body: formData,
      headers: getAuthHeader()
    });
    if (res.status === 401) { localStorage.removeItem('APP_API_KEY'); throw new Error('Invalid API Key.'); }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Extraction failed');
    }
    state.highlights = await res.json();
    setupResultsPage();
    renderResults();
    showView('results');
  } catch (err) {
    showError('Extraction failed', err.message);
  }
}

// ── Set up results page based on source format ────────────────────────────
function setupResultsPage() {
  // Show DOCX formatting toggle only for DOCX files
  const docxGroup = $('docx-formatting-group');
  if (docxGroup) {
    docxGroup.style.display = state.sourceFormat === 'docx' ? 'flex' : 'none';
  }

  // Populate dynamic filters
  populateFilters();
  
  // Reset filter inputs
  if ($('filter-type')) $('filter-type').value = 'all';
  if ($('filter-color')) $('filter-color').value = 'all';
  if ($('filter-page-from')) $('filter-page-from').value = '';
  if ($('filter-page-to')) $('filter-page-to').value = '';
  if ($('include-formatting-chk')) $('include-formatting-chk').checked = false;
  
  // AI summary section reset
  hideAiSummary();
  const btnAi = $('btn-ai');
  if (btnAi) { btnAi.classList.remove('active'); btnAi.textContent = '✨ Summarize with AI'; btnAi.disabled = false; }
}

// ── DOCX formatting toggle (re-extract) ──────────────────────────────────
if ($('include-formatting-chk')) {
  $('include-formatting-chk').addEventListener('change', async () => {
    if (state.sourceFormat !== 'docx' || !state.fileName) return;
    // Re-upload the cached file with new setting
    // We need to keep the original file object; store it
    if (!state._lastFile) return;
    
    $('processing-filename').textContent = state.fileName;
    showView('processing');
    
    const formData = new FormData();
    formData.append('file', state._lastFile);
    formData.append('include_formatting', $('include-formatting-chk').checked);
    
    try {
      const res = await fetch('/extract', {
        method: 'POST',
        body: formData,
        headers: getAuthHeader()
      });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Re-extraction failed'); }
      state.highlights = await res.json();
      state.summary = null;
      populateFilters();
      renderResults();
      showView('results');
    } catch (err) {
      showView('results');
      alert('Re-extraction failed: ' + err.message);
    }
  });
}

// ── Filters ────────────────────────────────────────────────────────────────
function populateFilters() {
  const types = new Set();
  const colors = new Set();
  state.highlights.forEach(h => {
    types.add(h.annotation_type || 'highlight');
    colors.add(h.color);
  });

  const typeSelect = $('filter-type');
  if (typeSelect) {
    typeSelect.innerHTML = '<option value="all">All Types</option>';
    Array.from(types).sort().forEach(t => {
      typeSelect.innerHTML += `<option value="${t}">${t.charAt(0).toUpperCase() + t.slice(1)}</option>`;
    });
  }

  const colorSelect = $('filter-color');
  if (colorSelect) {
    colorSelect.innerHTML = '<option value="all">All Colors</option>';
    Array.from(colors).sort().forEach(c => {
      const label = c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      colorSelect.innerHTML += `<option value="${c}">${label}</option>`;
    });
  }
}

if ($('filter-type')) $('filter-type').addEventListener('change', e => { state.filters.type = e.target.value; renderResults(); });
if ($('filter-color')) $('filter-color').addEventListener('change', e => { state.filters.color = e.target.value; renderResults(); });
if ($('filter-page-from')) $('filter-page-from').addEventListener('input', e => { state.filters.pageFrom = e.target.value ? parseInt(e.target.value) : null; renderResults(); });
if ($('filter-page-to')) $('filter-page-to').addEventListener('input', e => { state.filters.pageTo = e.target.value ? parseInt(e.target.value) : null; renderResults(); });

function getFilteredHighlights() {
  return state.highlights.filter(h => {
    if (state.filters.type !== 'all' && (h.annotation_type || 'highlight') !== state.filters.type) return false;
    if (state.filters.color !== 'all' && h.color !== state.filters.color) return false;
    
    // Page range — extract page number from location like "page 4"
    if (state.filters.pageFrom || state.filters.pageTo) {
      const match = h.location.match(/page\s+(\d+)/i);
      const pageNum = match ? parseInt(match[1]) : null;
      if (pageNum !== null) {
        if (state.filters.pageFrom && pageNum < state.filters.pageFrom) return false;
        if (state.filters.pageTo && pageNum > state.filters.pageTo) return false;
      }
    }
    return true;
  });
}

// ── Error view ─────────────────────────────────────────────────────────────
function showError(title, message) {
  $('error-title').textContent = title;
  $('error-message').textContent = message;
  showView('error');
}

$('btn-retry').addEventListener('click', () => { fileInput.value = ''; showView('upload'); });

// ── Results rendering ──────────────────────────────────────────────────────
function renderResults() {
  const filtered = getFilteredHighlights();
  $('result-count').textContent = `${filtered.length} annotation${filtered.length !== 1 ? 's' : ''}`;

  // Filename + optional demo link
  const filenameEl = $('result-filename');
  filenameEl.textContent = state.fileName;
  const existingLink = document.getElementById('view-original-pdf-link');
  if (existingLink) existingLink.remove();
  if (state.isDemoFile) {
    const link = document.createElement('a');
    link.id = 'view-original-pdf-link';
    link.href = '/static/demo.pdf';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'View original PDF ↗';
    link.style.cssText = 'margin-left:10px; font-size:0.78rem; color:var(--accent-light); text-decoration:none; border-bottom:1px solid var(--accent-light);';
    filenameEl.insertAdjacentElement('afterend', link);
  }

  renderByLocation(filtered);
}

function renderByLocation(filtered) {
  const container = $('highlights-container');
  container.innerHTML = '';

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state"><span class="empty-icon">🔍</span><p>No annotations match your filters.</p></div>`;
    return;
  }

  const groups = new Map();
  for (const h of filtered) {
    if (!groups.has(h.location)) groups.set(h.location, []);
    groups.get(h.location).push(h);
  }

  let delay = 0;
  for (const [location, items] of groups) {
    const group = document.createElement('div');
    group.className = 'location-group';
    group.innerHTML = `<div class="location-header"><h3>${escHtml(formatLocation(location))}</h3><div class="location-divider"></div></div>`;
    for (const h of items) { group.appendChild(buildHighlightCard(h, delay)); delay += 30; }
    container.appendChild(group);
  }
}

// ── Format timestamp as YYYY-MM-DD HH:mm ──────────────────────────────────
function formatTimestamp(ts) {
  if (!ts) return null;
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return null;
    const yr = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    const dy = String(d.getDate()).padStart(2, '0');
    const hr = String(d.getHours()).padStart(2, '0');
    const mn = String(d.getMinutes()).padStart(2, '0');
    return `${yr}-${mo}-${dy} ${hr}:${mn}`;
  } catch (e) { return null; }
}

function buildHighlightCard(h, delayMs = 0) {
  const card = document.createElement('div');
  const colorClass = 'color-' + h.color.replace(/[^a-z0-9_]/g, '');
  card.className = `highlight-card ${colorClass}`;
  card.style.animationDelay = `${delayMs}ms`;

  const colorLabel = h.color.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const atype = h.annotation_type || 'highlight';

  const typeColors = { highlight: '#f59e0b', underline: '#3b82f6', strikeout: '#ef4444', note: '#8b5cf6' };
  const typeBg = typeColors[atype] || '#6b7280';

  const typeBadge = `<span style="padding:2px 7px; border-radius:4px; font-size:0.7rem; font-weight:600; background:${typeBg}20; color:${typeBg}; border:1px solid ${typeBg}40; letter-spacing:0.03em;">${atype.toUpperCase()}</span>`;

  const ts = formatTimestamp(h.timestamp);
  const tsBadge = ts
    ? `<span style="font-size:0.75rem;color:var(--text-muted)">🕒 ${escHtml(ts)}</span>`
    : `<span style="font-size:0.75rem;color:var(--text-muted)" title="No timestamp stored">🕒 —</span>`;

  card.innerHTML = `
    <div class="color-swatch"></div>
    <div class="card-body">
      <p class="card-text">${escHtml(h.text)}</p>
      <div class="card-meta" style="display:flex; align-items:center; flex-wrap:wrap; gap:8px;">
        ${typeBadge}
        <span class="color-badge"><span class="color-dot"></span>${escHtml(colorLabel)}</span>
        ${tsBadge}
        <span style="margin-left:auto; font-size:0.75rem; color:var(--text-muted);">${escHtml(h.location)}</span>
      </div>
      ${h.note ? `<div class="card-note">💬 ${escHtml(h.note)}</div>` : ''}
    </div>`;
  return card;
}

// ── AI Summarize ───────────────────────────────────────────────────────────
const btnAi = $('btn-ai');
btnAi.addEventListener('click', toggleAiSummarize);

async function toggleAiSummarize() {
  if (state.viewMode === 'summary') {
    state.viewMode = 'location';
    btnAi.classList.remove('active');
    btnAi.textContent = '✨ Summarize with AI';
    hideAiSummary();
    renderResults();
    return;
  }

  if (state.summary) {
    state.viewMode = 'summary';
    btnAi.classList.add('active');
    btnAi.textContent = '↩ Hide Summary';
    showAiSummary(state.summary);
    return;
  }

  btnAi.disabled = true;
  btnAi.textContent = '⏳ Summarizing…';

  const container = $('highlights-container');
  container.innerHTML = `
    <div class="ai-loading">
      <div class="spinner"></div>
      <span>Generating summarization...</span>
    </div>
    ${Array(3).fill('<div class="skeleton" style="margin-bottom:12px;height:80px;border-radius:10px"></div>').join('')}`;

  try {
    const res = await fetch('/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify({ highlights: getFilteredHighlights() }),
    });

    if (res.status === 401) { localStorage.removeItem('APP_API_KEY'); throw new Error('Invalid API Key.'); }
    if (res.status === 503) {
      alert('AI summary is not available: GEMINI_API_KEY is not set on the server.\n\nSet it before starting uvicorn:\n  set GEMINI_API_KEY=your_key\n  uvicorn api.main:app --reload');
      throw new Error('API key not configured');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'AI summary failed');
    }

    const data = await res.json();
    state.summary = data.summary;
    state.viewMode = 'summary';
    btnAi.classList.add('active');
    btnAi.textContent = '↩ Hide Summary';
    renderResults();
    showAiSummary(state.summary);
  } catch (err) {
    state.viewMode = 'location';
    btnAi.classList.remove('active');
    btnAi.textContent = '✨ Summarize with AI';
    renderResults();
    if (err.message !== 'API key not configured') alert('AI summary failed: ' + err.message);
  } finally {
    btnAi.disabled = false;
  }
}

function showAiSummary(text) {
  const el = $('ai-summary-container');
  if (!el) return;
  $('ai-summary-text').textContent = text;
  el.classList.remove('hidden');
  // Scroll smoothly to the summary
  setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
}

function hideAiSummary() {
  const el = $('ai-summary-container');
  if (el) el.classList.add('hidden');
}

// ── Copy summary ───────────────────────────────────────────────────────────
if ($('btn-copy-summary')) {
  $('btn-copy-summary').addEventListener('click', async () => {
    if (!state.summary) return;
    try {
      await navigator.clipboard.writeText(state.summary);
      const btn = $('btn-copy-summary');
      btn.textContent = '✅ Copied!';
      setTimeout(() => { btn.textContent = '📋 Copy'; }, 2000);
    } catch (e) {
      alert('Could not copy to clipboard.');
    }
  });
}

// ── Download summary as PDF ─────────────────────────────────────────────────
if ($('btn-download-summary')) {
  $('btn-download-summary').addEventListener('click', async () => {
    if (!state.summary) return;
    const btn = $('btn-download-summary');
    btn.disabled = true;
    btn.textContent = '⏳ Generating…';
    try {
      // Build a synthetic "highlight" list with the summary text, exported as PDF
      const syntheticHighlight = [{
        id: 'summary-1',
        source_format: 'summary',
        annotation_type: 'note',
        location: 'AI Summary',
        color: 'yellow',
        text: state.summary,
        note: null,
        timestamp: new Date().toISOString(),
        order: 0,
      }];
      const res = await fetch('/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify({ highlights: syntheticHighlight, format: 'pdf', template: 'reading_notes' }),
      });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'PDF generation failed'); }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'ai-summary.pdf';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('PDF download failed: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = '⬇ Download PDF';
    }
  });
}

// ── Export ─────────────────────────────────────────────────────────────────
document.querySelectorAll('.format-pill').forEach(pill => {
  pill.addEventListener('click', () => {
    document.querySelectorAll('.format-pill').forEach(p => p.classList.remove('selected'));
    pill.classList.add('selected');
    state.selectedFormat = pill.dataset.format;
  });
});

$('btn-download').addEventListener('click', downloadExport);

async function downloadExport() {
  const btn = $('btn-download');
  btn.disabled = true;
  btn.textContent = '⏳ Generating…';

  try {
    const res = await fetch('/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: JSON.stringify({
        highlights: getFilteredHighlights(),
        format: state.selectedFormat,
        template: $('export-template') ? $('export-template').value : 'simple'
      }),
    });

    if (res.status === 401) { localStorage.removeItem('APP_API_KEY'); throw new Error('Invalid API Key.'); }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Export failed');
    }

    const blob = await res.blob();
    const contentDisp = res.headers.get('Content-Disposition') || '';
    const match = contentDisp.match(/filename="?([^"]+)"?/);
    const defaultExt = state.selectedFormat === 'anki' ? 'txt' : state.selectedFormat;
    const filename = match ? match[1] : `highlights.${defaultExt}`;

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('Export failed: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '⬇ Download';
  }
}

// ── New file ───────────────────────────────────────────────────────────────
$('btn-new-file').addEventListener('click', () => {
  fileInput.value = '';
  state.highlights = [];
  state.summary = null;
  state.viewMode = 'location';
  state.filters = { type: 'all', color: 'all', pageFrom: null, pageTo: null };
  state._lastFile = null;
  btnAi.classList.remove('active');
  btnAi.textContent = '✨ Summarize with AI';
  showView('upload');
});

// ── Helpers ────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatLocation(loc) {
  return loc.charAt(0).toUpperCase() + loc.slice(1);
}

// ── Init ───────────────────────────────────────────────────────────────────
showView('upload');
