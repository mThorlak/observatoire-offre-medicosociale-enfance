/*
  carte.js — îlot de la carte des établissements (OOM-113), copié tel quel
  dans site/actifs/ par src/export_html.py.

  Au chargement de la page, ce script ne fait qu'une chose : montrer le
  bouton « Afficher la carte » (caché sans JS, D10). AUCUNE requête n'est
  émise avant le clic (D9) : MapLibre (~1 Mo) dépasse à lui seul le budget
  d'une page. Au clic, il injecte la feuille de style et les scripts
  vendorisés de MapLibre et de pmtiles (chemins relatifs en data-* de
  #carte), télécharge le style vectoriel Plan IGN, puis construit la carte :
  fond IGN, points de la couche `etablissements` de l'archive PMTiles
  (contrat C), filtrés sur `dep` pour une carte départementale et cadrés sur
  data-emprise.

  Aucun échec silencieux (D6), jamais un cadre vide : un script qui ne se
  charge pas (ou une carte impossible à construire, WebGL absent) laisse la
  carte cachée et affiche un message dans #carte-etat, le bouton étant
  rendu pour réessayer ; un style IGN illisible est remplacé par un fond
  neutre, en le disant ; une erreur de l'archive ou des tuiles du fond est
  affichée à côté de la carte.

  Présentation seulement (D7) : chemins, filtre, cadrage et libellés des
  catégories viennent de la page, produite par la couche 6 ; un code de
  catégorie sans libellé s'affiche « [non résolu] » avec son code, jamais
  un libellé inventé. La fenêtre d'un point est construite par nœuds DOM
  (textContent), jamais par innerHTML ; son lien `lien` (relatif à la racine
  du site) mène à la fiche, ancre et-<finess> de la sous-page.
*/
(function () {
  "use strict";

  var SOURCE = "etablissements";
  // Fond de repli quand le style IGN est illisible : un aplat, sans appel.
  var FOND_NEUTRE = {
    version: 8, sources: {},
    layers: [{ id: "fond-neutre", type: "background", paint: { "background-color": "#eef0ec" } }]
  };

  var carte = document.getElementById("carte");
  var commande = document.getElementById("carte-commande");
  var bouton = document.getElementById("afficher-carte");
  var etat = document.getElementById("carte-etat");
  if (!carte || !commande || !bouton || !etat) return;
  var d = carte.dataset;
  var signales = {};

  function element(nom, classe, texte) {
    var noeud = document.createElement(nom);
    if (classe) noeud.className = classe;
    if (texte !== undefined) noeud.textContent = texte;
    return noeud;
  }

  // Un message par cause, affiché une fois (les tuiles en échec en
  // produiraient des dizaines).
  function signaler(cause, texte) {
    if (signales[cause]) return;
    signales[cause] = true;
    etat.appendChild(element("p", "", texte));
    etat.hidden = false;
  }

  function script(url) {
    return new Promise(function (resolu, rejete) {
      var s = document.createElement("script");
      s.src = url;
      s.onload = function () { resolu(); };
      s.onerror = function () { rejete(new Error("chargement impossible de " + url)); };
      document.head.appendChild(s);
    });
  }

  function feuille(url) {
    var lien = document.createElement("link");
    lien.rel = "stylesheet";
    lien.href = url;
    document.head.appendChild(lien);
  }

  function fond() {
    return fetch(d.fond).then(function (reponse) {
      if (!reponse.ok) throw new Error("HTTP " + reponse.status);
      return reponse.json();
    }).catch(function (erreur) {
      signaler("fond", "Fond de carte IGN indisponible (" + erreur.message +
        ") : les établissements sont affichés sur un fond neutre.");
      return FOND_NEUTRE;
    });
  }

  function fenetre(proprietes) {
    var categories = JSON.parse(d.categories || "{}");
    var code = proprietes.categorie;
    var bloc = element("div", "carte-fenetre");
    bloc.appendChild(element("strong", "", proprietes.nom || "[sans nom]"));
    var categorie = element("p", "", "Catégorie : " +
      (categories[code] || (code ? "[non résolu]" : "[absent]")));
    if (code) {
      categorie.appendChild(document.createTextNode(" "));
      categorie.appendChild(element("span", "code-brut", "(" + code + ")"));
    }
    bloc.appendChild(categorie);
    var lien = element("a", "", "Fiche de l'établissement " + proprietes.finess);
    lien.href = d.racine + proprietes.lien;
    bloc.appendChild(element("p")).appendChild(lien);
    return bloc;
  }

  function construire(style) {
    var maplibregl = window.maplibregl;
    var protocole = new window.pmtiles.Protocol();
    maplibregl.addProtocol("pmtiles", protocole.tile);
    var archive = new URL(d.archive, document.baseURI).href;
    carte.hidden = false;
    var instance = new maplibregl.Map({
      container: carte,
      style: style,
      bounds: JSON.parse(d.emprise),
      fitBoundsOptions: { padding: 24, maxZoom: 13 },
      attributionControl: false
    });
    instance.addControl(new maplibregl.AttributionControl({
      compact: false, customAttribution: d.attribution }));
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }));
    instance.on("error", function (evenement) {
      var message = evenement.error && evenement.error.message ? evenement.error.message : "erreur inconnue";
      if (evenement.sourceId === SOURCE) {
        signaler("archive", "Les établissements n'ont pas pu être chargés depuis l'archive (" +
          message + ") : la carte n'affiche que le fond. Les listes restent consultables.");
      } else {
        signaler("tuiles", "Une partie du fond de carte n'a pas pu être chargée (" + message + ").");
      }
    });
    instance.on("load", function () {
      instance.addSource(SOURCE, { type: "vector", url: "pmtiles://" + archive });
      var calque = {
        id: SOURCE, type: "circle", source: SOURCE, "source-layer": d.couche,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 2.5, 12, 6],
          "circle-color": ["match", ["get", "etat"], "actif", "#0969da", "#8c959f"],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1
        }
      };
      if (d.dep) calque.filter = ["==", ["get", "dep"], d.dep];
      instance.addLayer(calque);
      instance.on("click", SOURCE, function (evenement) {
        var point = evenement.features && evenement.features[0];
        if (!point) return;
        new maplibregl.Popup({ maxWidth: "320px" })
          .setLngLat(point.geometry.coordinates.slice())
          .setDOMContent(fenetre(point.properties))
          .addTo(instance);
      });
      instance.on("mouseenter", SOURCE, function () { instance.getCanvas().style.cursor = "pointer"; });
      instance.on("mouseleave", SOURCE, function () { instance.getCanvas().style.cursor = ""; });
    });
    return instance;
  }

  function afficher() {
    // Une nouvelle tentative repart de messages vides.
    while (etat.firstChild) etat.removeChild(etat.firstChild);
    etat.hidden = true;
    signales = {};
    bouton.disabled = true;
    feuille(d.maplibreCss);
    Promise.all([script(d.maplibre), script(d.pmtiles)])
      .then(fond)
      .then(construire)
      .then(function () { commande.hidden = true; })
      .catch(function (erreur) {
        carte.hidden = true;
        bouton.disabled = false;
        signaler("chargement", "La carte n'a pas pu être affichée (" + erreur.message +
          "). Les établissements restent consultables dans les listes ci-dessous ; " +
          "le bouton permet de réessayer.");
      });
  }

  bouton.addEventListener("click", afficher);
  commande.hidden = false;
})();
