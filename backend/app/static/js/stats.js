/* Tableau de bord : chiffres clés, graphiques (Chart.js), tableaux et exports CSV.
   Utilisé par l'administrateur (tout le fonds) et par le gestionnaire (son UFR). */
(function () {
  const CD = (window.CD = window.CD || {});
  const { h, remplacer, tronquer, tableau, dateFr } = CD.ui;

  const PALETTE = ["#0f5c8c", "#d97706", "#1b7f4b", "#7c3aed", "#dc2626", "#0891b2", "#65a30d", "#db2777", "#475569", "#ca8a04"];
  const COULEURS_NIVEAU = { TELECHARGEABLE: "#1b7f4b", CONSULTATION_SEULE: "#1d5fa8", RESTREINT: "#d97706" };
  const ECHELLE_ENTIERE = { beginAtZero: true, ticks: { precision: 0 } };

  let graphiques = [];
  function detruire() {
    graphiques.forEach((g) => g.destroy());
    graphiques = [];
  }

  function kpi(valeur, libelle, classe) {
    return h("div", { class: "carte kpi " + (classe || "") },
      h("div", { class: "valeur" }, String(valeur)), h("div", { class: "libelle" }, libelle));
  }

  /* Carte contenant un graphique ; `aTracer` reçoit la fonction qui dessine une fois la carte dans la page. */
  function carteGraphique(titre, vide, construire, aTracer, haut) {
    if (vide) return h("div", { class: "carte" }, h("h3", null, titre), CD.ui.messageVide(vide));
    const canvas = h("canvas");
    aTracer.push(() => {
      if (!window.Chart) return;
      graphiques.push(new window.Chart(canvas, construire()));
    });
    return h("div", { class: "carte" }, h("h3", null, titre),
      h("div", { class: "graphique" + (haut ? " haut" : "") }, canvas));
  }

  const tracer = (type, labels, datasets, options) => ({
    type,
    data: { labels, datasets },
    options: Object.assign({ responsive: true, maintainAspectRatio: false }, options),
  });

  /* « q=drone agricole | annee=2025 » devient « drone agricole · année 2025 » */
  const LIBELLES_CRITERES = { annee: "année", discipline: "discipline", mot_cle: "mot-clé", type: "type", id_ufr: "UFR n°", telechargeable: "téléchargeable" };
  function recherchePourHumains(requete) {
    return requete.split(" | ").map((morceau) => {
      const i = morceau.indexOf("=");
      if (i < 0) return morceau;
      const cle = morceau.slice(0, i), valeur = morceau.slice(i + 1);
      if (cle === "q") return valeur;
      return (LIBELLES_CRITERES[cle] || cle) + (cle === "id_ufr" ? "" : " ") + valeur;
    }).join(" · ");
  }

  async function afficher(conteneur, { admin, idUfr }) {
    detruire();
    remplacer(conteneur, CD.ui.chargement("Calcul des statistiques…"));
    const api = CD.api;
    const p = idUfr ? { id_ufr: idUfr } : {};
    try {
      const demandes = [
        api.get("/statistiques/globales", p),
        api.get("/statistiques/top-documents", Object.assign({ limite: 8 }, p)),
        api.get("/statistiques/repartition/discipline", p),
        api.get("/statistiques/repartition/annee", p),
        api.get("/statistiques/repartition/niveau_acces", p),
        api.get("/statistiques/documents-restreints", p),
      ];
      if (admin) demandes.push(api.get("/statistiques/activite-ufr", p), api.get("/statistiques/recherches-sans-resultat", { limite: 10 }));
      const [glob, top, disc, ann, niveaux, restreints, activite, sans] = await Promise.all(demandes);

      const aTracer = [];
      const tel = glob.telechargements;
      const cartes = [
        kpi(glob.documents.total, "documents dans le fonds"),
        kpi(tel.total, "téléchargements (" + tel.derniers_30_jours + " sur les 30 derniers jours)"),
        kpi(tel.etudiants_distincts, "étudiants ayant téléchargé"),
        kpi(glob.documents.par_niveau_acces.RESTREINT, "documents sous embargo", "alerte"),
      ];
      if (glob.utilisateurs) {
        const u = glob.utilisateurs;
        cartes.push(kpi(u.ADMIN + u.GESTIONNAIRE + u.ETUDIANT, "utilisateurs (" + u.ETUDIANT + " étudiants, " + u.GESTIONNAIRE + " gestionnaires)"));
      }
      if (glob.recherches) cartes.push(kpi(glob.recherches.total, "recherches (" + glob.recherches.sans_resultat + " sans résultat)"));

      const graphs = [
        carteGraphique("Documents les plus téléchargés", top.length ? null : "Aucun téléchargement pour le moment.",
          () => tracer("bar", top.map((d) => tronquer(d.titre, 38)),
            [{ label: "Téléchargements", data: top.map((d) => d.nb_telechargements), backgroundColor: PALETTE[0] }],
            { indexAxis: "y", plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => top[c[0].dataIndex].titre } } },
              scales: { x: ECHELLE_ENTIERE } }), aTracer, true),
        carteGraphique("Niveaux d'accès des documents", glob.documents.total ? null : "Aucun document dans le fonds.",
          () => tracer("doughnut", niveaux.map((n) => (CD.ui.NIVEAUX[n.libelle] || { texte: n.libelle }).texte),
            [{ data: niveaux.map((n) => n.nb_documents), backgroundColor: niveaux.map((n) => COULEURS_NIVEAU[n.libelle] || PALETTE[8]) }],
            { plugins: { legend: { position: "bottom" } } }), aTracer, true),
        carteGraphique("Répartition par discipline", disc.length ? null : "Aucun document dans le fonds.",
          () => { const d = disc.slice(0, 10); return tracer("bar", d.map((x) => tronquer(x.libelle, 24)),
            [{ label: "Documents", data: d.map((x) => x.nb_documents), backgroundColor: PALETTE[2] }],
            { plugins: { legend: { display: false } }, scales: { y: ECHELLE_ENTIERE } }); }, aTracer),
        carteGraphique("Documents par année", ann.length ? null : "Aucun document dans le fonds.",
          () => tracer("bar", ann.map((x) => x.libelle),
            [{ label: "Documents", data: ann.map((x) => x.nb_documents), backgroundColor: PALETTE[1] }],
            { plugins: { legend: { display: false } }, scales: { y: ECHELLE_ENTIERE } }), aTracer),
      ];
      if (admin && !idUfr) {
        graphs.push(carteGraphique("Activité par UFR", activite.some((a) => a.nb_documents || a.nb_telechargements) ? null : "Aucune activité pour le moment.",
          () => tracer("bar", activite.map((a) => tronquer(a.nom.replace(/^UFR\s+/, ""), 30)),
            [{ label: "Documents", data: activite.map((a) => a.nb_documents), backgroundColor: PALETTE[0] },
             { label: "Téléchargements", data: activite.map((a) => a.nb_telechargements), backgroundColor: PALETTE[1] }],
            { indexAxis: "y", plugins: { legend: { position: "bottom" } }, scales: { x: ECHELLE_ENTIERE } }), aTracer, true));
      }

      const tableaux = [
        h("div", { class: "carte" }, h("h3", null, "Documents en accès restreint (" + restreints.length + ")"),
          tableau([
            { titre: "Titre", cellule: (d) => d.titre }, { titre: "Auteur", cellule: (d) => d.auteur },
            { titre: "Année", cellule: (d) => d.annee }, { titre: "UFR", cellule: (d) => d.ufr_nom },
          ], restreints, "Aucun document sous embargo.")),
      ];
      if (admin) {
        tableaux.push(h("div", { class: "carte" }, h("h3", null, "Recherches sans résultat"),
          h("p", { class: "note" }, "Ce que les étudiants ont cherché sans rien trouver : une piste pour enrichir le fonds (aucune identité n'est enregistrée ici)."),
          tableau([
            { titre: "Recherche", cellule: (r) => recherchePourHumains(r.requete) }, { titre: "Fois", num: true, cellule: (r) => r.nb_fois },
            { titre: "Dernière fois", cellule: (r) => dateFr(r.derniere_recherche) },
          ], sans, "Toutes les recherches ont donné des résultats.")));
      }

      const exports = [["top-documents", "Documents les plus téléchargés"], ["activite-ufr", "Activité par UFR"],
        ["repartition-discipline", "Répartition par discipline"], ["repartition-annee", "Répartition par année"],
        ["documents-restreints", "Documents restreints"]];
      if (admin) exports.push(["recherches-sans-resultat", "Recherches sans résultat"]);
      const boutonsExport = h("div", { class: "carte" }, h("h3", null, "Exporter en CSV (Excel)"),
        h("div", { class: "actions" }, exports.map(([jeu, libelle]) =>
          h("button", { class: "btn btn-petit", type: "button", onclick: async () => {
            try { await api.telecharger("/statistiques/export/" + jeu, p, jeu + ".csv"); CD.ui.toast("Export « " + libelle + " » téléchargé.", "succes"); }
            catch (e) { CD.ui.toast(e.message, "erreur"); }
          } }, libelle))));

      remplacer(conteneur, 
        h("div", { class: "grille grille-kpi" }, cartes),
        h("div", { class: "grille grille-graphiques" }, graphs),
        h("div", { class: "grille" }, tableaux),
        h("div", { style: "margin-top:16px" }, boutonsExport)
      );
      aTracer.forEach((f) => f());
    } catch (e) {
      remplacer(conteneur, h("div", { class: "carte erreur-formulaire" }, e.message));
    }
  }

  CD.stats = { afficher, detruire };
})();
