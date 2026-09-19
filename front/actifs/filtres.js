/*
  filtres.js — îlot de confort commun aux vues tabulaires (OOM-102), copié
  tel quel dans site/actifs/ par src/export_html.py.

  La page rend déjà tout son contenu sans JS (D10) : ce script n'ajoute que le
  filtrage, le tri par colonne et le filtre par nature des activités. Il ne
  calcule aucune donnée publiée (D7) : il masque, réordonne et additionne des
  valeurs déjà présentes dans le HTML. Tout se branche par attributs data-*,
  aucun identifiant de page n'est codé ici :

  <form class="filtres" hidden data-table="id-table">   formulaire de filtres
      data-compteur="id"  data-unite="ligne(s) affichée(s)"
                          compteur réécrit en « n <unité> sur N. »
      data-vide="id"      message affiché quand aucune ligne ne reste
      data-total="id"  data-total-libelle="id"  data-colonne-total="k"
                          somme des data-valeur de la colonne k des lignes
                          visibles (optionnel)
    <select data-champ="dep">   égalité avec tr.dataset.dep (vide = tous)
    <input data-colonne="k">    sous-chaîne, sans casse, du texte de la
                                colonne k
  <th data-cle="k" [data-numerique]>…<span class="fleche"></span></th>
                          en-tête triable (numérique : tri sur data-valeur)
  <table data-natures>    chaque <details> de la table reçoit, à sa première
                          ouverture, un filtre par data-nature de ses lignes
                          dès qu'il en porte au moins deux distinctes
*/
(function () {
  "use strict";

  function tableau(liste) { return Array.prototype.slice.call(liste); }

  function valeurCellule(tr, cle, numerique) {
    var td = tr.children[cle];
    return numerique ? Number(td.dataset.valeur) : td.textContent;
  }

  function brancherFiltres(form) {
    var corps = document.getElementById(form.dataset.table).tBodies[0];
    var lignes = tableau(corps.children);
    var champs = tableau(form.querySelectorAll("[data-champ]"));
    var textes = tableau(form.querySelectorAll("[data-colonne]"));
    var compteur = document.getElementById(form.dataset.compteur);
    var vide = document.getElementById(form.dataset.vide);
    var total = form.dataset.total && document.getElementById(form.dataset.total);
    var totalLibelle = form.dataset.totalLibelle &&
      document.getElementById(form.dataset.totalLibelle);
    var colonneTotal = Number(form.dataset.colonneTotal);

    lignes.forEach(function (tr) {
      tr.textesMinuscules = textes.map(function (champ) {
        return tr.children[Number(champ.dataset.colonne)].textContent.toLowerCase();
      });
    });

    function filtrer() {
      var requetes = textes.map(function (champ) { return champ.value.trim().toLowerCase(); });
      var actif = champs.some(function (c) { return c.value; }) ||
        requetes.some(function (q) { return q; });
      var visibles = 0, somme = 0;
      lignes.forEach(function (tr) {
        var ok = requetes.every(function (q, i) {
          return !q || tr.textesMinuscules[i].indexOf(q) !== -1;
        }) && champs.every(function (c) {
          return !c.value || tr.dataset[c.dataset.champ] === c.value;
        });
        tr.hidden = !ok;
        if (ok) {
          visibles += 1;
          if (total) somme += valeurCellule(tr, colonneTotal, true);
        }
      });
      compteur.textContent = visibles + " " + form.dataset.unite + " sur " + lignes.length + ".";
      if (total) total.textContent = somme;
      if (totalLibelle) totalLibelle.textContent = actif ? "(lignes affichées)" : "(toutes lignes)";
      vide.hidden = visibles !== 0;
    }

    form.addEventListener("input", filtrer);
    form.addEventListener("reset", function () { setTimeout(filtrer, 0); });
    form.hidden = false;
    filtrer();
  }

  function brancherTri(table) {
    var corps = table.tBodies[0];
    var entetes = tableau(table.querySelectorAll("thead th[data-cle]"));
    var tri = { cle: null, sens: 1 };

    function trier(th) {
      var cle = Number(th.dataset.cle);
      var numerique = !!th.dataset.numerique;
      var lignes = tableau(corps.children);
      tri.sens = tri.cle === cle ? -tri.sens : (numerique ? -1 : 1);
      tri.cle = cle;
      lignes.sort(function (a, b) {
        var va = valeurCellule(a, cle, numerique), vb = valeurCellule(b, cle, numerique);
        return (numerique ? va - vb : String(va).localeCompare(String(vb), "fr")) * tri.sens;
      });
      lignes.forEach(function (tr) { corps.appendChild(tr); });
      entetes.forEach(function (autre) {
        autre.querySelector(".fleche").textContent =
          autre === th ? (tri.sens === 1 ? "▲" : "▼") : "";
      });
    }

    entetes.forEach(function (th) {
      th.addEventListener("click", function () { trier(th); });
    });
  }

  function brancherNatures(details) {
    details.addEventListener("toggle", function () {
      if (!details.open || details.dataset.pret) return;
      details.dataset.pret = "1";
      var activites = tableau(details.querySelectorAll("tbody tr"));
      var natures = activites.map(function (tr) { return tr.dataset.nature; })
        .filter(function (n, i, t) { return n && t.indexOf(n) === i; }).sort();
      if (natures.length < 2) return;
      var label = document.createElement("label");
      label.className = "filtre-nature";
      label.textContent = "Filtrer par nature ";
      var select = document.createElement("select");
      select.appendChild(new Option("Toutes", ""));
      natures.forEach(function (n) { select.appendChild(new Option(n, n)); });
      select.addEventListener("change", function () {
        activites.forEach(function (tr) {
          tr.hidden = !!select.value && tr.dataset.nature !== select.value;
        });
      });
      label.appendChild(select);
      details.querySelector("summary").after(label);
    });
  }

  tableau(document.querySelectorAll("form.filtres[data-table]")).forEach(brancherFiltres);
  tableau(document.querySelectorAll("table")).forEach(function (table) {
    if (table.querySelector("thead th[data-cle]")) brancherTri(table);
  });
  tableau(document.querySelectorAll("table[data-natures] details")).forEach(brancherNatures);
})();
