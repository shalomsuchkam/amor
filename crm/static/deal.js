// Страница сделки: поля причины отказа и повода показываем только для итоговых стадий.
(function () {
  const sel = document.getElementById('page-stage');
  if (!sel) return;
  function sync() {
    const final = sel.selectedOptions[0].dataset.final;
    document.getElementById('p-reason').hidden = final !== 'lost';
    document.getElementById('p-occasion').hidden = final !== 'won';
  }
  sel.addEventListener('change', sync); sync();
})();
