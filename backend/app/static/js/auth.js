/* Page de connexion : étudiant (sans mot de passe) ou administrateur / gestionnaire. */
(function () {
  const CD = (window.CD = window.CD || {});
  const { h, champ } = CD.ui;

  function vue(onConnecte, message) {
    let onglet = "etudiant";
    let preRemplissage = null;   // compte de test choisi : valeurs à placer dans le formulaire
    const boite = h("div", { class: "boite-connexion" });
    const racine = h("div", { class: "page-connexion" }, boite);

    function formulaire() {
      const erreur = h("div", { class: "erreur-formulaire", hidden: true });
      const etudiant = onglet === "etudiant";
      const champs = etudiant
        ? [
            h("div", { class: "ligne-champs" },
              champ("Prénom", h("input", { type: "text", name: "prenom", required: true, autocomplete: "given-name" })),
              champ("Nom", h("input", { type: "text", name: "nom", required: true, autocomplete: "family-name" }))),
            champ("Email UGB", h("input", { type: "email", name: "email", required: true, placeholder: "prenom.nom@ugb.edu.sn" })),
            champ("Code étudiant", h("input", { type: "text", name: "code_etudiant", required: true, autocomplete: "off" })),
          ]
        : [
            champ("Email UGB", h("input", { type: "email", name: "email", required: true, placeholder: "prenom.nom@ugb.edu.sn", autocomplete: "username" })),
            champ("Mot de passe", h("input", { type: "password", name: "mot_de_passe", required: true, autocomplete: "current-password" })),
            h("label", { class: "coche", style: "margin-bottom:12px" },
              h("input", { type: "checkbox", class: "afficher-mdp", onchange: (e) => {
                const saisie = e.target.closest("form").querySelector("[name=mot_de_passe]");
                saisie.type = e.target.checked ? "text" : "password";
              } }), "Afficher le mot de passe"),
          ];
      const bouton = h("button", { class: "btn btn-primaire", type: "submit", style: "width:100%" }, "Se connecter");
      const form = h("form", null, erreur, champs, bouton);
      if (preRemplissage) {
        for (const [nom, valeur] of Object.entries(preRemplissage)) {
          const saisie = form.querySelector(`[name="${nom}"]`);
          if (saisie) saisie.value = valeur;
        }
        preRemplissage = null;
      }
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const donnees = Object.fromEntries(new FormData(form).entries());
        erreur.hidden = true;
        bouton.disabled = true;
        bouton.textContent = "Connexion…";
        try {
          CD.api.fermerSession();
          const jeton = await CD.api.post(etudiant ? "/auth/login-etudiant" : "/auth/login", donnees);
          CD.api.ouvrirSession(jeton);
          onConnecte();
        } catch (err) {
          erreur.textContent = err.message;
          erreur.hidden = false;
          bouton.disabled = false;
          bouton.textContent = "Se connecter";
        }
      });
      return form;
    }

    // Comptes de test (mode démonstration) : un clic remplit le formulaire, « Se connecter » valide.
    function panneauDemo() {
      const comptes = CD.config.comptesDemo || [];
      if (!comptes.length) return null;
      const choisir = (compte) => {
        if (compte.role === "ETUDIANT") {
          onglet = "etudiant";
          preRemplissage = { prenom: compte.prenom, nom: compte.nom, email: compte.email, code_etudiant: compte.code_etudiant };
        } else {
          onglet = "personnel";
          preRemplissage = { email: compte.email, mot_de_passe: compte.mot_de_passe };
        }
        rendre();
      };
      return h("div", { class: "comptes-demo" },
        h("div", { class: "comptes-demo-titre" }, "Comptes de test"),
        h("p", { class: "comptes-demo-aide" }, "Aucune inscription nécessaire : cliquez sur un profil, puis sur « Se connecter »."),
        comptes.map((compte) => {
          const identifiants = compte.role === "ETUDIANT"
            ? `${compte.email} · code ${compte.code_etudiant}`
            : `${compte.email} · ${compte.mot_de_passe}`;
          return h("button", { type: "button", class: "compte-demo", onclick: () => choisir(compte) },
            h("span", { class: "compte-demo-role" }, compte.libelle),
            h("span", { class: "compte-demo-desc" }, compte.description),
            h("span", { class: "compte-demo-id" }, identifiants));
        }));
    }

    function rendre() {
      const onglets = h("div", { class: "onglets", role: "tablist" },
        [["etudiant", "Étudiant"], ["personnel", "Gestionnaire / Admin"]].map(([id, libelle]) =>
          h("button", { type: "button", role: "tab", "aria-selected": String(onglet === id), onclick: () => { onglet = id; rendre(); } }, libelle)));
      CD.ui.remplacer(boite, 
        h("img", { class: "logo-connexion", src: "img/logo.svg", alt: "" }),
        h("h1", null, CD.config.nom),
        h("p", { class: "sous-titre" }, CD.config.sousTitre),
        message ? h("div", { class: "info-connexion" }, message) : null,
        panneauDemo(),
        onglets,
        formulaire()
      );
    }
    rendre();
    return racine;
  }

  CD.auth = { vue };
})();
