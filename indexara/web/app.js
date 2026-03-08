(function () {
  'use strict';

  let currentMode = 'search';
  let debounceTimer = null;

  const form = document.getElementById('search-form');
  const input = document.getElementById('query-input');
  const submitBtn = document.getElementById('submit-btn');
  const results = document.getElementById('results');
  const statusBar = document.getElementById('status-bar');
  const modeButtons = document.querySelectorAll('.mode-btn');

  // Mode toggle
  modeButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      currentMode = btn.dataset.mode;
      modeButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const searchContainer = document.querySelector('.search-container');
      if (currentMode === 'insights') {
        searchContainer.style.display = 'none';
        results.innerHTML = '';
        statusBar.textContent = '';
        doInsights();
      } else {
        searchContainer.style.display = '';
        if (currentMode === 'search') {
          input.placeholder = 'Search files... e.g. FLAC albums by Radiohead';
          submitBtn.textContent = 'Search';
        } else {
          input.placeholder = 'Ask a question... e.g. What documents mention broadband costs?';
          submitBtn.textContent = 'Ask';
        }
        results.innerHTML = '';
        statusBar.textContent = '';
        input.focus();
      }
    });
  });

  // Form submit
  form.addEventListener('submit', e => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    runQuery(q);
  });

  // Debounced live search (search mode only)
  input.addEventListener('input', () => {
    if (currentMode !== 'search') return;
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (!q) {
      results.innerHTML = '';
      statusBar.textContent = '';
      return;
    }
    if (q.length < 2) return;
    debounceTimer = setTimeout(() => runQuery(q), 400);
  });

  async function runQuery(q) {
    if (currentMode === 'search') {
      await doSearch(q);
    } else {
      await doAsk(q);
    }
  }

  async function doInsights() {
    results.innerHTML = '<div class="loading">Loading insights</div>';
    statusBar.textContent = '';
    try {
      const res = await fetch('/insights?limit=20');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderInsights(data);
    } catch (err) {
      renderError(err.message);
    }
  }

  async function doSearch(q) {
    setLoading(true);
    try {
      const res = await fetch(`/search?q=${encodeURIComponent(q)}&limit=50`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderSearchResults(data.results, data.count);
      statusBar.textContent = `${data.count} result${data.count !== 1 ? 's' : ''} found`;
    } catch (err) {
      renderError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function doAsk(q) {
    setLoading(true);
    statusBar.textContent = 'Thinking...';
    try {
      const res = await fetch(`/ask?q=${encodeURIComponent(q)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderAskResponse(data);
      statusBar.textContent = `Answer generated from ${data.sources ? data.sources.length : 0} sources`;
    } catch (err) {
      renderError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function setLoading(on) {
    submitBtn.disabled = on;
    if (on) {
      results.innerHTML = '<div class="loading">Searching</div>';
    }
  }

  function renderSearchResults(items, count) {
    if (!items || items.length === 0) {
      results.innerHTML = `
        <div class="empty-state">
          <div class="icon">&#128269;</div>
          <p>No results found. Try a different query.</p>
        </div>`;
      return;
    }
    results.innerHTML = items.map(renderResultCard).join('');
  }

  function renderResultCard(r) {
    const ext = (r.type_subgroup || r.extension || '').toUpperCase();
    const group = r.type_group || 'other';
    const size = r.size != null ? formatSize(r.size) : '';
    const modified = r.modified_at ? formatDate(r.modified_at) : '';

    let audioPart = '';
    if (r.audio_metadata) {
      const am = r.audio_metadata;
      const parts = [];
      if (am.artist) parts.push(am.artist);
      if (am.album) parts.push(am.album);
      if (am.duration_seconds) parts.push(formatDuration(am.duration_seconds));
      if (parts.length) {
        audioPart = `<div class="result-audio-meta">${escHtml(parts.join(' — '))}</div>`;
      }
    }

    let snippetPart = '';
    if (r.snippet) {
      // snippet may contain <mark> tags — sanitize but preserve marks
      const safe = r.snippet
        .replace(/&/g, '&amp;')
        .replace(/<mark>/g, '\x00MARK\x00')
        .replace(/<\/mark>/g, '\x00ENDMARK\x00')
        .replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/\x00MARK\x00/g, '<mark>')
        .replace(/\x00ENDMARK\x00/g, '</mark>');
      snippetPart = `<div class="result-snippet">${safe}</div>`;
    }

    return `
      <div class="result-card">
        <div class="result-header">
          <div class="result-filename">${escHtml(r.filename)}</div>
          <div class="badges">
            ${ext ? `<span class="badge badge-${group}">${escHtml(ext)}</span>` : ''}
            <span class="badge badge-device">${escHtml(r.device_name || '')}</span>
          </div>
        </div>
        <div class="result-path">${escHtml(r.path)}</div>
        ${audioPart}
        <div class="result-meta">
          ${size ? `<span>${size}</span>` : ''}
          ${modified ? `<span>${modified}</span>` : ''}
        </div>
        ${snippetPart}
      </div>`;
  }

  function renderAskResponse(data) {
    const sources = data.sources || [];
    let sourcesHtml = '';
    if (sources.length) {
      const list = sources.map(s =>
        `<span>${escHtml(s.filename)}</span>`
      ).join(', ');
      sourcesHtml = `<div class="ask-sources">Sources: ${list}</div>`;
    }
    results.innerHTML = `
      <div class="ask-answer">${escHtml(data.answer || '')}</div>
      ${sourcesHtml}`;
  }

  function renderError(msg) {
    results.innerHTML = `<div class="error-banner">Error: ${escHtml(msg)}</div>`;
  }

  function renderInsights(data) {
    const sections = [];

    // Largest Files
    const lf = data.largest_files || [];
    sections.push(`
      <div class="insights-section">
        <h2 class="insights-title">Largest Files</h2>
        ${lf.length ? lf.map(r => `
          <div class="insights-row">
            <span class="insights-size">${formatSize(r.size || 0)}</span>
            <span class="insights-name">${escHtml(r.filename)}</span>
            <span class="insights-path">${escHtml(r.path)}</span>
          </div>`).join('') : '<p class="insights-empty">No data</p>'}
      </div>`);

    // Recently Added
    const rf = data.recent_files || [];
    sections.push(`
      <div class="insights-section">
        <h2 class="insights-title">Recently Added</h2>
        ${rf.length ? rf.map(r => `
          <div class="insights-row">
            <span class="insights-size">${r.created_at ? formatDate(r.created_at) : ''}</span>
            <span class="insights-name">${escHtml(r.filename)}</span>
            <span class="insights-path">${escHtml(r.path)}</span>
          </div>`).join('') : '<p class="insights-empty">No data</p>'}
      </div>`);

    // Duplicate Files
    const dups = data.duplicate_files || [];
    sections.push(`
      <div class="insights-section">
        <h2 class="insights-title">Duplicate Files</h2>
        ${dups.length ? dups.map(d => `
          <div class="insights-dup-group">
            <div class="insights-dup-header">
              <span class="insights-dup-copies">${d.copies} copies</span>
              <span class="insights-dup-hash">${escHtml(d.content_hash.slice(0, 16))}…</span>
              <span class="insights-dup-wasted">${formatSize(d.wasted_bytes || 0)} wasted</span>
            </div>
            ${(d.files || []).map(f => `
              <div class="insights-dup-file">${escHtml(f.path)}</div>`).join('')}
          </div>`).join('') : '<p class="insights-empty">No duplicates found</p>'}
      </div>`);

    // Largest Folders
    const folders = data.largest_folders || [];
    sections.push(`
      <div class="insights-section">
        <h2 class="insights-title">Largest Folders</h2>
        ${folders.length ? folders.map(r => `
          <div class="insights-row">
            <span class="insights-size">${formatSize(r.total_size || 0)}</span>
            <span class="insights-count">${r.file_count} files</span>
            <span class="insights-path">${escHtml(r.folder)}</span>
          </div>`).join('') : '<p class="insights-empty">No data</p>'}
      </div>`);

    results.innerHTML = `<div class="insights-grid">${sections.join('')}</div>`;
  }

  function escHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  function formatDate(unixTs) {
    return new Date(unixTs * 1000).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  }

  function formatDuration(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    if (m >= 60) {
      const h = Math.floor(m / 60);
      const mm = (m % 60).toString().padStart(2, '0');
      return `${h}:${mm}:${s}`;
    }
    return `${m}:${s}`;
  }
}());
