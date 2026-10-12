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
  function attach(box) {
    if (box.dataset.captionEditor === 'true') return;
    var card = box.closest('article');
    var preview = box.querySelector('.facebook-post-preview');
    var copy = box.querySelector('.copy-facebook-post');
    var heading = box.querySelector('.facebook-post-heading');
    var asinLabel = card && card.querySelector('.asin');
    var title = card && card.querySelector('h2,h3');
    if (!preview || !copy || !asinLabel || !title) return;
    box.dataset.captionEditor = 'true';
    box.dataset.polished = 'true';
    var key = 'dashboard-caption-override-' + asinLabel.textContent.replace(/^ASIN:\s*/, '').trim();
    var options = alternatives(preview.textContent.trim(), title.textContent.trim());
    var index = 0;
    var feedback = document.createElement('p');
    feedback.style.fontSize = '13px';
    function show(text, save) {
      preview.textContent = text;
      if (heading) heading.textContent = 'Facebook Post - ' + text.length + ' characters';
      if (save) {
        try { localStorage.setItem(key, text); } catch (_) {}
        feedback.textContent = 'Updated. New selections will use this wording; already queued posts keep their saved caption.';
      }
    }
    try { var saved = localStorage.getItem(key); if (saved && saved.length <= 129) show(saved, false); } catch (_) {}
    var liveCopy = copy.cloneNode(true);
    liveCopy.addEventListener('click', async function () {
      var text = preview.textContent.trim();
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
      if (options.length < 2) { feedback.textContent = 'Use Edit Post to write your preferred wording.'; edit.click(); return; }
      index = (index + 1) % options.length;
      show(options[index], true);
    });
    var edit = document.createElement('button');
    edit.type = 'button'; edit.textContent = 'Edit Post';
    var area = document.createElement('textarea');
    area.setAttribute('aria-label', 'Edit Facebook post');
    area.maxLength = 129; area.rows = 3;
    area.style.cssText = 'width:100%;box-sizing:border-box;margin-top:8px';
    var counter = document.createElement('span');
    var save = document.createElement('button');
    save.type = 'button'; save.textContent = 'Save Wording';
    var cancel = document.createElement('button');
    cancel.type = 'button'; cancel.textContent = 'Cancel Edit';
    var editor = document.createElement('div');
    editor.hidden = true;
    editor.append(area, counter, save, cancel);
    area.addEventListener('input', function () { counter.textContent = area.value.length + '/129 characters '; });
    edit.addEventListener('click', function () {
      editor.hidden = false; area.value = preview.textContent.trim();
      counter.textContent = area.value.length + '/129 characters '; area.focus();
    });
    save.addEventListener('click', function () {
      var text = area.value.trim();
      if (!text || text.length > 129) { feedback.textContent = 'Use 1–129 characters.'; return; }
      show(text, true); editor.hidden = true;
    });
    cancel.addEventListener('click', function () { editor.hidden = true; });
    controls.append(rewrite, edit);
    box.append(controls, editor, feedback);
  }
  function scan() { document.querySelectorAll('.facebook-post-box').forEach(attach); }
  new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
  scan();
}());

