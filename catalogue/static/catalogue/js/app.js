// Interactions JavaScript : recherche AJAX, retour d'emprunt AJAX, affichage/masquage.
(function () {
  'use strict';

  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const zoneMessages = document.getElementById('messages');

  function afficherMessage(texte, type) {
    const p = document.createElement('p');
    p.className = 'message ' + type;
    p.textContent = texte;
    zoneMessages.replaceChildren(p);
  }

  function formaterDate(iso) {
    return new Date(iso + 'T00:00:00').toLocaleDateString('fr-FR');
  }

  // 1. Recherche / filtre en direct (fetch vers l'API REST, sans rechargement)
  const formRecherche = document.getElementById('form-recherche');
  if (formRecherche) {
    const tbody = document.getElementById('livres-tbody');
    const compteur = document.getElementById('compteur');
    const champ = document.getElementById('q');
    const caseDispo = document.getElementById('dispo');
    let minuteur = null;
    let derniereRequete = 0;

    function ligne(livre) {
      const tr = document.createElement('tr');
      const tdTitre = document.createElement('td');
      const lien = document.createElement('a');
      lien.href = formRecherche.dataset.detailUrl.replace('/0/', '/' + livre.id + '/');
      lien.textContent = livre.titre;
      tdTitre.append(lien);
      const tdAuteur = document.createElement('td');
      tdAuteur.textContent = livre.auteur_nom;
      const tdAnnee = document.createElement('td');
      tdAnnee.textContent = livre.annee_publication ?? '—';
      const tdDispo = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = 'badge ' + (livre.disponibles > 0 ? 'ok' : 'ko');
      badge.textContent = livre.disponibles + ' / ' + livre.exemplaires;
      tdDispo.append(badge);
      tr.append(tdTitre, tdAuteur, tdAnnee, tdDispo);
      return tr;
    }

    async function rechercher() {
      const numero = ++derniereRequete;
      const params = new URLSearchParams();
      if (champ.value.trim()) params.set('search', champ.value.trim());
      if (caseDispo.checked) params.set('disponible', '1');
      try {
        const reponse = await fetch(formRecherche.dataset.api + '?' + params, {
          headers: { Accept: 'application/json' },
        });
        if (!reponse.ok) throw new Error('HTTP ' + reponse.status);
        const donnees = await reponse.json();
        if (numero !== derniereRequete) return; // une requête plus récente est partie
        const lignes = donnees.results.map(ligne);
        if (lignes.length === 0) {
          const tr = document.createElement('tr');
          const td = document.createElement('td');
          td.colSpan = 4;
          td.textContent = 'Aucun livre ne correspond.';
          tr.append(td);
          lignes.push(tr);
        }
        tbody.replaceChildren(...lignes);
        compteur.textContent = donnees.count + ' résultat' + (donnees.count > 1 ? 's' : '');
        const pagination = document.getElementById('pagination');
        if (pagination) pagination.hidden = true;
      } catch (erreur) {
        afficherMessage('La recherche a échoué (' + erreur.message + ').', 'error');
      }
    }

    formRecherche.addEventListener('submit', (e) => { e.preventDefault(); rechercher(); });
    champ.addEventListener('input', () => { clearTimeout(minuteur); minuteur = setTimeout(rechercher, 250); });
    caseDispo.addEventListener('change', rechercher);
  }

  // 2. Retour d'un emprunt via l'API (POST), mise à jour de la ligne sans recharger
  document.querySelectorAll('.form-retour').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const bouton = form.querySelector('button');
      bouton.disabled = true;
      try {
        const reponse = await fetch(form.dataset.api, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf, Accept: 'application/json' },
        });
        const donnees = await reponse.json();
        if (!reponse.ok) {
          afficherMessage(donnees.detail || 'Retour impossible.', 'error');
          bouton.disabled = false;
          return;
        }
        const tr = form.closest('tr');
        tr.classList.remove('retard');
        tr.querySelector('.statut').textContent = 'Rendu le ' + formaterDate(donnees.date_retour);
        form.remove();
        afficherMessage('« ' + donnees.livre_titre + ' » est retourné.', 'success');
      } catch (erreur) {
        afficherMessage('Erreur réseau : ' + erreur.message, 'error');
        bouton.disabled = false;
      }
    });
  });

  // 3. Affichage / masquage d'un bloc (résumé d'un livre)
  document.querySelectorAll('[data-toggle]').forEach((bouton) => {
    const cible = document.getElementById(bouton.dataset.toggle);
    bouton.addEventListener('click', () => {
      cible.hidden = !cible.hidden;
      bouton.textContent = cible.hidden ? 'Afficher le résumé' : 'Masquer le résumé';
    });
  });
})();
