/*
  activites.js — îlot de chargement des activités à la demande (OOM-107),
  copié tel quel dans site/actifs/ par src/export_html.py.

  Une sous-page départementale n'embarque pas le détail des activités :
  chaque établissement qui en a porte un <details data-finess="…"> dont le
  <summary> donne le nombre, et la table porte l'URL relative du fragment de
  sa sous-page (data-fragment, contrat B révisé par OOM-115 :
  donnees/activites/<code>/<n>.json ; l'URL est résolue par fetch contre la
  page, quelle que soit sa profondeur). Ce
  script n'émet AUCUNE requête au chargement de la page (D9) : le fragment est
  téléchargé à la première ouverture d'un panneau, une seule fois par table,
  puis sert à remplir chaque panneau ouvert.

  Aucun silence (D6) : un fetch en échec (réseau, statut HTTP, JSON illisible)
  s'affiche dans le panneau, avec le lien vers le fragment ; refermer puis
  rouvrir le panneau retente. Un établissement absent du fragment alors que
  la page lui annonçait des activités le dit aussi, jamais un panneau vide.

  Présentation seulement (D7) : les valeurs viennent du fragment, produit par
  la couche 6 ; code_nature reste brut, libelle_nature vaut null tant
  qu'aucune nomenclature de nature n'est versionnée (OOM-29) — affiché
  « [non résolu] » à côté du code, jamais un libellé inventé. Même rendu que
  les activités embarquées de liste.html. Le contenu est construit par nœuds
  DOM (textContent), jamais par innerHTML.

  Une fois un panneau rempli, l'événement « activites-chargees » est émis sur
  son <details> (filtres.js y branche le filtre par nature).
*/
(function () {
  "use strict";

  var CLASSES_ETAT = { A: "etat-actif", I: "etat-inactif" };

  function element(nom, classe, texte) {
    var noeud = document.createElement(nom);
    if (classe) noeud.className = classe;
    if (texte !== undefined) noeud.textContent = texte;
    return noeud;
  }

  function cellule(tr) {
    var td = element("td");
    for (var i = 1; i < arguments.length; i += 1) {
      if (i > 1) td.appendChild(document.createTextNode(" "));
      td.appendChild(arguments[i]);
    }
    tr.appendChild(td);
  }

  function capacites(liste) {
    if (!liste || !liste.length) return element("span", "code-brut", "—");
    var ul = element("ul", "capacites-liste");
    liste.forEach(function (c) {
      var li = element("li", "", c.nombre === null || c.nombre === undefined ? "?" : String(c.nombre));
      li.appendChild(document.createTextNode(" "));
      li.appendChild(element("span", "code-brut", "(unité " + (c.code_unite_mesure || "?") +
        ", statut " + (c.code_statut_capacite || "?") + ")"));
      ul.appendChild(li);
    });
    return ul;
  }

  function tableActivites(activites) {
    var table = element("table");
    var tete = element("tr");
    ["Nature", "État", "Capacité(s)"].forEach(function (t) { tete.appendChild(element("th", "", t)); });
    table.appendChild(element("thead")).appendChild(tete);
    var corps = table.appendChild(element("tbody"));
    activites.forEach(function (a) {
      var tr = element("tr");
      tr.dataset.nature = a.code_nature || "";
      var nature = a.libelle_nature || (a.code_nature ? "[non résolu]" : "[absent]");
      cellule(tr, element("span", a.libelle_nature ? "" : "code-non-resolu", nature),
        element("span", "code-brut", "(" + (a.code_nature || "") + ")"));
      cellule(tr, element("span", "etat " + (CLASSES_ETAT[a.etat_objet] || ""), a.etat_libelle || ""));
      cellule(tr, capacites(a.capacites));
      corps.appendChild(tr);
    });
    return table;
  }

  function message(details, texte, classe, lien) {
    var p = element("p", classe, texte);
    if (lien) {
      p.appendChild(document.createTextNode(" "));
      var a = element("a", "", "Fichier de données des activités");
      a.href = lien;
      p.appendChild(a);
      p.appendChild(document.createTextNode("."));
    }
    vider(details);
    details.appendChild(p);
  }

  function vider(details) {
    var summary = details.querySelector("summary");
    while (summary.nextSibling) details.removeChild(summary.nextSibling);
  }

  function brancher(table) {
    var url = table.dataset.fragment;
    var chargement = null;  // promesse du fragment, partagée par les panneaux

    function fragment() {
      if (!chargement) {
        chargement = fetch(url).then(function (reponse) {
          if (!reponse.ok) throw new Error("HTTP " + reponse.status + " sur " + url);
          return reponse.json();
        });
        // Un échec ne reste pas en cache : rouvrir un panneau retente.
        chargement.catch(function () { chargement = null; });
      }
      return chargement;
    }

    function ouvrir(details) {
      if (!details.open || details.dataset.chargees) return;
      if (details.dataset.enCours) return;
      details.dataset.enCours = "1";
      message(details, "Chargement des activités…", "activites-etat");
      fragment().then(function (donnees) {
        var activites = donnees[details.dataset.finess];
        if (!Array.isArray(activites) || !activites.length) {
          message(details, "Aucune activité trouvée pour l'établissement " + details.dataset.finess +
            " dans le fichier de données, alors que la page en annonce : données incohérentes.",
            "alerte", url);
          return;
        }
        vider(details);
        details.appendChild(tableActivites(activites));
        details.dataset.chargees = "1";
        details.dispatchEvent(new Event("activites-chargees"));
      }).catch(function (erreur) {
        message(details, "Échec du chargement des activités (" + erreur.message +
          "). Refermez puis rouvrez le panneau pour réessayer.", "alerte", url);
      }).then(function () {
        delete details.dataset.enCours;
      });
    }

    Array.prototype.forEach.call(table.querySelectorAll("details[data-finess]"), function (details) {
      details.addEventListener("toggle", function () { ouvrir(details); });
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("table[data-fragment]"), brancher);
})();
