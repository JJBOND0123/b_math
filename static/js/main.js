// Shared helpers used across templates to keep naming aligned with backend fields.
(function (window) {
  function zeroPad(num) {
    return num < 10 ? '0' + num : String(num);
  }

  window.formatCount = function (num) {
    const value = Number(num) || 0;
    if (value >= 100000000) return (value / 100000000).toFixed(2) + '\u4ebf';
    if (value >= 10000) return (value / 10000).toFixed(1) + '\u4e07';
    return value.toLocaleString();
  };

  window.formatDuration = function (seconds) {
    const total = Math.max(0, parseInt(seconds || 0, 10));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return h > 0 ? `${h}:${zeroPad(m)}:${zeroPad(s)}` : `${m}:${zeroPad(s)}`;
  };

  window.buildPlayUrl = function (bvid) {
    return bvid ? `https://www.bilibili.com/video/${bvid}` : '#';
  };

  window.logHistory = function (bvid) {
    if (!bvid) return;
    const payload = JSON.stringify({ bvid });

    // Prefer sendBeacon/keepalive so logging still succeeds when navigating away
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      navigator.sendBeacon('/api/log_history', blob);
      return;
    }

    if (window.fetch) {
      fetch('/api/log_history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true
      }).catch(() => {});
      return;
    }

    if (window.$) {
      $.ajax({
        url: '/api/log_history',
        type: 'POST',
        contentType: 'application/json',
        data: payload
      });
    }
  };
})(window);
