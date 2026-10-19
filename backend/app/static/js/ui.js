/* Outils d'affichage.
   SÉCURITÉ : les pages sont construites avec h() (nœuds DOM + texte brut). Aucune donnée venant de
   l'API n'est jamais insérée comme du HTML, ce qui empêche l'injection de code (XSS). */
(function () {
  const CD = (window.CD = window.CD || {});

  const NIVEAUX = {
    TELECHARGEABLE: { texte: "Téléchargeable", classe: "badge-ok" },
    CONSULTATION_SEULE: { texte: "Consultation seule", classe: "badge-info" },
    RESTREINT: { texte: "Restreint (embargo)", classe: "badge-warn" },
  };
  const TYPES = { THESE: "Thèse", MEMOIRE: "Mémoire" };
  const ROLES = { ADMIN: "Administrateur", GESTIONNAIRE: "Gestionnaire", ETUDIANT: "Étudiant" };
  const PROPRIETES = ["value", "checked", "selected", "disabled", "required"];

  function ajouter(parent, enfants) {
    for (const enfant of enfants.flat(Infinity)) {
      if (enfant === null || enfant === undefined || enfant === false) continue;
      parent.append(enfant instanceof Node ? enfant : document.createTextNode(String(enfant)));
    }
  }

  function h(balise, attributs, ...enfants) {
    const element = document.createElement(balise);
    for (const [cle, valeur] of Object.entries(attributs || {})) {
      if (valeur === null || valeur === undefined || valeur === false) continue;
      if (cle === "class") element.className = valeur;
      else if (cle.startsWith("on") && typeof valeur === "function") element.addEventListener(cle.slice(2), valeur);
      else if (PROPRIETES.includes(cle)) element[cle] = valeur;
      else element.setAttribute(cle, valeur === true ? "" : valeur);
    }
    ajouter(element, enfants);
    return element;
  }

  function vider(noeud) {
    noeud.replaceChildren();
    return noeud;
  }

  /* Remplace le contenu d'un élément. Contrairement à element.append(), ignore null / undefined / false
     (sinon le navigateur écrirait le mot « null » à l'écran). */
  function remplacer(noeud, ...enfants) {
    noeud.replaceChildren();
    ajouter(noeud, enfants);
    return noeud;
  }

  const badge = (texte, classe) => h("span", { class: "badge " + (classe || "") }, texte);

  function badgeNiveau(niveau) {
    const n = NIVEAUX[niveau] || { texte: niveau, classe: "" };
    return badge(n.texte, n.classe);
  }

  function dateFr(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return isNaN(d) ? String(iso) : d.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
  }

  const tronquer = (texte, max) => (texte && texte.length > max ? texte.slice(0, max - 1) + "…" : texte || "");

  function toast(message, type) {
    const zone = document.getElementById("toasts");
    if (!zone) return;
    const element = h("div", { class: "toast toast-" + (type || "info"), role: "status" }, message);
    zone.append(element);
    setTimeout(() => element.remove(), type === "erreur" ? 7000 : 4000);
  }

  function modal({ titre, corps, pied, large, onFermer }) {
    const racine = document.getElementById("modal-root");
    const fond = h("div", { class: "modal-fond" });
    const surEchap = (e) => { if (e.key === "Escape") fermer(); };
    function fermer() {
      document.removeEventListener("keydown", surEchap);
      fond.remove();
      if (onFermer) onFermer();
    }
    const boite = h(
      "div",
      { class: "modal" + (large ? " modal-large" : ""), role: "dialog", "aria-modal": "true", "aria-label": titre },
      h("div", { class: "modal-entete" }, h("h2", null, titre),
        h("button", { class: "btn-icone", type: "button", "aria-label": "Fermer", onclick: fermer }, "×")),
      h("div", { class: "modal-corps" }, corps),
      pied ? h("div", { class: "modal-pied" }, pied) : null
    );
    fond.addEventListener("mousedown", (e) => { if (e.target === fond) fermer(); });
    document.addEventListener("keydown", surEchap);
    fond.append(boite);
    racine.append(fond);
    const premier = boite.querySelector("input, select, textarea");
    if (premier) premier.focus();
    return { fermer, boite };
  }

  function confirmer(message, libelleOk) {
    return new Promise((resolve) => {
      let resultat = false;
      const fenetre = modal({
        titre: "Confirmation",
        corps: h("p", null, message),
        pied: [
          h("button", { class: "btn", type: "button", onclick: () => fenetre.fermer() }, "Annuler"),
          h("button", { class: "btn btn-danger", type: "button", onclick: () => { resultat = true; fenetre.fermer(); } },
            libelleOk || "Confirmer"),
        ],
        onFermer: () => resolve(resultat),
      });
    });
  }

  function champ(etiquette, controle, aide) {
    const id = "champ-" + Math.random().toString(36).slice(2, 9);
    controle.id = id;
    return h("div", { class: "champ" }, h("label", { for: id }, etiquette), controle, aide ? h("div", { class: "aide" }, aide) : null);
  }

  function liste(nom, options, valeur) {
    const s = h("select", { name: nom });
    for (const [v, libelle] of options) s.append(h("option", { value: v, selected: String(v) === String(valeur ?? "") }, libelle));
    return s;
  }

  /* Fenêtre contenant un formulaire. `soumettre()` lève une erreur => son message s'affiche dans la fenêtre. */
  function fenetreFormulaire({ titre, champs, libelleOk, large, soumettre }) {
    const idForm = "form-" + Math.random().toString(36).slice(2, 9);
    const erreur = h("div", { class: "erreur-formulaire", hidden: true });
    const form = h("form", { id: idForm }, erreur, champs);
    const ok = h("button", { class: "btn btn-primaire", type: "submit", form: idForm }, libelleOk || "Enregistrer");
    const fenetre = modal({
      titre, large, corps: form,
      pied: [h("button", { class: "btn", type: "button", onclick: () => fenetre.fermer() }, "Annuler"), ok],
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      erreur.hidden = true;
      ok.disabled = true;
      try {
        await soumettre();
        fenetre.fermer();
      } catch (err) {
        erreur.textContent = err.message;
        erreur.hidden = false;
        ok.disabled = false;
      }
    });
    return fenetre;
  }

  const messageVide = (texte) => h("div", { class: "vide" }, texte);
  const chargement = (texte) => h("div", { class: "chargement" }, texte || "Chargement…");

  function tableau(colonnes, lignes, vide) {
    if (!lignes.length) return messageVide(vide || "Aucun élément.");
    return h("div", { class: "tableau-conteneur" },
      h("table", null,
        h("thead", null, h("tr", null, colonnes.map((c) => h("th", { class: c.num ? "num" : null }, c.titre)))),
        h("tbody", null, lignes.map((ligne) =>
          h("tr", null, colonnes.map((c) => h("td", { class: c.num ? "num" : null }, c.cellule(ligne)))))))
    );
  }

  CD.ui = { NIVEAUX, TYPES, ROLES, h, vider, remplacer, badge, badgeNiveau, dateFr, tronquer, toast, modal, confirmer, fenetreFormulaire, champ, liste, messageVide, chargement, tableau };
})();
