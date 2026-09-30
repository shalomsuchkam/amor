// Доска: перетаскивание, автообновление раз в 30 секунд, фильтр стадий на телефоне.
(function () {
  const board = document.getElementById('board');
  const dlg = document.getElementById('stage-dialog');
  const filter = document.getElementById('stage-filter');
  let busy = false; // пока открыт диалог или тянется карточка, опрос не должен перерисовывать доску

  function applyFilter() {
    board.querySelectorAll('.col').forEach(c => c.classList.toggle('hidden', !!filter.value && c.dataset.stage !== filter.value));
  }
  filter.addEventListener('change', applyFilter);
  applyFilter();

  async function refresh() {
    if (busy || document.hidden) return;
    try {
      const r = await fetch(board.dataset.fragment, {credentials: 'same-origin'});
      if (!r.ok) return;
      board.innerHTML = await r.text();
      applyFilter();
    } catch (e) { /* сеть моргнула: попробуем в следующий раз */ }
  }
  setInterval(refresh, 30000);
  document.addEventListener('visibilitychange', refresh);

  async function move(id, stage, extra) {
    const body = new URLSearchParams({stage, ...extra});
    const r = await fetch(`/deals/${id}/stage`, {
      method: 'POST', body, credentials: 'same-origin',
      headers: {'X-CSRF-Token': csrf(), 'X-Requested-With': 'fetch'},
    });
    if (!r.ok) { const j = await r.json().catch(() => ({})); alert(j.error || 'Не удалось сменить стадию'); }
    busy = false; refresh();
  }

  function ask(col, id) {
    return new Promise(resolve => {
      const final = col.dataset.final;
      if (!final) return resolve({});
      document.getElementById('stage-title').textContent = final === 'lost' ? 'Почему отказ?' : 'Повод заказа';
      document.getElementById('reason-row').hidden = final !== 'lost';
      document.getElementById('occasion-row').hidden = final !== 'won';
      dlg.returnValue = '';
      dlg.onclose = () => {
        if (dlg.returnValue !== 'ok') return resolve(null);
        resolve(final === 'lost'
          ? {loss_reason_id: document.getElementById('reason').value}
          : {occasion: document.getElementById('occasion').value, occasion_for: document.getElementById('occasion-for').value});
      };
      dlg.showModal();
    });
  }

  let dragId = null;
  board.addEventListener('dragstart', e => {
    const d = e.target.closest('.deal'); if (!d) return;
    dragId = d.dataset.id; busy = true; d.classList.add('dragging');
    e.dataTransfer.setData('text/plain', dragId);
  });
  board.addEventListener('dragend', e => { busy = false; e.target.classList && e.target.classList.remove('dragging'); });
  board.addEventListener('dragover', e => { const c = e.target.closest('.col'); if (c) { e.preventDefault(); c.classList.add('over'); } });
  board.addEventListener('dragleave', e => { const c = e.target.closest('.col'); if (c) c.classList.remove('over'); });
  board.addEventListener('drop', async e => {
    const col = e.target.closest('.col'); if (!col || !dragId) return;
    e.preventDefault(); col.classList.remove('over');
    const id = dragId; dragId = null;
    const card = board.querySelector(`.deal[data-id="${id}"]`);
    if (card && card.dataset.stage === col.dataset.stage) { busy = false; return; }
    const extra = await ask(col, id);
    if (extra === null) { busy = false; return; }
    move(id, col.dataset.stage, extra);
  });
})();
