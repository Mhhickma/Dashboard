// Explicit checkbox selections only. Local service owns timing and publication.
(function () {
  var base = 'http://127.0.0.1:8766';
  var items = [];
  var cacheKey = 'dashboard-posting-queue-cache';
  var lastUpdated = 0;
  var busy = new Set();
  var appliedHidden = new Set();
  var pendingRefresh = false;
  var lastError = '';
  var alreadyPosted = new Set();
  var panel = document.createElement('section');
  panel.className = 'engagement-posts';
  panel.style.display = 'block';
  var heading = document.createElement('h2');
  heading.textContent = 'Selected posting queue';
  var explanation = document.createElement('p');
  explanation.textContent = 'Selecting a deal prepares and saves its JoyLink. The first deal posts when ready; additional deals follow 30–60 minutes apart. Uncheck to cancel.';
  var status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.style.cssText = 'padding:14px 18px;border-radius:12px;border:2px solid;font-size:20px;font-weight:700;line-height:1.4;margin:14px 0;';
  function showStatus(message) {
    var ready = message.indexOf('Queue ready.') === 0;
    status.textContent = message;
    status.style.setProperty('background-color', ready ? '#dcfce7' : '#fff7ed', 'important');
    status.style.setProperty('color', ready ? '#166534' : '#9a3412', 'important');
    status.style.borderColor = ready ? '#22c55e' : '#fb923c';
  }
  var list = document.createElement('ul');
  panel.append(heading, explanation, status, list);
  var container = document.querySelector('main');
  if (!container || typeof window.toggleSelectedForPosting !== 'function') return;
  container.prepend(panel);
  var ccPanel = document.createElement('details');
  var ccHeading = document.createElement('summary');
  ccHeading.textContent = 'CC watchlist — selected products';
  var ccStatus = document.createElement('p');
  var ccList = document.createElement('div');
  ccPanel.append(ccHeading, ccStatus, ccList);
  panel.append(ccPanel);
  var ccItems = [];
  function campaignText(c) {
    return c.status + ' · ' + (c.accepted === true ? 'Accepted in your CSV history' : c.accepted === false ? 'Not in accepted history' : 'Acceptance unknown') + ' · ' + (c.commission || 'Rate unknown') + ' · Ends ' + (c.end || 'unknown');
  }
  function ccContent(target, item) {
    target.replaceChildren();
    if (!item.campaigns.length) { target.textContent = 'CC: No campaign found in latest CSV.'; return; }
    item.campaigns.forEach(function (c) {
      var line = document.createElement('p');
      line.append(document.createTextNode('CC: ' + campaignText(c) + ' '));
      var link = document.createElement('a');
      link.textContent = 'Open campaign'; link.href = c.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      line.append(link); target.append(line);
    });
  }
  function paintCC() {
    ccItems.forEach(function (item) {
      var card = cardFor(item.asin); if (!card) return;
      var box = card.querySelector('.posting-cc-status');
      if (!box) { box = document.createElement('div'); box.className = 'posting-cc-status'; box.style.cssText = 'padding:12px;border:1px solid #94a3b8;border-radius:12px;margin:10px;'; card.append(box); }
      ccContent(box, item);
    });
  }
  async function refreshCC() {
    try {
      var data = await request('/cc-monitor');
      ccItems = data.items || [];
      ccStatus.textContent = data.message + (data.cc_updated ? ' CC upload: ' + data.cc_updated + '. Accepted upload: ' + (data.accepted_updated || 'unknown') + '.' : '');
      document.querySelectorAll('.posting-cc-status').forEach(function (box) { box.remove(); });
      ccList.replaceChildren();
      ccItems.forEach(function (item) {
        var row = document.createElement('div'); var title = document.createElement('strong');
        title.textContent = item.title + ' (' + item.asin + ')';
        var detail = document.createElement('div'); ccContent(detail, item); row.append(title, detail); ccList.append(row);
      });
      paintCC();
    } catch (_) { ccStatus.textContent = 'CC check offline. Campaign status is not verified.'; ccItems = []; document.querySelectorAll('.posting-cc-status').forEach(function (box) { box.remove(); }); ccList.replaceChildren(); }
  }

  async function request(path, body) {
    var options = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
    var response = await fetch(base + path, options);
    var result = await response.json();
    if (!response.ok) { var error = new Error(result.error || 'Queue request failed.'); error.code = result.code; throw error; }
    return result;
  }
  function cardFor(asin) {
    return Array.from(document.querySelectorAll('article')).find(function (card) {
      var label = card.querySelector('.asin');
      return label && label.textContent.trim() === 'ASIN: ' + asin;
    });
  }
  function timeLabel(value) {
    return new Date(value * 1000).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' Eastern';
  }
  function paint() {
    paintCC();
    alreadyPosted.forEach(function (asin) {
      var card = cardFor(asin);
      if (!card) return;
      var checkbox = card.querySelector('.select-posting-control input');
      var label = card.querySelector('.select-posting-control span');
      if (checkbox) { checkbox.checked = false; checkbox.disabled = true; }
      if (label) label.textContent = 'Already posted';
    });
    items.forEach(function (item) {
      var card = cardFor(item.asin);
      if (!card) return;
      var checkbox = card.querySelector('.select-posting-control input');
      var label = card.querySelector('.select-posting-control span');
      if (!checkbox || !label) return;
      if (!busy.has(item.asin)) checkbox.checked = ['queued', 'running', 'failed', 'needs_review'].includes(item.state);
      checkbox.disabled = ['running','needs_review'].includes(item.state) || busy.has(item.asin);
      if (item.state === 'queued') label.textContent = (item.link_ready ? 'Link saved — scheduled: ' : 'Preparing link — scheduled: ') + timeLabel(item.due);
      else if (item.state === 'running') label.textContent = 'Posting now';
      else if (item.state === 'needs_review') label.textContent = 'Needs review — other posts continue';
      else if (item.state === 'failed') label.textContent = 'Needs attention — queue paused';
      else label.textContent = 'Select for posting';
    });
  }
  function offlineMessage() {
    return lastUpdated ? 'Queue connection offline. Showing the last saved queue from ' + timeLabel(lastUpdated / 1000) + '. Status may have changed.' : 'Posting queue offline. Run Start Posting Queue.cmd before selecting deals.';
  }
  function sync(result, cached) {
    items = result.items || [];
    if (!cached) {
      lastUpdated = Date.now();
      try { localStorage.setItem(cacheKey, JSON.stringify({items:items, updated:lastUpdated})); } catch (_) {}
    }
    showStatus(lastError || (items.some(function (i) { return i.state === 'failed'; }) ? 'Queue paused: a posting attempt needs review.' : 'Queue ready. ' + (items.filter(function(i){return i.state === 'needs_review';}).length ? 'Some deals need review; other queued posts continue. ' : '') + 'Keep this PC awake and signed into Windows.'));
    list.replaceChildren();
    items.filter(function (i) { return ['queued', 'running', 'failed', 'needs_review'].includes(i.state); }).forEach(function (item) {
      var row = document.createElement('li');
      row.textContent = (item.title || item.asin) + ' — ' + (item.state === 'queued' ? (item.link_ready ? 'Link saved — ' : 'Preparing link — ') + timeLabel(item.due) : item.state === 'running' ? 'Posting now' : item.state === 'needs_review' ? 'Needs review — other posts continue. ' + String(item.error || '').split('\n')[0].slice(0,180) : item.error || 'Needs review');
      list.append(row);
    });
    if (!list.children.length) { var empty = document.createElement('li'); empty.textContent = 'No waiting posts.'; list.append(empty); }
    if (cached) { showStatus(offlineMessage()); return; }
    var selected = selectedForPostingAsins();
    var changed = false;
    items.forEach(function (item) {
      var active = ['queued', 'running', 'failed', 'needs_review'].includes(item.state);
      if (active && !selected.has(item.asin)) { selected.add(item.asin); changed = true; }
      if (!active && selected.has(item.asin)) { selected.delete(item.asin); changed = true; }
    });
    if (changed) { writeSelectedForPostingAsins(selected); applySearch(false); }
    items.filter(function (i) { return i.state === 'complete'; }).forEach(function (item) {
      if (!appliedHidden.has(item.asin) && cardFor(item.asin)) {
        appliedHidden.add(item.asin);
        hideDeal(item.asin);
      }
    });
    paint();
  }
  window.toggleSelectedForPosting = async function (asin) {
    if (busy.has(asin)) return;
    var item = items.find(function (i) { return i.asin === asin; });
    var cancelling = item && ['queued', 'running', 'failed', 'needs_review'].includes(item.state);
    var card = cardFor(asin);
    busy.add(asin);
    paint();
    try {
      lastError = '';
      if (cancelling) {
        sync(await request('/cancel', { asin: asin }));
      } else {
        if (!card) throw new Error('Selected product card is unavailable.');
        var title = card.querySelector('h2,h3');
        var preview = card.querySelector('.facebook-post-preview');
        var input = card.querySelector('.facebook-caption-input');
        var amazon = card.querySelector('a[href*="amazon.com/dp/"]');
        if (!title || !preview || !amazon) throw new Error('Product caption or link is missing.');
        var rating = card.dataset.rating ? Number(card.dataset.rating) : NaN;
        sync(await request('/queue', { asin: asin, title: title.textContent.trim(), text: (input && input.value.trim()) || preview.textContent.trim(), amazon: amazon.href, tier: 'selected', rating: rating }));
        ccStatus.textContent = 'Checking CC for ' + asin + '…';
        refreshCC();
      }
    } catch (error) {
      if (error.code === 'already_posted') alreadyPosted.add(asin);
      lastError = 'Not scheduled: ' + error.message;
      if (error instanceof TypeError) lastError += ' Check that the posting queue is running and Chrome allows local-network access.';
      showStatus(lastError);
      var checkbox = card && card.querySelector('.select-posting-control input');
      if (checkbox) checkbox.checked = !!cancelling;
    } finally { busy.delete(asin); paint(); }
  };
  async function refresh() {
    if (pendingRefresh) return;
    pendingRefresh = true;
    try { sync(await request('/queue')); }
    catch (_) { showStatus(offlineMessage()); }
    finally { pendingRefresh = false; }
  }
  new MutationObserver(function () { paint(); }).observe(document.getElementById('cards'), { childList: true });
  var selectedCards = document.getElementById('selectedCards');
  if (selectedCards) new MutationObserver(function () { paint(); }).observe(selectedCards, { childList: true });
  try {
    var savedQueue = JSON.parse(localStorage.getItem(cacheKey) || 'null');
    if (savedQueue && Array.isArray(savedQueue.items)) {
      lastUpdated = savedQueue.updated || 0;
      sync({items:savedQueue.items}, true);
    }
  } catch (_) {}
  refresh();
  refreshCC();
  window.setInterval(refreshCC, 20000);
  window.setInterval(refresh, 15000);
}());
