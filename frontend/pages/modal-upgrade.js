fetch('modal-upgrade.html')
  .then(res => res.text())
  .then(html => {
    document.body.insertAdjacentHTML('beforeend', html);
  })
  .catch(err => console.error('Erreur chargement modal upgrade:', err));
