(() => {
  'use strict';
  const interval = 4 * 86400000;
  const endpoint = `data/csv-reminders.json?ts=${Date.now()}`;
  const cacheKey = 'dashboard-csv-reminder-dates-v1';

  function render(id, label, updated) {
    const element = document.getElementById(id);
    const due = updated + interval;
    const left = due - Date.now();
    const overdue = !updated || left <= 0;
    const days = updated ? Math.ceil(Math.abs(left) / 86400000) : 0;
    element.querySelector('.dashboard-countdown-number').textContent = overdue ? '!' : days;
    element.querySelector('strong').textContent = overdue ? `${label} update due` : `day${days === 1 ? '' : 's'} remaining`;
    element.querySelector('small').textContent = !updated ? `${label} update date unavailable.` : overdue ? `${label} is ${days} day${days === 1 ? '' : 's'} overdue.` : `${label} due ${new Date(due).toLocaleDateString()}.`;
    element.classList.toggle('overdue', overdue);
  }

  let dates = {};
  try { dates = JSON.parse(localStorage.getItem(cacheKey) || '{}'); } catch {}
  const show = () => { render('dashboard-cc-countdown', 'CC list', dates.cc); render('dashboard-accepted-countdown', 'Accepted CC list', dates.accepted); };
  show();
  async function refresh() {
    try {
      const response = await fetch('https://api.github.com/repos/Mhhickma/Dashboard/git/trees/main?recursive=1', {cache:'no-store', signal:AbortSignal.timeout(20000)});
      if (!response.ok) throw Error('Upload dates unavailable');
      const tree = await response.json();
      if (tree.truncated) throw Error('Incomplete upload listing');
      const latest = suffix => {
        const names = tree.tree.map(item => item.path).filter(path => path.startsWith('data/creator-connections/') && path.endsWith(suffix)).sort();
        const stamp = names.at(-1)?.split('/').at(-1).match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(\d{3})Z-/);
        return stamp ? Date.parse(`${stamp[1]}-${stamp[2]}-${stamp[3]}T${stamp[4]}:${stamp[5]}:${stamp[6]}.${stamp[7]}Z`) : null;
      };
      dates = {cc:latest('-replacement-complete.csv'), accepted:latest('-accepted-history.csv')};
      try { localStorage.setItem(cacheKey, JSON.stringify(dates)); } catch {}
      show();
    } catch {
      // Keep the last verified dates when GitHub is temporarily unavailable.
      show();
    }
  }
  refresh();
  window.addEventListener('focus', refresh);
  setInterval(show, 60000);
})();
