// 爬虫任务前端逻辑：提交任务、轮询进度、展示结果。
(function (window) {
  let currentTaskId = null;
  let pollTimer = null;

  function parseKeywords(raw) {
    if (!raw) return [];
    return raw
      .split(/[\n,，]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function setProgress(percent, statusText) {
    const bar = document.getElementById('spider-progress');
    const badge = document.getElementById('status-badge');
    const value = Math.max(0, Math.min(100, percent || 0));
    if (bar) {
      bar.style.width = `${value}%`;
      bar.textContent = `${value}%`;
    }
    if (badge && statusText) {
      badge.textContent = statusText;
      badge.className = 'badge ' + (statusText === 'running' ? 'bg-success' : 'bg-secondary');
    }
  }

  function setLogs(lines) {
    const box = document.getElementById('spider-logs');
    if (!box) return;
    if (!lines || !lines.length) {
      box.textContent = '暂无日志';
      return;
    }
    box.textContent = lines.join('\n');
  }

  function renderTable(list) {
    const tbody = document.getElementById('spider-table-body');
    const counter = document.getElementById('result-count');
    if (counter) counter.textContent = `${(list || []).length} 条`;
    if (!tbody) return;
    if (!list || !list.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">暂无数据</td></tr>';
      return;
    }
    const rows = list
      .slice(0, 200) // 避免表格一次性过大
      .map(
        (item) => `
      <tr>
        <td><a href="${window.buildPlayUrl(item.bvid)}" target="_blank">${item.bvid}</a></td>
        <td>${item.title || '-'}</td>
        <td>${item.up_name || '-'}</td>
        <td>${window.formatCount(item.view_count)}</td>
        <td>${window.formatCount(item.favorite_count)}</td>
        <td>${item.tags || '-'}</td>
        <td>${item.subject || item.category || '-'}</td>
      </tr>`
      )
      .join('');
    tbody.innerHTML = rows;
  }

  function disableForm(disabled) {
    const startBtn = document.getElementById('btn-start');
    const cancelBtn = document.getElementById('btn-cancel');
    if (startBtn) startBtn.disabled = disabled;
    if (cancelBtn) cancelBtn.disabled = !disabled;
  }

  async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`请求失败: ${res.status}`);
    return res.json();
  }

  async function submitTask(event) {
    event.preventDefault();
    const rawKeywords = document.getElementById('input-keywords').value;
    const pages = parseInt(document.getElementById('input-pages').value, 10) || 3;
    const save = document.getElementById('input-save').checked;
    const keywords = parseKeywords(rawKeywords);

    const params = { max_pages: pages, save };
    if (keywords.length) {
      params.tasks = keywords.map((k) => ({ q: k, keyword: k, phase: '', subject: '' }));
    }

    disableForm(true);
    setProgress(0, 'running');
    setLogs(['任务创建中...']);
    document.getElementById('current-task-label').textContent = '';

    try {
      const data = await fetchJSON('/api/spider/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      currentTaskId = data.task_id;
      document.getElementById('current-task-label').textContent = `当前任务: ${currentTaskId}`;
      startPolling();
    } catch (err) {
      disableForm(false);
      setLogs([`创建任务失败: ${err.message}`]);
      setProgress(0, 'idle');
    }
  }

  async function cancelTask() {
    if (!currentTaskId) return;
    try {
      await fetchJSON(`/api/spider/tasks/${currentTaskId}/cancel`, { method: 'POST' });
    } catch (err) {
      setLogs([`取消失败: ${err.message}`]);
    }
  }

  async function pollTask() {
    if (!currentTaskId) return;
    try {
      const data = await fetchJSON(`/api/spider/tasks/${currentTaskId}`);
      setProgress(data.progress || 0, data.status || 'running');
      setLogs(data.logs || []);
      if (['succeeded', 'failed', 'cancelled'].includes(data.status)) {
        clearInterval(pollTimer);
        pollTimer = null;
        disableForm(false);
        if (data.status === 'succeeded') {
          const res = await fetchJSON(`/api/spider/tasks/${currentTaskId}/data`);
          renderTable(res.data || []);
        }
      }
    } catch (err) {
      clearInterval(pollTimer);
      pollTimer = null;
      disableForm(false);
      setLogs([`轮询失败: ${err.message}`]);
      setProgress(0, 'idle');
    }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTask();
    pollTimer = setInterval(pollTask, 2500);
  }

  function initSpiderPage() {
    const form = document.getElementById('spider-form');
    if (form) form.addEventListener('submit', submitTask);
    const cancelBtn = document.getElementById('btn-cancel');
    if (cancelBtn) cancelBtn.addEventListener('click', cancelTask);
    setProgress(0, 'idle');
  }

  window.initSpiderPage = initSpiderPage;
})(window);
