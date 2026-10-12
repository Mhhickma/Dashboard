// Explicit checkbox selections only. Local service owns timing and publication.
(function () {
  var base = 'http://127.0.0.1:8766';
  var items = [];
  var busy = new Set();
  var appliedHidden = new Set();
  var pendingRefresh = false;
  var panel = document.createElement('section');
  panel.className = 'engagement-posts';
  panel.style.display = 'block';
  var heading = document.createElement('h2');
  heading.textContent = 'Selected posting queue';
  var explanation = document.createElement('p');
  explanation.textContent = 'First deal posts now. Each additional deal follows 30–60 minutes later at a random interval. Uncheck to cancel.';
  var status = document.createElement('p');
  var list = document.createElement('ul');
  panel.append(heading, explanation, status, list);
  var container = document.querySelector('main');
  if (!container || typeof window.toggleSelectedForPosting !== 'function') return;
  container.prepend(panel);

  async function request(path, body) {
    var options = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
    var response = await fetch(base + path, options);
    var result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Queue request failed.');
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
    items.forEach(function (item) {
      var card = cardFor(item.asin);
      if (!card) return;
      var checkbox = card.querySelector('.select-posting-control input');
      var label = card.querySelector('.select-posting-control span');
      if (!checkbox || !label) return;
      if (!busy.has(item.asin)) checkbox.checked = ['queued', 'running', 'failed'].includes(item.state);
      checkbox.disabled = item.state === 'running' || busy.has(item.asin);
      if (item.state === 'queued') label.textContent = 'Scheduled: ' + timeLabel(item.due);
      else if (item.state === 'running') label.textContent = 'Posting now';
      else if (item.state === 'failed') label.textContent = 'Needs attention — queue paused';
      else label.textContent = 'Select for posting';
    });
  }
  function sync(result) {
    items = result.items || [];
    status.textContent = items.some(function (i) { return i.state === 'failed'; }) ? 'Queue paused: a posting attempt needs review.' : 'Queue ready. Keep this PC awake and signed into Windows.';
    list.replaceChildren();
    items.filter(function (i) { return ['queued', 'running', 'failed'].includes(i.state); }).forEach(function (item) {
      var row = document.createElement('li');
      row.textContent = (item.title || item.asin) + ' — ' + (item.state === 'queued' ? timeLabel(item.due) : item.state === 'running' ? 'Posting now' : item.error || 'Needs review');
      list.append(row);
    });
    var selected = selectedForPostingAsins();
    var changed = false;
    items.forEach(function (item) {
      var active = ['queued', 'running', 'failed'].includes(item.state);
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
    var cancelling = item && ['queued', 'running', 'failed'].includes(item.state);
    var card = cardFor(asin);
    busy.add(asin);
    paint();
    try {
      if (cancelling) {
        sync(await request('/cancel', { asin: asin }));
      } else {
        if (!card) throw new Error('Selected product card is unavailable.');
        var title = card.querySelector('h2,h3');
        var preview = card.querySelector('.facebook-post-preview');
        var amazon = card.querySelector('a[href*="amazon.com/dp/"]');
        if (!title || !preview || !amazon) throw new Error('Product caption or link is missing.');
        sync(await request('/queue', { asin: asin, title: title.textContent.trim(), text: preview.textContent.trim(), amazon: amazon.href, tier: 'selected' }));
      }
    } catch (error) {
      status.textContent = 'Not scheduled: ' + error.message + ' If the queue is offline, run Start Posting Queue.cmd. Allow local-network access if Chrome asks.';
      var checkbox = card && card.querySelector('.select-posting-control input');
      if (checkbox) checkbox.checked = !!cancelling;
    } finally { busy.delete(asin); paint(); }
  };
  async function refresh() {
    if (pendingRefresh) return;
    pendingRefresh = true;
    try { sync(await request('/queue')); }
    catch (_) { status.textContent = 'Posting queue offline. Run Start Posting Queue.cmd before selecting deals.'; }
    finally { pendingRefresh = false; }
  }
  new MutationObserver(function () { paint(); }).observe(document.getElementById('cards'), { childList: true });
  var selectedCards = document.getElementById('selectedCards');
  if (selectedCards) new MutationObserver(function () { paint(); }).observe(selectedCards, { childList: true });
  refresh();
  window.setInterval(refresh, 15000);
}());

