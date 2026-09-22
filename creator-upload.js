/* Shared upload controller: stream logical CSV records into bounded, immutable files. */
(() => {
  'use strict';
  const form = document.getElementById('creatorCsvUploadForm');
  if (!form) return;
  const input = document.getElementById('creatorCsvFile');
  const status = document.getElementById('creatorCsvUploadStatus');
  const label = document.getElementById('creatorCsvFileName');
  const endpoint = 'https://script.google.com/macros/s/AKfycbxU4HTktR6zH5Wfbk58V24X-HAE9kZYlzdlm1gqMp1NL_ZGzF7p-0VAL5VeGNfnAyxESA/exec';
  const reminder = document.createElement('p');
  reminder.className = 'creator-upload-status';
  reminder.setAttribute('role','status');
  form.before(reminder);
  const reminderKey = 'cc-last-completed-upload';
  let completedAt = null;
  function showCountdown() {
    if (!completedAt) { reminder.textContent = 'CC update reminder: checking the latest completed upload...'; return; }
    const due = completedAt + 15 * 86400000;
    const left = due - Date.now();
    const days = Math.ceil(Math.abs(left) / 86400000);
    reminder.textContent = left > 0
      ? `CC list update due in ${days} day${days===1?'':'s'} (${new Date(due).toLocaleDateString()}). Last completed upload: ${new Date(completedAt).toLocaleDateString()}.`
      : `Reminder: upload your newest CC list. ${days ? days+' day'+(days===1?'':'s')+' overdue.' : 'Due today.'} Last completed upload: ${new Date(completedAt).toLocaleDateString()}.`;
    reminder.style.fontWeight = '700';
    reminder.style.color = left > 0 ? '#1d4ed8' : '#b45309';
  }
  function recordCompletedUpload(timestamp) {
    completedAt = timestamp;
    try { localStorage.setItem(reminderKey,String(timestamp)); } catch {}
    showCountdown();
  }
  async function checkCompletedUpload() {
    try { const cached=Number(localStorage.getItem(reminderKey)); if(cached>0 && Number.isFinite(cached))completedAt=cached; } catch {}
    showCountdown();
    try {
      const response=await fetch('https://api.github.com/repos/Mhhickma/Dashboard/git/trees/main?recursive=1');
      if(!response.ok)throw Error('GitHub unavailable');
      const tree=await response.json();if(tree.truncated)throw Error('Incomplete listing');
      const markers=tree.tree.filter(f=>/^data\/creator-connections\/.*-replacement-complete\.csv$/.test(f.path)).map(f=>f.path).sort();
      if(!markers.length){reminder.textContent='Reminder: upload your newest CC list. No completed replacement upload found.';return;}
      const commits=await fetch('https://api.github.com/repos/Mhhickma/Dashboard/commits?per_page=1&path='+encodeURIComponent(markers.at(-1)));
      if(!commits.ok)throw Error('Upload date unavailable');
      const rows=await commits.json();const timestamp=Date.parse(rows[0]?.commit?.committer?.date);
      if(!Number.isFinite(timestamp))throw Error('Upload date unavailable');
      recordCompletedUpload(timestamp);
    } catch { if(!completedAt)reminder.textContent='CC update reminder unavailable. Could not verify the latest completed upload.';else reminder.textContent+=' Using the last verified upload date.'; }
  }
  checkCompletedUpload();
  setInterval(showCountdown,60000);
  const encoder = new TextEncoder();
  const maxBytes = 2 * 1024 * 1024;
  input.multiple = true;
  input.addEventListener('change', () => { label.textContent = `${input.files.length} CSV file(s) selected`; });

  async function* chunks(file) {
    const reader = file.stream().pipeThrough(new TextDecoderStream('utf-8', {fatal: true})).getReader();
    let header = '', record = '', body = '', size = 0, quoted = false;
    try {
      for (;;) {
        const {value, done} = await reader.read();
        if (done) break;
        for (const ch of value) {
          record += ch;
          if (ch === '"') quoted = !quoted;
          if (record.length > maxBytes) throw new Error('A CSV record exceeds the 2 MB upload limit. Use the documented local import.');
          if (ch !== '\n' || quoted) continue;
          if (!header) { header = record.replace(/^\uFEFF/, ''); size = encoder.encode(header).length; }
          else {
            const bytes = encoder.encode(record).length;
            if (bytes + encoder.encode(header).length > maxBytes) throw new Error('A CSV record is too large for browser upload.');
            if (size + bytes > maxBytes && body) { yield header + body; body = ''; size = encoder.encode(header).length; }
            body += record; size += bytes;
          }
          record = '';
        }
      }
      if (quoted) throw new Error('Unclosed CSV quote. Upload stopped.');
      if (record.trim()) {
        if (!header) throw new Error('CSV needs a header and campaign rows.');
        const bytes = encoder.encode(record + '\n').length;
        if (bytes + encoder.encode(header).length > maxBytes) throw new Error('A CSV record is too large for browser upload.');
        if (size + bytes > maxBytes && body) { yield header + body; body = ''; }
        body += record + '\n';
      }
      if (body) yield header + body;
    } finally { reader.releaseLock(); }
  }

  function post(text, filename) {
    return new Promise((resolve, reject) => {
      const requestId = crypto.randomUUID();
      const frame = document.createElement('iframe');
      frame.name = `creator-${requestId}`; frame.hidden = true;
      const postForm = document.createElement('form');
      postForm.method = 'POST'; postForm.action = endpoint; postForm.target = frame.name;
      const bytes = encoder.encode(text);
      let binary = '';
      for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i+8192));
      const fields = {action: 'uploadCreatorChunk', filename, csvBase64: btoa(binary), requestId, replyOrigin: location.origin};
      for (const [name, value] of Object.entries(fields)) {
        const field = document.createElement('input'); field.type = 'hidden'; field.name = name; field.value = value; postForm.append(field);
      }
      const cleanup = () => { clearTimeout(timer); window.removeEventListener('message', receive); postForm.remove(); frame.remove(); };
      const receive = event => {
        if (!/^https:\/\/(?:script\.google\.com|(?:[a-z0-9-]+\.)?googleusercontent\.com)$/.test(event.origin)) return;
        if (event.data?.requestId !== requestId) return;
        cleanup();
        event.data.ok ? resolve(event.data) : reject(new Error(event.data.error || 'Upload not confirmed.'));
      };
      const timer = setTimeout(() => { cleanup(); reject(new Error('No upload confirmation. Update the Apps Script upload handler before retrying.')); }, 120000);
      window.addEventListener('message', receive);
      document.body.append(frame, postForm); postForm.submit();
    });
  }

  const progressKey = 'creator-csv-upload-progress-v1';
  async function contentHash(text) {
    const bytes = encoder.encode(text);
    const header = encoder.encode(`blob ${bytes.length}\0`);
    const blob = new Uint8Array(header.length + bytes.length);
    blob.set(header); blob.set(bytes, header.length);
    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-1', blob)), b => b.toString(16).padStart(2, '0')).join('');
  }
  async function uploadConfirmed(text, name, hash) {
    let lastError;
    for (let attempt = 0; attempt < 4; attempt++) {
      try { await post(text, name); return; }
      catch (error) {
        lastError = error;
        // A lost confirmation can still mean the immutable file was saved.
        try {
          const response = await fetch(`https://api.github.com/repos/Mhhickma/Dashboard/contents/data/creator-connections/${name}?ref=main`, {cache:'no-store', signal:AbortSignal.timeout(20000)});
          if (response.ok) {
            const saved = await response.json();
            if (saved.sha === hash) return;
            throw new Error('Saved upload part differs from the selected file. Select the original files to resume.');
          }
        } catch (verificationError) {
          if (verificationError.message.startsWith('Saved upload part differs')) throw verificationError;
        }
        if (attempt < 3) {
          status.textContent = `Connection interrupted. Retrying this part (${attempt+1} of 3). Confirmed progress is saved.`;
          await new Promise(resolve => setTimeout(resolve, 5000 * (attempt+1)));
        }
      }
    }
    throw lastError;
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const files = [...input.files];
    if (!files.length || files.some(f => !/\.csv$/i.test(f.name))) { status.textContent = 'Choose one or more CSV files.'; return; }
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true; input.disabled = true;
    let confirmed = 0; const batchFiles = [];
    const signature = JSON.stringify(files.map(f => [f.name, f.size, f.lastModified]));
    let progress;
    try { progress = JSON.parse(localStorage.getItem(progressKey)); } catch {}
    if (!progress || progress.signature !== signature) progress = {signature, session:new Date().toISOString().replace(/[-:.]/g, '') + '-' + crypto.randomUUID() + '-replacement', parts:{}};
    const session = progress.session;
    const saveProgress = () => localStorage.setItem(progressKey, JSON.stringify(progress));
    try {
      saveProgress();
      for (let index = 0; index < files.length; index++) {
        let part = 0;
        for await (const text of chunks(files[index])) {
          const name = `${session}-${String(index).padStart(4,'0')}-${String(part++).padStart(6,'0')}.csv`;
          status.textContent = `Uploading ${files[index].name}, part ${part}… ${confirmed} confirmed.`;
          const hash = await contentHash(text);
          if (progress.parts[name] && progress.parts[name] !== hash) throw new Error('Selected file contents changed. Choose the original files to resume.');
          if (!progress.parts[name]) {
            await uploadConfirmed(text, name, hash);
            progress.parts[name] = hash; saveProgress();
          }
          batchFiles.push(name); confirmed++;
        }
        if (!part) throw new Error(`${files[index].name} contains no campaign rows.`);
      }
      status.textContent = 'Activating the complete replacement CC batch…';
      const manifest = 'ASIN List,Batch file\n'+batchFiles.map(name=>','+name).join('\n')+'\n';
      await uploadConfirmed(manifest,session+'-complete.csv',await contentHash(manifest));
      localStorage.removeItem(progressKey);
      recordCompletedUpload(Date.now());
      status.textContent = `${confirmed} CSV parts uploaded. This batch replaces the previous CC list for the next scans.`;
      form.reset(); label.textContent = 'Choose CSV files';
    } catch (error) { status.textContent = `${error.message} ${confirmed} parts confirmed and progress saved. Select these same files in the same order and click Replace CC list to resume. Your previous CC list remains active until completion.`; }
    finally { button.disabled = false; input.disabled = false; }
  });
})();
