// Local alternatives and manual edits; no AI service calls.
(function () {
  function alternatives(text, title) {
    var price = text.match(/\s+(?:(?:Best|Lowest) price in \d+ days|\d+-day low)\.$/i);
    var suffix = price ? price[0] : '';
    var base = price ? text.slice(0, -suffix.length) : text;
    var choices = [text];
    var purpose = base.match(/^(.+?) for (.+?)\.(.*)$/);
    if (purpose) {
      choices.push(purpose[1] + '. Handy for ' + purpose[2] + '.' + purpose[3] + suffix);
      choices.push(purpose[1] + ', useful for ' + purpose[2] + '.' + purpose[3] + suffix);
    } else if (/mechanical pencils?/i.test(title)) {
      var brand = /^Ticonderoga\b/i.test(title) ? 'Ticonderoga ' : /^Paper Mate\b/i.test(title) ? 'Paper Mate ' : '';
      choices.push(brand + 'mechanical pencils to keep at the bench or in your tool bag.' + suffix);
      choices.push(brand + 'mechanical pencils, good to have around for marking and layout.' + suffix);
    } else {
      var short = base.replace(/\.$/, '');
      choices.push(short + ', good to have around for the next project.' + suffix);
      choices.push(short + '. One for the shop supplies.' + suffix);
    }
    return Array.from(new Set(choices)).filter(function (value) { return value.length > 0 && value.length <= 129; });
  }
  var endpoint = 'http://127.0.0.1:8766';
  var shared = fetch(endpoint + '/captions').then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
  function attach(box) {
    if (box.dataset.captionEditor === 'true') return;
    var card = box.closest('article');
    var preview = box.querySelector('.facebook-post-preview');
    var copy = box.querySelector('.copy-facebook-post');
    var heading = box.querySelector('.facebook-post-heading');
    var asinLabel = card && card.querySelector('.asin');
    var title = card && card.querySelector('h2,h3');
    if (!preview || !copy || !asinLabel || !title) return;
    box.dataset.captionEditor = 'true'; box.dataset.polished = 'true';
    var asin = asinLabel.textContent.replace(/^ASIN:\s*/, '').trim();
    var key = 'dashboard-caption-override-' + asin;
    var suggested = preview.textContent.trim();
    var options = alternatives(suggested, title.textContent.trim());
    var index = 0, revision = 0, changed = false, timer = null, editNumber = 0;
    var override = '';
    var feedback = document.createElement('p');
    feedback.style.fontSize = '13px';
    var area = document.createElement('textarea');
    area.className = 'facebook-caption-input';
    area.setAttribute('aria-label', 'Facebook post caption');
    area.maxLength = 129; area.rows = 4;
    area.style.cssText = 'width:100%;box-sizing:border-box;padding:12px;border:1px solid #bfdbfe;border-radius:12px;font:inherit;resize:vertical';
    area.value = suggested;
    var counter = document.createElement('span');
    preview.hidden = true;
    preview.insertAdjacentElement('afterend', area);
    function effective() { return area.value.trim() || suggested; }
    function display() {
      var text = effective();
      preview.textContent = text;
      if (heading) heading.textContent = 'Facebook Post - ' + text.length + ' characters';
      counter.textContent = area.value.length + '/129 characters';
    }
    function localSave() {
      try { localStorage.setItem(key, JSON.stringify({ text: override, revision: revision })); } catch (_) {}
    }
    async function flush() {
      if (timer) { window.clearTimeout(timer); timer = null; }
      var number = editNumber;
      try {
        var result = await fetch(endpoint + '/caption', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ asin: asin, text: override, revision: revision, effective_text: effective() }) });
        var data = await result.json();
        if (!result.ok) throw new Error(data.error || 'Could not save caption.');
        if (number === editNumber) feedback.textContent = data.queued_updated ? 'Saved. The waiting post will use this text.' : 'Saved for posting. A post already in progress cannot be changed here.';
      } catch (_) {
        if (number === editNumber) feedback.textContent = 'Saved in this browser. Start the posting queue to sync this text with POST NEXT.';
      }
    }
    function update(text, save) {
      area.value = text; display();
      if (save) edited();
    }
    function edited() {
      changed = true; editNumber += 1;
      revision = Math.max(Date.now(), revision + 1);
      override = area.value.trim(); display(); localSave();
      feedback.textContent = 'Saving wording...';
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(flush, 300);
    }
    try {
      var raw = localStorage.getItem(key);
      if (raw) {
        var cached;
        try { cached = JSON.parse(raw); } catch (_) { cached = { text: raw, revision: 1 }; }
        if (cached && typeof cached.text === 'string' && cached.text.length <= 129) {
          override = cached.text; revision = cached.revision || 1;
          update(override || suggested, false);
        }
      }
    } catch (_) {}
    shared.then(function (data) {
      var saved = data.captions && data.captions[asin];
      if (!changed && saved && saved.revision >= revision) {
        override = saved.text || ''; revision = saved.revision;
        update(override || suggested, false); localSave();
      }
    });
    area.addEventListener('input', edited);
    area.addEventListener('change', function () { if (changed) flush(); });
    var liveCopy = copy.cloneNode(true);
    liveCopy.addEventListener('click', async function () {
      if (changed) await flush();
      var text = effective();
      try { await navigator.clipboard.writeText(text); liveCopy.textContent = 'Copied Facebook Post'; }
      catch (_) { window.prompt('Copy this Facebook post:', text); }
      window.setTimeout(function () { liveCopy.textContent = 'Copy Facebook Post'; }, 1800);
    });
    copy.replaceWith(liveCopy);
    var controls = document.createElement('div');
    controls.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;margin-top:8px';
    var rewrite = document.createElement('button');
    rewrite.type = 'button'; rewrite.textContent = 'Rewrite Post';
    rewrite.addEventListener('click', function () {
      if (options.length < 2) { area.focus(); feedback.textContent = 'Type your preferred wording in the box.'; return; }
      index = (index + 1) % options.length; update(options[index], true);
    });
    var reset = document.createElement('button');
    reset.type = 'button'; reset.textContent = 'Use Suggested Text';
    reset.addEventListener('click', function () {
      area.value = suggested; display(); changed = true; editNumber += 1;
      revision = Math.max(Date.now(), revision + 1); override = ''; localSave(); flush();
    });
    controls.append(rewrite, reset);
    box.append(counter, controls, feedback);
    display();
  }
  function scan() { document.querySelectorAll('.facebook-post-box').forEach(attach); }
  new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
  scan();
}());

