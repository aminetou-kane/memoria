/* Espace étudiant : recherche de documents, fiche détaillée, téléchargement, historique personnel. */
(function () {
  const CD = (window.CD = window.CD || {});
  const { h, remplacer, badge, badgeNiveau, dateFr, champ, liste, tableau } = CD.ui;
  const TAILLE = 10;

  async function telechargerDocument(id, bouton) {
    if (bouton) bouton.disabled = true;
    try {
      await CD.api.telecharger("/documents/" + id + "/download", null, "document.pdf");
      CD.ui.toast("Téléchargement terminé.", "succes");
    } catch (e) {
      CD.ui.toast(e.message, "erreur");
    } finally {
      if (bouton) bouton.disabled = false;
    }
  }

  async function ouvrirFiche(id) {
    try {
      const d = await CD.api.get("/documents/" + id);
      const bouton = h("button", { class: "btn btn-primaire", type: "button", onclick: () => telechargerDocument(id, bouton) }, "Télécharger le PDF");
      const fenetre = CD.ui.modal({
        titre: d.titre,
        large: true,
        corps: [
          h("div", { class: "puces" }, badgeNiveau(d.niveau_acces), badge(CD.ui.TYPES[d.type] || d.type), d.discipline ? badge(d.discipline) : null),
          h("dl", { class: "definitions" },
            h("dt", null, "Auteur"), h("dd", null, d.auteur),
            d.encadrant ? [h("dt", null, "Encadrant"), h("dd", null, d.encadrant)] : null,
            h("dt", null, "Année"), h("dd", null, String(d.annee)),
            h("dt", null, "UFR"), h("dd", null, d.ufr_nom),
            d.mots_cles.length ? [h("dt", null, "Mots-clés"), h("dd", null, h("div", { class: "puces" }, d.mots_cles.map((m) => h("span", { class: "puce" }, m))))] : null),
          h("h3", null, "Résumé"),
          d.resume ? h("div", { class: "texte-resume" }, d.resume) : h("p", { class: "note" }, "Aucun résumé disponible."),
        ],
        pied: [
          d.telechargeable ? null : h("span", { class: "note" }, "Consultation seule : le PDF n'est pas téléchargeable."),
          h("button", { class: "btn", type: "button", onclick: () => fenetre.fermer() }, "Fermer"),
          d.telechargeable ? bouton : null,
        ],
      });
    } catch (e) {
      CD.ui.toast(e.message, "erreur");
    }
  }

  function carteDocument(d) {
    const bouton = h("button", { class: "btn btn-petit btn-primaire", type: "button", onclick: () => telechargerDocument(d.id_document, bouton) }, "Télécharger le PDF");
    return h("article", { class: "carte resultat" },
      h("h3", null, h("button", { class: "btn-lien", type: "button", onclick: () => ouvrirFiche(d.id_document) }, d.titre)),
      h("div", { class: "meta" }, d.auteur + " · " + d.annee + " · " + d.ufr_nom),
      h("div", { class: "puces" }, badgeNiveau(d.niveau_acces), badge(CD.ui.TYPES[d.type] || d.type), d.discipline ? badge(d.discipline) : null,
        d.mots_cles.map((m) => h("span", { class: "puce" }, m))),
      d.extrait ? h("p", { class: "extrait" }, d.extrait) : null,
      h("div", { class: "pied-resultat" },
        h("button", { class: "btn btn-petit", type: "button", onclick: () => ouvrirFiche(d.id_document) }, "Voir la fiche"),
        d.telechargeable ? bouton : null)
    );
  }

  async function recherche(conteneur) {
    const etat = { page: 1 };
    let compteur = 0;
    let ufrs = [];
    try { ufrs = await CD.api.listeUfr(); } catch (e) { /* les filtres restent utilisables sans la liste */ }

    const q = h("input", { type: "search", name: "q", placeholder: "Titre, auteur, mot-clé, sujet…", "aria-label": "Rechercher" });
    const annee = h("input", { type: "number", name: "annee", min: "1950", max: "2100" });
    const ufr = liste("id_ufr", [["", "Toutes les UFR"], ...ufrs.map((u) => [u.id_ufr, u.nom])], "");
    const discipline = h("input", { type: "text", name: "discipline" });
    const type = liste("type", [["", "Tous"], ["THESE", "Thèse"], ["MEMOIRE", "Mémoire"]], "");
    const motCle = h("input", { type: "text", name: "mot_cle" });
    const telechargeable = h("input", { type: "checkbox", name: "telechargeable" });
    const zone = h("div");

    const form = h("form", { class: "carte", role: "search" },
      h("div", { class: "recherche-principale" }, q, h("button", { class: "btn btn-primaire", type: "submit" }, "Rechercher")),
      h("details", { class: "filtres" }, h("summary", null, "Filtres avancés"),
        h("div", { class: "ligne-champs" },
          champ("Année", annee), champ("UFR", ufr), champ("Discipline", discipline), champ("Type", type),
          champ("Mot-clé exact", motCle)),
        h("label", { class: "coche" }, telechargeable, "Uniquement les documents dont le PDF est téléchargeable"))
    );
    form.addEventListener("submit", (e) => { e.preventDefault(); etat.page = 1; lancer(); });

    async function lancer() {
      const moi = ++compteur;
      remplacer(zone, CD.ui.chargement("Recherche…"));
      try {
        const rep = await CD.api.get("/documents/recherche", {
          q: q.value.trim(), annee: annee.value, id_ufr: ufr.value, discipline: discipline.value.trim(),
          type: type.value, mot_cle: motCle.value.trim(), telechargeable: telechargeable.checked ? "true" : "",
          page: etat.page, taille: TAILLE,
        });
        if (moi !== compteur) return;   // une recherche plus récente a déjà répondu
        const pages = Math.max(1, Math.ceil(rep.total / rep.taille));
        remplacer(zone, 
          h("div", { class: "resume-compteur" },
            rep.total === 0 ? "Aucun document ne correspond à ta recherche."
              : rep.total + (rep.total > 1 ? " documents trouvés" : " document trouvé") + " · page " + rep.page + " sur " + pages),
          h("div", { class: "grille" }, rep.resultats.map(carteDocument)),
          rep.total > rep.taille ? h("div", { class: "pagination" },
            h("button", { class: "btn btn-petit", type: "button", disabled: rep.page <= 1, onclick: () => { etat.page--; lancer(); } }, "← Précédent"),
            "Page " + rep.page + " / " + pages,
            h("button", { class: "btn btn-petit", type: "button", disabled: rep.page >= pages, onclick: () => { etat.page++; lancer(); } }, "Suivant →")) : null
        );
      } catch (e) {
        if (moi === compteur) remplacer(zone, h("div", { class: "carte erreur-formulaire" }, e.message));
      }
    }

    remplacer(conteneur, 
      h("div", { class: "titre-page" }, h("h1", null, "Rechercher un document")),
      h("p", { class: "sous-titre" }, "Thèses et mémoires des centres de documentation. Les documents sous embargo ne sont pas affichés."),
      form, zone);
    lancer();
  }

  async function telechargements(conteneur) {
    remplacer(conteneur, h("div", { class: "titre-page" }, h("h1", null, "Mes téléchargements")), CD.ui.chargement());
    try {
      const lignes = await CD.api.get("/telechargements/moi");
      remplacer(conteneur, 
        h("div", { class: "titre-page" }, h("h1", null, "Mes téléchargements")),
        h("div", { class: "carte" }, tableau([
          { titre: "Document", cellule: (l) => l.titre }, { titre: "Auteur", cellule: (l) => l.auteur },
          { titre: "Date", cellule: (l) => dateFr(l.date_telechargement) },
        ], lignes, "Tu n'as encore téléchargé aucun document.")));
    } catch (e) {
      remplacer(conteneur, h("div", { class: "carte erreur-formulaire" }, e.message));
    }
  }

  CD.etudiant = { recherche, telechargements };
})();
