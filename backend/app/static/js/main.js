/* Point d'entrée : connexion, mise en page selon le rôle, navigation par « # ». */
(function () {
  const CD = (window.CD = window.CD || {});
  const { h, remplacer } = CD.ui;
  const racine = document.getElementById("app");

  const MENUS = {
    ETUDIANT: [["recherche", "Rechercher", CD.etudiant.recherche], ["telechargements", "Mes téléchargements", CD.etudiant.telechargements]],
    GESTIONNAIRE: [["documents", "Mes documents", CD.gestionnaire.documents], ["historique", "Téléchargements", CD.gestionnaire.historique],
      ["statistiques", "Statistiques", CD.gestionnaire.statistiques]],
    ADMIN: [["tableau", "Tableau de bord", CD.admin.tableauDeBord], ["utilisateurs", "Utilisateurs", CD.admin.utilisateurs], ["ufr", "UFR", CD.admin.ufr]],
  };

  let menuActif = null;   // null tant que personne n'est connecté
  let contenu = null;

  function afficherConnexion(message) {
    menuActif = null;
    CD.stats.detruire();
    remplacer(racine, CD.auth.vue(demarrer, message));
  }
  CD.surDeconnexion = afficherConnexion;

  function route() {
    if (!menuActif) return;
    const id = location.hash.replace(/^#\/?/, "");
    const element = menuActif.find((m) => m[0] === id) || menuActif[0];
    document.querySelectorAll(".menu a").forEach((a) => {
      if (a.dataset.vue === element[0]) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    document.title = element[1] + " - " + CD.config.nom;
    CD.stats.detruire();
    Promise.resolve()
      .then(() => element[2](contenu))
      .catch((e) => remplacer(contenu, h("div", { class: "carte erreur-formulaire" }, e.message)));
  }

  async function demarrer() {
    const session = CD.api.session();
    if (!session) return afficherConnexion();
    let moi;
    try {
      moi = await CD.api.get("/auth/me");
    } catch (e) {
      CD.api.fermerSession();
      return afficherConnexion(e.statut === 401 ? null : e.message);
    }
    let ufrNom = "";
    if (moi.role === "GESTIONNAIRE") {
      try { ufrNom = ((await CD.api.listeUfr()).find((u) => u.id_ufr === moi.id_ufr) || {}).nom || ""; } catch (e) { /* facultatif */ }
    }

    menuActif = MENUS[moi.role];
    contenu = h("main", { class: "contenu", id: "contenu" });
    remplacer(racine, 
      h("header", { class: "entete" },
        h("div", { class: "marque" }, h("img", { class: "logo", src: "img/logo.svg", alt: "" }), CD.config.nom),
        h("div", { class: "utilisateur" },
          h("span", null, moi.prenom + " " + moi.nom),
          h("span", { class: "role" }, (CD.ui.ROLES[moi.role] || moi.role) + (ufrNom ? " · " + ufrNom.replace(/^UFR\s+/, "") : "")),
          h("button", { class: "btn btn-petit", type: "button", onclick: () => { CD.api.fermerSession(); location.hash = ""; afficherConnexion(); } }, "Déconnexion"))),
      h("div", { class: "disposition" },
        h("nav", { class: "menu", "aria-label": "Navigation principale" },
          menuActif.map(([id, libelle]) => h("a", { href: "#/" + id, "data-vue": id }, libelle))),
        contenu)
    );
    route();
  }

  window.addEventListener("hashchange", route);
  CD.config.charger().then(demarrer);
})();
