(function () {
  'use strict';

  let currentMode = 'search';
  let debounceTimer = null;
  let currentResults = [];
  let currentSort = 'relevance';
  let currentPage = 1;
  const PAGE_SIZE = 25;

  const form = document.getElementById('search-form');
  const input = document.getElementById('query-input');
  const submitBtn = document.getElementById('submit-btn');
  const results = document.getElementById('results');
  const statusBar = document.getElementById('status-bar');
  const modeButtons = document.querySelectorAll('.mode-btn');
  const sortBar = document.getElementById('sort-bar');

  // Sort bar
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentSort = btn.dataset.sort;
      currentPage = 1;
      document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderSearchResults(currentResults, currentResults.length);
    });
  });

  // Mode toggle
  modeButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      currentMode = btn.dataset.mode;
      modeButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const searchContainer = document.querySelector('.search-container');
      const quickFilters = document.getElementById('quick-filters');
      if (currentMode === 'insights') {
        searchContainer.style.display = 'none';
        sortBar.style.display = 'none';
        results.innerHTML = '';
        statusBar.textContent = '';
        doInsights();
      } else if (currentMode === 'scan') {
        searchContainer.style.display = 'none';
        sortBar.style.display = 'none';
        results.innerHTML = '';
        statusBar.textContent = '';
        doScanPanel();
      } else if (currentMode === 'audio') {
        searchContainer.style.display = 'none';
        sortBar.style.display = 'none';
        results.innerHTML = '';
        statusBar.textContent = '';
        doAudioPanel();
      } else {
        stopScanPoll();
        searchContainer.style.display = '';
        sortBar.style.display = 'none';
        quickFilters.style.display = currentMode === 'search' ? '' : 'none';
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

  // Quick filter chips
  document.querySelectorAll('.qf-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.query;
      // Switch to search mode if not already
      if (currentMode !== 'search') {
        document.getElementById('btn-search').click();
      }
      input.value = q;
      document.querySelectorAll('.qf-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      runQuery(q);
    });
  });

  // Clear active chip when user types manually
  input.addEventListener('keydown', () => {
    document.querySelectorAll('.qf-btn').forEach(b => b.classList.remove('active'));
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
    sortBar.style.display = 'none';
    try {
      const res = await fetch(`/search?q=${encodeURIComponent(q)}&limit=200`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentResults = data.results || [];
      currentSort = 'relevance';
      currentPage = 1;
      document.querySelectorAll('.sort-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.sort === 'relevance');
      });
      if (currentResults.length > 0) sortBar.style.display = '';
      renderSearchResults(currentResults, data.count);
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

  function sortedItems(items) {
    const arr = [...items];
    switch (currentSort) {
      case 'name':
        return arr.sort((a, b) => (a.filename || '').localeCompare(b.filename || ''));
      case 'size-desc':
        return arr.sort((a, b) => (b.size || 0) - (a.size || 0));
      case 'size-asc':
        return arr.sort((a, b) => (a.size || 0) - (b.size || 0));
      case 'date-desc':
        return arr.sort((a, b) => (b.modified_at || 0) - (a.modified_at || 0));
      case 'date-asc':
        return arr.sort((a, b) => (a.modified_at || 0) - (b.modified_at || 0));
      case 'type':
        return arr.sort((a, b) => {
          const ta = `${a.type_group || ''}/${a.type_subgroup || ''}`;
          const tb = `${b.type_group || ''}/${b.type_subgroup || ''}`;
          return ta.localeCompare(tb) || (a.filename || '').localeCompare(b.filename || '');
        });
      default: // relevance — original order
        return arr;
    }
  }

  function renderSearchResults(items, count) {
    if (!items || items.length === 0) {
      sortBar.style.display = 'none';
      results.innerHTML = `
        <div class="empty-state">
          <div class="icon">&#128269;</div>
          <p>No results found. Try a different query.</p>
        </div>`;
      return;
    }
    const sorted = sortedItems(items);
    const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
    currentPage = Math.min(currentPage, totalPages);
    const start = (currentPage - 1) * PAGE_SIZE;
    const pageItems = sorted.slice(start, start + PAGE_SIZE);

    const cards = pageItems.map(renderResultCard).join('');
    const paginationTop = totalPages > 1 ? renderPagination(currentPage, totalPages, sorted.length, true) : '';
    const paginationBot = totalPages > 1 ? renderPagination(currentPage, totalPages, sorted.length, false) : '';
    results.innerHTML = paginationTop + cards + paginationBot;
  }

  function renderPagination(page, totalPages, totalItems, isTop = false) {
    const start = (page - 1) * PAGE_SIZE + 1;
    const end = Math.min(page * PAGE_SIZE, totalItems);
    return `
      <div class="pagination${isTop ? ' pagination-top' : ''}">
        <button class="page-btn" onclick="window._goPage(${page - 1})" ${page <= 1 ? 'disabled' : ''}>&#8592; Prev</button>
        <span class="page-info">Page ${page} of ${totalPages} &nbsp;(${start}–${end} of ${totalItems})</span>
        <button class="page-btn" onclick="window._goPage(${page + 1})" ${page >= totalPages ? 'disabled' : ''}>Next &#8594;</button>
      </div>`;
  }

  window._goPage = function(page) {
    currentPage = page;
    renderSearchResults(currentResults, currentResults.length);
    document.getElementById('results-container').scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Reusable open buttons for any file or folder path
  function actionBtns(path, isFolder = false) {
    const enc = encodeURIComponent(path);
    const open = isFolder
      ? `<button class="result-action-btn" onclick="openPath('${enc}','folder')" title="Open folder">Open</button>`
      : `<button class="result-action-btn" onclick="openPath('${enc}','file')" title="Open file">Open</button>
         <button class="result-action-btn" onclick="openPath('${enc}','folder')" title="Open containing folder">Folder</button>`;
    return `<div class="result-actions" style="margin:0">${open}</div>`;
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

    const pathEnc = encodeURIComponent(r.path);
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
        <div class="result-actions">
          <button class="result-action-btn" onclick="openPath('${pathEnc}','file')" title="Open file">Open</button>
          <button class="result-action-btn" onclick="openPath('${pathEnc}','folder')" title="Open containing folder">Open Folder</button>
        </div>
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

  function insightsSection(id, title, icon, bodyHtml) {
    return `
      <div class="insights-section" id="isec-${id}">
        <button class="insights-section-header" onclick="
          var b = document.getElementById('isec-${id}');
          b.classList.toggle('collapsed');
        ">
          <span class="insights-section-icon">${icon}</span>
          <span class="insights-title">${title}</span>
          <span class="insights-chevron">&#8964;</span>
        </button>
        <div class="insights-section-body">${bodyHtml}</div>
      </div>`;
  }

  function renderInsights(data) {
    // Largest Files
    const lf = data.largest_files || [];
    const lfBody = lf.length ? `
      <table class="insights-table">
        <thead><tr><th>Size</th><th>Filename</th><th>Path</th><th></th></tr></thead>
        <tbody>${lf.map(r => `
          <tr>
            <td class="insights-td-size">${formatSize(r.size || 0)}</td>
            <td class="insights-td-name">${escHtml(r.filename)}</td>
            <td class="insights-td-path">${escHtml(r.path)}</td>
            <td class="insights-td-actions">${actionBtns(r.path)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '<p class="insights-empty">No data</p>';

    // Recently Added
    const rf = data.recent_files || [];
    const rfBody = rf.length ? `
      <table class="insights-table">
        <thead><tr><th>Date</th><th>Filename</th><th>Path</th><th></th></tr></thead>
        <tbody>${rf.map(r => `
          <tr>
            <td class="insights-td-size">${r.created_at ? formatDate(r.created_at) : ''}</td>
            <td class="insights-td-name">${escHtml(r.filename)}</td>
            <td class="insights-td-path">${escHtml(r.path)}</td>
            <td class="insights-td-actions">${actionBtns(r.path)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '<p class="insights-empty">No data</p>';

    // Duplicate Files
    const dups = data.duplicate_files || [];
    const dupsBody = dups.length ? dups.map(d => `
      <div class="insights-dup-group">
        <div class="insights-dup-header">
          <span class="insights-dup-copies">${d.copies} copies</span>
          <span class="insights-dup-hash">${escHtml(d.content_hash.slice(0, 16))}…</span>
          <span class="insights-dup-wasted">${formatSize(d.wasted_bytes || 0)} wasted</span>
        </div>
        ${(d.files || []).map(f => `
          <div class="insights-dup-file">${escHtml(f.path)} ${actionBtns(f.path)}</div>`).join('')}
      </div>`).join('') : '<p class="insights-empty">No duplicates found</p>';

    // Largest Folders
    const folders = data.largest_folders || [];
    const foldersBody = folders.length ? `
      <table class="insights-table">
        <thead><tr><th>Total Size</th><th>Files</th><th>Folder</th></tr></thead>
        <tbody>${folders.map(r => `
          <tr>
            <td class="insights-td-size">${formatSize(r.total_size || 0)}</td>
            <td class="insights-td-count">${r.file_count}</td>
            <td class="insights-td-path">${escHtml(r.folder)}</td>
            <td class="insights-td-actions">${actionBtns(r.folder, true)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '<p class="insights-empty">No data</p>';

    // Disk Growth (last 7 days)
    const growth = data.disk_growth || {};
    const growthDevices = growth.by_device || [];
    const growthFiles = growth.top_new_files || [];
    const growthBody = (growthDevices.length || growthFiles.length) ? `
      ${growthDevices.length ? `
      <table class="insights-table">
        <thead><tr><th>Device</th><th>New Files</th><th>New Data</th></tr></thead>
        <tbody>${growthDevices.map(r => `
          <tr>
            <td class="insights-td-name">${escHtml(r.device_name)}</td>
            <td class="insights-td-count">${r.file_count}</td>
            <td class="insights-td-size">${formatSize(r.total_size || 0)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : ''}
      ${growthFiles.length ? `
      <p style="margin:12px 0 4px;font-size:0.8rem;opacity:0.6">Largest new files</p>
      <table class="insights-table">
        <thead><tr><th>Size</th><th>Filename</th><th>Path</th></tr></thead>
        <tbody>${growthFiles.map(r => `
          <tr>
            <td class="insights-td-size">${formatSize(r.size || 0)}</td>
            <td class="insights-td-name">${escHtml(r.filename)}</td>
            <td class="insights-td-path">${escHtml(r.path)}</td>
            <td class="insights-td-actions">${actionBtns(r.path)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : ''}
    ` : `<p class="insights-empty">No new files in the last 7 days</p>`;

    // Cleanup Candidates
    const cleanup = data.cleanup_candidates || [];
    const cleanupBody = cleanup.length ? `
      <p class="insights-warning-note">Large files (&gt;100 MB) with no extension or temp-like names</p>
      <table class="insights-table">
        <thead><tr><th>Size</th><th>Filename</th><th>Path</th></tr></thead>
        <tbody>${cleanup.map(r => `
          <tr>
            <td class="insights-td-size">${formatSize(r.size || 0)}</td>
            <td class="insights-td-name insights-warning">${escHtml(r.filename)}</td>
            <td class="insights-td-path">${escHtml(r.path)}</td>
            <td class="insights-td-actions">${actionBtns(r.path)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '<p class="insights-empty">No suspicious files found</p>';

    results.innerHTML = `
      <div class="insights-stack">
        ${insightsSection('largest', 'Largest Files', '📦', lfBody)}
        ${insightsSection('growth', 'Disk Growth (Last 7 Days)', '📈', growthBody)}
        ${insightsSection('recent', 'Recently Added', '🕐', rfBody)}
        ${insightsSection('dupes', 'Duplicate Files', '🗂', dupsBody)}
        ${insightsSection('folders', 'Largest Folders', '📁', foldersBody)}
        ${insightsSection('cleanup', 'Cleanup Candidates', '⚠️', cleanupBody)}
      </div>`;
  }

  // ── Scan panel ──────────────────────────────────────────────────────────────
  let _scanPollTimer = null;
  let _scanPaths = [];

  async function doScanPanel() {
    stopScanPoll();
    const [statsRes, statusRes] = await Promise.all([
      fetch('/scan/stats').then(r => r.json()).catch(() => null),
      fetch('/scan/status').then(r => r.json()).catch(() => ({})),
    ]);
    _scanPaths = statusRes.paths && statusRes.paths.length ? statusRes.paths : [];
    renderScanPanel(statsRes, statusRes);
    if (statusRes.state === 'running') startScanPoll();
  }

  function renderScanPanel(stats, status) {
    const typeIcons = { audio:'🎵', video:'🎬', image:'🖼', document:'📄', code:'💻', archive:'📦', data:'🗄', other:'📁' };

    const statsHtml = stats ? `
      <div class="scan-stats-grid">
        <div class="scan-stat-card">
          <div class="scan-stat-value">${stats.total_files.toLocaleString()}</div>
          <div class="scan-stat-label">Total Files</div>
        </div>
        <div class="scan-stat-card">
          <div class="scan-stat-value">${formatSize(stats.total_size || 0)}</div>
          <div class="scan-stat-label">Total Size</div>
        </div>
        <div class="scan-stat-card">
          <div class="scan-stat-value">${stats.last_indexed ? formatDate(stats.last_indexed) : '—'}</div>
          <div class="scan-stat-label">Last Indexed</div>
        </div>
      </div>
      <div class="scan-type-chips">${(stats.by_type || []).map(t =>
        `<span class="scan-type-chip badge badge-${t.type_group}">${typeIcons[t.type_group] || '📁'} ${t.type_group} <span class="scan-type-count">${t.count.toLocaleString()}</span></span>`
      ).join('')}</div>` : '';

    const isRunning = status.state === 'running';
    const isDone    = status.state === 'done';
    const isError   = status.state === 'error';

    let progressHtml = '';
    if (isRunning) {
      progressHtml = `
        <div class="scan-progress">
          <div class="scan-progress-bar"><div class="scan-progress-fill"></div></div>
          <div class="scan-progress-stats">
            <span class="scan-p-indexed">${(status.files_indexed || 0).toLocaleString()} indexed</span>
            <span class="scan-p-skipped">${(status.files_skipped || 0).toLocaleString()} skipped</span>
            ${status.current_path ? `<span class="scan-p-path">${escHtml(status.current_path)}</span>` : ''}
          </div>
        </div>`;
    } else if (isDone) {
      const elapsed = status.finished_at && status.started_at ? ((status.finished_at - status.started_at)).toFixed(0) : '';
      const errPart = status.files_errored ? `, ${status.files_errored} errors` : '';
      progressHtml = `<div class="scan-done">✓ Scan complete — ${(status.files_indexed || 0).toLocaleString()} indexed, ${(status.files_skipped || 0).toLocaleString()} skipped${errPart}${elapsed ? ` in ${elapsed}s` : ''}</div>`;
    } else if (isError) {
      progressHtml = `<div class="scan-error">✗ Scan failed: ${escHtml(status.error || 'unknown error')}</div>`;
    }

    results.innerHTML = `
      <div class="scan-panel">
        <div class="scan-section">
          <h2 class="scan-section-title">📊 Catalogue</h2>
          ${statsHtml || '<p class="scan-empty">No files indexed yet.</p>'}
        </div>

        <div class="scan-section">
          <h2 class="scan-section-title">📂 Paths to Scan</h2>
          <div id="scan-path-list">${renderPathList()}</div>
          <div class="scan-add-row">
            <input id="scan-path-input" class="scan-path-input" type="text" placeholder="/path/to/directory">
            <button class="scan-browse-btn" onclick="window._fbOpen()">Browse…</button>
            <button class="scan-add-btn" onclick="window._scanAddPath()">Add</button>
          </div>
        </div>

        ${progressHtml ? `<div class="scan-section">${progressHtml}</div>` : ''}

        <div class="scan-actions">
          <button class="scan-start-btn ${isRunning ? 'scan-running' : ''}" id="scan-start-btn"
            onclick="window._scanStart()" ${isRunning ? 'disabled' : ''}>
            ${isRunning ? '⏳ Scanning…' : '▶ Start Scan'}
          </button>
          <label class="scan-force-label">
            <input type="checkbox" id="scan-force"> Force re-index all files
          </label>
        </div>
      </div>`;

    // Re-attach enter key on path input
    const pathInput = document.getElementById('scan-path-input');
    if (pathInput) {
      pathInput.addEventListener('keydown', e => { if (e.key === 'Enter') window._scanAddPath(); });
    }
  }

  function renderPathList() {
    if (!_scanPaths.length) return '<p class="scan-empty">No paths added.</p>';
    return _scanPaths.map((p, i) => `
      <div class="scan-path-row">
        <span class="scan-path-text">${escHtml(p)}</span>
        <button class="scan-path-remove" onclick="window._scanRemovePath(${i})">✕</button>
      </div>`).join('');
  }

  window._scanAddPath = function() {
    const input = document.getElementById('scan-path-input');
    const val = (input?.value || '').trim();
    if (!val || _scanPaths.includes(val)) { if (input) input.value = ''; return; }
    _scanPaths.push(val);
    if (input) input.value = '';
    const list = document.getElementById('scan-path-list');
    if (list) list.innerHTML = renderPathList();
  };

  window._scanRemovePath = function(idx) {
    _scanPaths.splice(idx, 1);
    const list = document.getElementById('scan-path-list');
    if (list) list.innerHTML = renderPathList();
  };

  window._scanStart = async function() {
    if (!_scanPaths.length) {
      alert('Add at least one path to scan.');
      return;
    }
    const force = document.getElementById('scan-force')?.checked || false;
    const btn = document.getElementById('scan-start-btn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Scanning…'; btn.classList.add('scan-running'); }
    try {
      const res = await fetch('/scan/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: _scanPaths, force }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      startScanPoll();
    } catch (e) {
      alert(`Failed to start scan: ${e.message}`);
      if (btn) { btn.disabled = false; btn.textContent = '▶ Start Scan'; btn.classList.remove('scan-running'); }
    }
  };

  function startScanPoll() {
    stopScanPoll();
    _scanPollTimer = setInterval(async () => {
      if (currentMode !== 'scan') { stopScanPoll(); return; }
      try {
        const [statusRes, statsRes] = await Promise.all([
          fetch('/scan/status').then(r => r.json()),
          fetch('/scan/stats').then(r => r.json()).catch(() => null),
        ]);
        renderScanPanel(statsRes, statusRes);
        if (statusRes.state !== 'running') stopScanPoll();
      } catch (_) {}
    }, 1500);
  }

  function stopScanPoll() {
    if (_scanPollTimer) { clearInterval(_scanPollTimer); _scanPollTimer = null; }
  }

  // ── File browser modal ──────────────────────────────────────────────────────
  let _fbCurrentPath = '/';

  window._fbOpen = function(startPath) {
    _fbCurrentPath = startPath || document.getElementById('scan-path-input')?.value.trim() || '/home';
    document.getElementById('fb-overlay').style.display = 'flex';
    _fbNavigate(_fbCurrentPath);
  };

  window._fbClose = function() {
    document.getElementById('fb-overlay').style.display = 'none';
  };

  window._fbSelect = function() {
    const input = document.getElementById('scan-path-input');
    if (input) input.value = _fbCurrentPath;
    window._fbClose();
  };

  window._fbNavigate = async function(path) {
    _fbCurrentPath = path;
    const list = document.getElementById('fb-list');
    const crumbs = document.getElementById('fb-breadcrumbs');
    const currentPathEl = document.getElementById('fb-current-path');
    list.innerHTML = '<div class="fb-loading">Loading…</div>';

    try {
      const res = await fetch(`/fs/browse?path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
      const data = await res.json();
      _fbCurrentPath = data.path;

      // Breadcrumbs
      crumbs.innerHTML = data.breadcrumbs.map((c, i) =>
        `<button class="fb-crumb ${i === data.breadcrumbs.length - 1 ? 'fb-crumb-active' : ''}"
          onclick="window._fbNavigate(${JSON.stringify(c.path)})">${escHtml(c.name)}</button>`
      ).join('<span class="fb-crumb-sep">›</span>');

      // Directory list
      if (data.parent) {
        list.innerHTML = `<div class="fb-entry fb-entry-up" onclick="window._fbNavigate(${JSON.stringify(data.parent)})">
          <span class="fb-entry-icon">⬆</span><span class="fb-entry-name">..</span>
        </div>`;
      } else {
        list.innerHTML = '';
      }

      if (data.entries.length === 0) {
        list.innerHTML += '<div class="fb-empty">No subdirectories</div>';
      } else {
        list.innerHTML += data.entries.map(e =>
          `<div class="fb-entry" onclick="window._fbNavigate(${JSON.stringify(e.path)})">
            <span class="fb-entry-icon">📁</span>
            <span class="fb-entry-name">${escHtml(e.name)}</span>
          </div>`
        ).join('');
      }

      if (currentPathEl) currentPathEl.textContent = data.path;

    } catch (err) {
      list.innerHTML = `<div class="fb-error">${escHtml(err.message)}</div>`;
    }
  };

  // ── Audio panel ─────────────────────────────────────────────────────────────

  async function doAudioPanel() {
    results.innerHTML = '<div class="loading">Loading audio insights…</div>';
    try {
      const [healthRes, cleanupRes] = await Promise.all([
        fetch('/audio/health?limit=100'),
        fetch('/audio/cleanup?limit=50'),
      ]);
      if (!healthRes.ok || !cleanupRes.ok) throw new Error('Failed to load audio data');
      const health = await healthRes.json();
      const cleanup = await cleanupRes.json();
      renderAudioPanel(health, cleanup);
    } catch (err) {
      renderError(err.message);
    }
  }

  function renderAudioPanel(health, cleanup) {
    const s = health.summary || {};
    const dupes = cleanup.duplicate_tracks || [];
    const artists = cleanup.inconsistent_artists || [];

    // Summary cards
    const statsHtml = `
      <div class="scan-stats-grid" style="margin-bottom:20px">
        <div class="scan-stat-card"><div class="scan-stat-val">${s.total_audio || 0}</div><div class="scan-stat-label">Total Audio Files</div></div>
        <div class="scan-stat-card"><div class="scan-stat-val">${s.missing_artist || 0}</div><div class="scan-stat-label">Missing Artist</div></div>
        <div class="scan-stat-card"><div class="scan-stat-val">${s.missing_album || 0}</div><div class="scan-stat-label">Missing Album</div></div>
        <div class="scan-stat-card"><div class="scan-stat-val">${s.missing_title || 0}</div><div class="scan-stat-label">Missing Title</div></div>
        <div class="scan-stat-card"><div class="scan-stat-val">${(health.generic_titles || []).length}</div><div class="scan-stat-label">Generic Titles</div></div>
        <div class="scan-stat-card"><div class="scan-stat-val">${dupes.length}</div><div class="scan-stat-label">Duplicate Groups</div></div>
      </div>`;

    // Missing artist files
    const maBody = renderAudioFileTable(health.missing_artist || [], true);
    // Missing album
    const malBody = renderAudioFileTable(health.missing_album || [], true);
    // Generic titles
    const gtBody = renderAudioFileTable(health.generic_titles || [], true);
    // Duplicates
    const dupBody = dupes.length ? dupes.map(d => `
      <div class="insights-dup-group">
        <div class="insights-dup-header">
          <span class="insights-dup-copies">${d.copies} copies</span>
          <span class="insights-dup-hash">${escHtml(d.content_hash.slice(0,16))}…</span>
        </div>
        ${(d.paths || []).map(p => `<div class="insights-dup-file">${escHtml(p.path)} ${actionBtns(p.path)}</div>`).join('')}
      </div>`).join('') : '<p class="insights-empty">No duplicates found</p>';

    // Inconsistent artists
    const artistBody = artists.length ? `
      <table class="insights-table">
        <thead><tr><th>Variants</th><th>Artist Names Found</th></tr></thead>
        <tbody>${artists.map(a => `
          <tr>
            <td class="insights-td-count">${a.variants}</td>
            <td class="insights-td-name">${escHtml(a.artist_list || '')}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '<p class="insights-empty">No inconsistencies found</p>';

    results.innerHTML = `
      <div class="insights-stack">
        ${statsHtml}
        ${insightsSection('au-missing-artist', 'Missing Artist', '🎤', maBody)}
        ${insightsSection('au-missing-album', 'Missing Album', '💿', malBody)}
        ${insightsSection('au-generic-titles', 'Generic Titles', '🏷️', gtBody)}
        ${insightsSection('au-dupes', 'Duplicate Tracks', '♊', dupBody)}
        ${insightsSection('au-artists', 'Inconsistent Artist Names', '⚠️', artistBody)}
      </div>`;
  }

  function renderAudioFileTable(files, showEditBtn) {
    if (!files.length) return '<p class="insights-empty">None found</p>';
    return `
      <table class="insights-table">
        <thead><tr><th>Filename</th><th>Path</th><th></th></tr></thead>
        <tbody>${files.map(r => `
          <tr>
            <td class="insights-td-name">${escHtml(r.filename)}</td>
            <td class="insights-td-path">${escHtml(r.path)}</td>
            <td class="insights-td-actions">
              ${actionBtns(r.path)}
              ${showEditBtn ? `<button class="result-action-btn" onclick='window._teOpen(${JSON.stringify(r.path)})'>Edit Tags</button>` : ''}
            </td>
          </tr>`).join('')}
        </tbody>
      </table>`;
  }

  // ── Tag editor modal ─────────────────────────────────────────────────────────

  window._teOpen = function(path) {
    document.getElementById('te-path').value = path;
    document.getElementById('te-artist').value = '';
    document.getElementById('te-album').value = '';
    document.getElementById('te-title').value = '';
    document.getElementById('te-year').value = '';
    document.getElementById('te-status').textContent = path;
    document.getElementById('te-save-btn').disabled = false;
    document.getElementById('te-overlay').style.display = 'flex';
  };

  window._teClose = function() {
    document.getElementById('te-overlay').style.display = 'none';
  };

  window._teSave = async function() {
    const path = document.getElementById('te-path').value;
    const artist = document.getElementById('te-artist').value.trim();
    const album = document.getElementById('te-album').value.trim();
    const title = document.getElementById('te-title').value.trim();
    const year = document.getElementById('te-year').value.trim();
    const status = document.getElementById('te-status');
    const btn = document.getElementById('te-save-btn');

    const body = { path };
    if (artist) body.artist = artist;
    if (album) body.album = album;
    if (title) body.title = title;
    if (year) body.year = parseInt(year);

    btn.disabled = true;
    status.textContent = 'Saving…';
    try {
      const res = await fetch('/audio/update_tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const d = await res.json();
        status.style.color = '#ef4444';
        status.textContent = 'Error: ' + (d.detail || res.status);
        btn.disabled = false;
      } else {
        status.style.color = '#22c55e';
        status.textContent = 'Tags saved successfully';
        setTimeout(() => window._teClose(), 1200);
      }
    } catch (err) {
      status.style.color = '#ef4444';
      status.textContent = 'Error: ' + err.message;
      btn.disabled = false;
    }
  };

  window.openPath = async function(encodedPath, action) {
    const path = decodeURIComponent(encodedPath);
    try {
      const res = await fetch(`/open?path=${encodeURIComponent(path)}&action=${action}`);
      if (!res.ok) {
        const d = await res.json();
        alert('Could not open: ' + (d.detail || res.status));
      }
    } catch (err) {
      alert('Error: ' + err.message);
    }
  };

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
