(() => {
  'use strict';
  const interval = 14 * 86400000;
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
  fetch(endpoint, {cache:'no-store'}).then(response => {
    if (!response.ok) throw Error('Reminder dates unavailable');
    return response.json();
  }).then(status => {
    dates = {cc:Date.parse(status.cc_updated_at), accepted:Date.parse(status.accepted_updated_at)};
    localStorage.setItem(cacheKey, JSON.stringify(dates));
    show();
  }).catch(() => show());
  setInterval(show, 60000);
})();
