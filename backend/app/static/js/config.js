/* Nom de l'application : il vient du serveur (fichier backend/.env : APP_NOM et APP_SOUS_TITRE).
   Les valeurs ci-dessous ne servent que de secours si le serveur ne répond pas. */
(function () {
  const CD = (window.CD = window.CD || {});
  CD.config = {
    nom: "Mémoria",
    sousTitre: "Gestion et recherche des thèses et mémoires",
    comptesDemo: [],   // rempli par le serveur seulement en mode démonstration (DEMO_MODE=true)
    async charger() {
      try {
        const reponse = await fetch("/sante");
        if (reponse.ok) {
          const donnees = await reponse.json();
          if (donnees.application) this.nom = donnees.application;
          if (donnees.sous_titre) this.sousTitre = donnees.sous_titre;
          this.comptesDemo = Array.isArray(donnees.comptes_demo) ? donnees.comptes_demo : [];
        }
      } catch (e) { /* on garde les valeurs de secours */ }
      document.title = this.nom;
    },
  };
})();
