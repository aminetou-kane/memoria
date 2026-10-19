/* Espace administrateur : tableau de bord, comptes utilisateurs, UFR. */
(function () {
  const CD = (window.CD = window.CD || {});
  const { h, remplacer, badge, champ, liste, tableau } = CD.ui;
  const erreurCarte = (e) => h("div", { class: "carte erreur-formulaire" }, e.message);

  async function tableauDeBord(conteneur) {
    let ufrs = [];
    try { ufrs = await CD.api.listeUfr(); } catch (e) { /* le filtre reste facultatif */ }
    const filtre = liste("id_ufr", [["", "Toutes les UFR"], ...ufrs.map((u) => [u.id_ufr, u.nom])], "");
    const zone = h("div");
    const recharger = () => CD.stats.afficher(zone, { admin: true, idUfr: filtre.value });
    filtre.addEventListener("change", recharger);
    remplacer(conteneur, 
      h("div", { class: "titre-page" }, h("h1", null, "Tableau de bord"),
        h("div", { class: "champ champ-en-ligne" }, h("label", { for: "filtre-ufr" }, "Afficher :"), Object.assign(filtre, { id: "filtre-ufr" }))),
      zone);
    return recharger();
  }

  /* ----- utilisateurs ----- */
  const optionsUfr = (ufrs) => ufrs.map((u) => [u.id_ufr, u.nom]);

  async function formulaireCreation(role, ufrs, apres) {
    const gest = role === "GESTIONNAIRE";
    const f = {
      nom: h("input", { type: "text", required: true }), prenom: h("input", { type: "text", required: true }),
      email: h("input", { type: "email", required: true, placeholder: "prenom.nom@ugb.edu.sn" }),
      mot_de_passe: h("input", { type: "password", required: true, autocomplete: "new-password" }),
      id_ufr: liste("id_ufr", optionsUfr(ufrs), ""), code_etudiant: h("input", { type: "text", required: true }),
    };
    CD.ui.fenetreFormulaire({
      titre: gest ? "Nouveau gestionnaire" : "Nouvel étudiant",
      libelleOk: "Créer le compte",
      champs: [
        h("div", { class: "ligne-champs" }, champ("Prénom", f.prenom), champ("Nom", f.nom)),
        champ("Email UGB", f.email),
        gest ? [champ("Mot de passe", f.mot_de_passe, "8 caractères minimum."), champ("UFR de rattachement", f.id_ufr)]
             : champ("Code étudiant", f.code_etudiant),
      ],
      soumettre: async () => {
        const base = { nom: f.nom.value, prenom: f.prenom.value, email: f.email.value };
        if (gest) await CD.api.post("/users/gestionnaires", Object.assign(base, { mot_de_passe: f.mot_de_passe.value, id_ufr: Number(f.id_ufr.value) }));
        else await CD.api.post("/users/etudiants", Object.assign(base, { code_etudiant: f.code_etudiant.value }));
        CD.ui.toast("Compte créé.", "succes");
        apres();
      },
    });
  }

  function formulaireModification(u, ufrs, apres) {
    const f = {
      nom: h("input", { type: "text", required: true, value: u.nom }), prenom: h("input", { type: "text", required: true, value: u.prenom }),
      email: h("input", { type: "email", required: true, value: u.email }),
      id_ufr: liste("id_ufr", optionsUfr(ufrs), u.id_ufr), code: h("input", { type: "text", value: u.code_etudiant || "" }),
      mdp: h("input", { type: "password", autocomplete: "new-password" }),
    };
    CD.ui.fenetreFormulaire({
      titre: "Modifier le compte",
      champs: [
        h("div", { class: "ligne-champs" }, champ("Prénom", f.prenom), champ("Nom", f.nom)),
        champ("Email UGB", f.email),
        u.role === "GESTIONNAIRE" ? [champ("UFR de rattachement", f.id_ufr), champ("Nouveau mot de passe", f.mdp, "Laisse vide pour ne pas le changer.")] : null,
        u.role === "ETUDIANT" ? champ("Code étudiant", f.code) : null,
      ],
      soumettre: async () => {
        const corps = { nom: f.nom.value, prenom: f.prenom.value, email: f.email.value };
        if (u.role === "GESTIONNAIRE") {
          corps.id_ufr = Number(f.id_ufr.value);
          if (f.mdp.value) corps.mot_de_passe = f.mdp.value;
        }
        if (u.role === "ETUDIANT") corps.code_etudiant = f.code.value;
        await CD.api.put("/users/" + u.id_utilisateur, corps);
        CD.ui.toast("Compte modifié.", "succes");
        apres();
      },
    });
  }

  async function utilisateurs(conteneur) {
    let ufrs = [];
    try { ufrs = await CD.api.listeUfr(); } catch (e) { /* liste vide */ }
    const q = h("input", { type: "search", placeholder: "Rechercher par nom ou email…", "aria-label": "Rechercher" });
    const role = liste("role", [["", "Tous les rôles"], ["ADMIN", "Administrateurs"], ["GESTIONNAIRE", "Gestionnaires"], ["ETUDIANT", "Étudiants"]], "");
    const zone = h("div", { class: "carte" });

    async function charger() {
      remplacer(zone, CD.ui.chargement());
      try {
        const lignes = await CD.api.get("/users", { q: q.value.trim(), role: role.value });
        remplacer(zone, tableau([
          { titre: "Nom", cellule: (u) => u.nom }, { titre: "Prénom", cellule: (u) => u.prenom }, { titre: "Email", cellule: (u) => u.email },
          { titre: "Rôle", cellule: (u) => badge(CD.ui.ROLES[u.role] || u.role, u.role === "ADMIN" ? "badge-warn" : u.role === "GESTIONNAIRE" ? "badge-info" : "badge-ok") },
          { titre: "UFR / code", cellule: (u) => u.ufr_nom || u.code_etudiant || "" },
          { titre: "Actions", cellule: (u) => (u.role === "ADMIN" ? "" : h("div", { class: "actions" },
            h("button", { class: "btn btn-petit", type: "button", onclick: () => formulaireModification(u, ufrs, charger) }, "Modifier"),
            h("button", { class: "btn btn-petit", type: "button", onclick: async () => {
              if (!(await CD.ui.confirmer("Supprimer le compte de " + u.prenom + " " + u.nom + " ?", "Supprimer"))) return;
              try { await CD.api.supprimer("/users/" + u.id_utilisateur); CD.ui.toast("Compte supprimé.", "succes"); charger(); }
              catch (e) { CD.ui.toast(e.message, "erreur"); }
            } }, "Supprimer"))) },
        ], lignes, "Aucun utilisateur ne correspond."));
      } catch (e) {
        remplacer(zone, erreurCarte(e));
      }
    }

    let minuteur = null;
    q.addEventListener("input", () => { clearTimeout(minuteur); minuteur = setTimeout(charger, 300); });
    role.addEventListener("change", charger);
    remplacer(conteneur, 
      h("div", { class: "titre-page" }, h("h1", null, "Utilisateurs"),
        h("div", { class: "actions" },
          h("button", { class: "btn btn-primaire", type: "button", onclick: () => formulaireCreation("GESTIONNAIRE", ufrs, charger) }, "+ Gestionnaire"),
          h("button", { class: "btn", type: "button", onclick: () => formulaireCreation("ETUDIANT", ufrs, charger) }, "+ Étudiant"))),
      h("div", { class: "barre-outils" }, q, role), zone);
    charger();
  }

  /* ----- UFR ----- */
  function formulaireUfr(ufr, apres) {
    const nom = h("input", { type: "text", required: true, value: ufr ? ufr.nom : "" });
    CD.ui.fenetreFormulaire({
      titre: ufr ? "Renommer l'UFR" : "Nouvelle UFR",
      champs: champ("Nom de l'UFR", nom),
      soumettre: async () => {
        if (ufr) await CD.api.put("/ufr/" + ufr.id_ufr, { nom: nom.value });
        else await CD.api.post("/ufr", { nom: nom.value });
        await CD.api.listeUfr(true);
        CD.ui.toast(ufr ? "UFR renommée." : "UFR créée.", "succes");
        apres();
      },
    });
  }

  async function ufr(conteneur) {
    const zone = h("div", { class: "carte" });
    async function charger() {
      remplacer(zone, CD.ui.chargement());
      try {
        const lignes = await CD.api.get("/statistiques/activite-ufr");
        remplacer(zone, tableau([
          { titre: "UFR / centre de documentation", cellule: (u) => u.nom },
          { titre: "Documents", num: true, cellule: (u) => u.nb_documents },
          { titre: "Téléchargements", num: true, cellule: (u) => u.nb_telechargements },
          { titre: "Actions", cellule: (u) => h("div", { class: "actions" },
            h("button", { class: "btn btn-petit", type: "button", onclick: () => formulaireUfr(u, charger) }, "Renommer"),
            h("button", { class: "btn btn-petit", type: "button", onclick: async () => {
              if (!(await CD.ui.confirmer("Supprimer l'UFR « " + u.nom + " » ?", "Supprimer"))) return;
              try { await CD.api.supprimer("/ufr/" + u.id_ufr); await CD.api.listeUfr(true); CD.ui.toast("UFR supprimée.", "succes"); charger(); }
              catch (e) { CD.ui.toast(e.message, "erreur"); }
            } }, "Supprimer")) },
        ], lignes, "Aucune UFR."));
      } catch (e) {
        remplacer(zone, erreurCarte(e));
      }
    }
    remplacer(conteneur, 
      h("div", { class: "titre-page" }, h("h1", null, "UFR / centres de documentation"),
        h("button", { class: "btn btn-primaire", type: "button", onclick: () => formulaireUfr(null, charger) }, "+ Nouvelle UFR")),
      h("p", { class: "sous-titre" }, "Une UFR ne peut être supprimée que si aucun gestionnaire ni aucun document n'y est rattaché."),
      zone);
    charger();
  }

  CD.admin = { tableauDeBord, utilisateurs, ufr };
})();
