/* Espace gestionnaire : documents de son UFR, historique des téléchargements, statistiques. */
(function () {
  const CD = (window.CD = window.CD || {});
  const { h, remplacer, badge, badgeNiveau, dateFr, champ, liste, tableau } = CD.ui;

  const erreurCarte = (e) => h("div", { class: "carte erreur-formulaire" }, e.message);
  const nomEtudiant = (l) => l.prenom + " " + l.nom;
  const colonnesHistorique = [
    { titre: "Date", cellule: (l) => dateFr(l.date_telechargement) },
    { titre: "Document", cellule: (l) => l.titre },
    { titre: "Étudiant", cellule: nomEtudiant },
    { titre: "Code étudiant", cellule: (l) => l.code_etudiant || "" },
    { titre: "Email", cellule: (l) => l.email },
  ];

  /* Sélecteur de fichier avec des textes en français (ceux du navigateur dépendent de sa langue). */
  function champFichierPdf(input, libelle, aide) {
    const id = "champ-fichier-" + Math.random().toString(36).slice(2, 8);
    const aucun = "Aucun fichier choisi";
    const nom = h("span", { class: "nom-fichier" }, aucun);
    input.id = id;
    input.hidden = true;
    input.addEventListener("change", () => { nom.textContent = input.files && input.files[0] ? input.files[0].name : aucun; });
    return h("div", { class: "champ" }, h("label", { for: id }, libelle),
      h("div", { class: "selecteur-fichier" }, h("label", { class: "btn btn-petit", for: id }, "Choisir un fichier PDF"), nom, input),
      aide ? h("div", { class: "aide" }, aide) : null);
  }

  /* ----- création / modification d'un document ----- */
  function formulaireDocument(doc, apres) {
    const edition = Boolean(doc);
    const f = {
      titre: h("input", { type: "text", name: "titre", required: true, value: edition ? doc.titre : "" }),
      auteur: h("input", { type: "text", name: "auteur", required: true, value: edition ? doc.auteur : "" }),
      encadrant: h("input", { type: "text", name: "encadrant", value: edition ? doc.encadrant || "" : "" }),
      annee: h("input", { type: "number", name: "annee", required: true, min: "1950", max: "2100", value: edition ? doc.annee : new Date().getFullYear() }),
      type: liste("type", [["MEMOIRE", "Mémoire"], ["THESE", "Thèse"]], edition ? doc.type : "MEMOIRE"),
      discipline: h("input", { type: "text", name: "discipline", value: edition ? doc.discipline || "" : "" }),
      niveau_acces: liste("niveau_acces", [["TELECHARGEABLE", "Téléchargeable"], ["CONSULTATION_SEULE", "Consultation seule (métadonnées et résumé)"], ["RESTREINT", "Restreint (embargo)"]],
        edition ? doc.niveau_acces : "CONSULTATION_SEULE"),
      resume: h("textarea", { name: "resume" }, edition ? doc.resume || "" : ""),
      mots_cles: h("input", { type: "text", name: "mots_cles", value: edition ? doc.mots_cles.join(", ") : "" }),
      fichier: h("input", { type: "file", name: "fichier", accept: "application/pdf,.pdf" }),
    };
    CD.ui.fenetreFormulaire({
      titre: edition ? "Modifier le document" : "Ajouter un document",
      large: true,
      libelleOk: edition ? "Enregistrer" : "Ajouter",
      champs: [
        champ("Titre", f.titre),
        h("div", { class: "ligne-champs" }, champ("Auteur (étudiant rédacteur)", f.auteur), champ("Encadrant", f.encadrant)),
        h("div", { class: "ligne-champs" }, champ("Année", f.annee), champ("Type", f.type), champ("Discipline", f.discipline)),
        champ("Niveau d'accès", f.niveau_acces),
        champ("Résumé", f.resume),
        champ("Mots-clés", f.mots_cles, "Séparés par des virgules, par exemple : irrigation, agriculture, Sénégal"),
        champFichierPdf(f.fichier, edition ? "Remplacer le PDF (facultatif)" : "Fichier PDF",
          edition && doc.pdf_disponible ? "Un PDF est déjà enregistré : laisse vide pour le conserver." : "Obligatoire pour un document téléchargeable."),
      ],
      soumettre: async () => {
        const fichier = f.fichier.files && f.fichier.files[0];
        if (f.niveau_acces.value === "TELECHARGEABLE" && !fichier && !(edition && doc.pdf_disponible)) {
          throw new Error("Un document téléchargeable doit avoir un fichier PDF.");
        }
        const donnees = new FormData();
        for (const nom of ["titre", "auteur", "annee", "type", "niveau_acces", "encadrant", "discipline", "resume", "mots_cles"]) {
          donnees.append(nom, f[nom].value);
        }
        if (fichier) donnees.append("fichier", fichier);
        if (edition) await CD.api.putFormulaire("/documents/" + doc.id_document, donnees);
        else await CD.api.postFormulaire("/documents", donnees);
        CD.ui.toast(edition ? "Document modifié." : "Document ajouté.", "succes");
        apres();
      },
    });
  }

  /* ----- disponibilité + historique d'un document ----- */
  async function detailsDocument(doc) {
    try {
      const [dispo, historique] = await Promise.all([
        CD.api.get("/documents/" + doc.id_document + "/disponibilite"),
        CD.api.get("/telechargements/document/" + doc.id_document),
      ]);
      const fenetre = CD.ui.modal({
        titre: doc.titre,
        large: true,
        corps: [
          h("dl", { class: "definitions" },
            h("dt", null, "Niveau d'accès"), h("dd", null, badgeNiveau(dispo.niveau_acces)),
            h("dt", null, "PDF enregistré"), h("dd", null, dispo.pdf_disponible ? "Oui" : "Non"),
            h("dt", null, "Téléchargeable"), h("dd", null, dispo.telechargeable ? "Oui" : "Non"),
            h("dt", null, "Téléchargements"), h("dd", null, String(dispo.nb_telechargements)),
            h("dt", null, "Dernier"), h("dd", null, dispo.dernier_telechargement ? dateFr(dispo.dernier_telechargement) : "—")),
          h("h3", null, "Historique des téléchargements"),
          tableau(colonnesHistorique.filter((c) => c.titre !== "Document"), historique, "Ce document n'a pas encore été téléchargé."),
        ],
        pied: h("button", { class: "btn", type: "button", onclick: () => fenetre.fermer() }, "Fermer"),
      });
    } catch (e) {
      CD.ui.toast(e.message, "erreur");
    }
  }

  async function documents(conteneur) {
    const q = h("input", { type: "search", placeholder: "Filtrer par titre ou auteur…", "aria-label": "Filtrer" });
    const zone = h("div", { class: "carte" });

    async function charger() {
      remplacer(zone, CD.ui.chargement());
      try {
        const docs = await CD.api.get("/documents/gestion", { q: q.value.trim() });
        remplacer(zone, tableau([
          { titre: "Titre", cellule: (d) => h("button", { class: "btn-lien", type: "button", onclick: () => detailsDocument(d) }, d.titre) },
          { titre: "Auteur", cellule: (d) => d.auteur },
          { titre: "Année", cellule: (d) => d.annee },
          { titre: "Type", cellule: (d) => CD.ui.TYPES[d.type] || d.type },
          { titre: "Accès", cellule: (d) => badgeNiveau(d.niveau_acces) },
          { titre: "PDF", cellule: (d) => (d.pdf_disponible ? "✔" : "—") },
          { titre: "Actions", cellule: (d) => h("div", { class: "actions" },
            h("button", { class: "btn btn-petit", type: "button", onclick: () => formulaireDocument(d, charger) }, "Modifier"),
            h("button", { class: "btn btn-petit", type: "button", onclick: async () => {
              if (!(await CD.ui.confirmer("Supprimer définitivement « " + d.titre + " » et son historique de téléchargements ?", "Supprimer"))) return;
              try { await CD.api.supprimer("/documents/" + d.id_document); CD.ui.toast("Document supprimé.", "succes"); charger(); }
              catch (e) { CD.ui.toast(e.message, "erreur"); }
            } }, "Supprimer")) },
        ], docs, q.value.trim() ? "Aucun document ne correspond." : "Aucun document pour le moment. Clique sur « Ajouter un document »."));
      } catch (e) {
        remplacer(zone, erreurCarte(e));
      }
    }

    let minuteur = null;
    q.addEventListener("input", () => { clearTimeout(minuteur); minuteur = setTimeout(charger, 300); });
    remplacer(conteneur, 
      h("div", { class: "titre-page" }, h("h1", null, "Mes documents"),
        h("button", { class: "btn btn-primaire", type: "button", onclick: () => formulaireDocument(null, charger) }, "+ Ajouter un document")),
      h("p", { class: "sous-titre" }, "Thèses et mémoires de ton UFR. Clique sur un titre pour voir sa disponibilité et son historique."),
      h("div", { class: "barre-outils" }, q), zone);
    charger();
  }

  async function historique(conteneur) {
    remplacer(conteneur, h("div", { class: "titre-page" }, h("h1", null, "Téléchargements de mon UFR")), CD.ui.chargement());
    try {
      const lignes = await CD.api.get("/telechargements/gestion");
      remplacer(conteneur, 
        h("div", { class: "titre-page" }, h("h1", null, "Téléchargements de mon UFR")),
        h("div", { class: "carte" }, tableau(colonnesHistorique, lignes, "Aucun document de ton UFR n'a encore été téléchargé.")));
    } catch (e) {
      remplacer(conteneur, erreurCarte(e));
    }
  }

  function statistiques(conteneur) {
    const zone = h("div");
    remplacer(conteneur, h("div", { class: "titre-page" }, h("h1", null, "Statistiques de mon UFR")), zone);
    return CD.stats.afficher(zone, { admin: false });
  }

  CD.gestionnaire = { documents, historique, statistiques };
})();
