/* Dialogue avec l'API + session (jeton conservé le temps de l'onglet : sessionStorage). */
(function () {
  const CD = (window.CD = window.CD || {});
  const CLE = "memoria_session";

  let session = null;
  try { session = JSON.parse(sessionStorage.getItem(CLE)); } catch (e) { session = null; }

  function sauver(s) {
    session = s;
    if (s) sessionStorage.setItem(CLE, JSON.stringify(s));
    else sessionStorage.removeItem(CLE);
  }

  class ErreurApi extends Error {
    constructor(message, statut, type) {
      super(message);
      this.statut = statut;
      this.type = type;
    }
  }

  function messageDepuis(corps, statut) {
    if (corps && corps.message) return corps.message;              // erreurs métier de l'application
    if (corps && Array.isArray(corps.detail) && corps.detail.length) {   // erreurs de format (FastAPI)
      return "Données invalides : " + corps.detail.map((d) => (d.loc ? d.loc.slice(1).join(".") + " - " : "") + d.msg).join(" ; ");
    }
    return "Erreur inattendue (code " + statut + ").";
  }

  async function requete(methode, chemin, options) {
    const { params, json, form, brut } = options || {};
    const qs = new URLSearchParams();
    for (const [cle, valeur] of Object.entries(params || {})) {
      if (valeur !== undefined && valeur !== null && valeur !== "") qs.append(cle, valeur);
    }
    const url = chemin + (qs.toString() ? "?" + qs.toString() : "");
    const entetes = {};
    if (session) entetes.Authorization = "Bearer " + session.access_token;
    let corps;
    if (json !== undefined) { entetes["Content-Type"] = "application/json"; corps = JSON.stringify(json); }
    else if (form) corps = form;

    let reponse;
    try {
      reponse = await fetch(url, { method: methode, headers: entetes, body: corps });
    } catch (e) {
      throw new ErreurApi("Impossible de joindre le serveur. Vérifie que l'application est bien lancée.", 0, "Reseau");
    }
    if (!reponse.ok) {
      let contenu = null;
      try { contenu = await reponse.json(); } catch (e) { /* pas de JSON */ }
      if (reponse.status === 401 && session) {
        sauver(null);
        if (CD.surDeconnexion) CD.surDeconnexion("Ta session a expiré. Reconnecte-toi.");
      }
      throw new ErreurApi(messageDepuis(contenu, reponse.status), reponse.status, contenu && contenu.erreur);
    }
    if (brut) return reponse;
    if (reponse.status === 204) return null;
    return reponse.json();
  }

  /* Télécharge un fichier protégé (le jeton doit être envoyé : un simple lien ne suffit pas). */
  async function telecharger(chemin, params, nomParDefaut) {
    const reponse = await requete("GET", chemin, { params, brut: true });
    const blob = await reponse.blob();
    const dispo = reponse.headers.get("Content-Disposition") || "";
    const trouve = /filename="?([^";]+)"?/i.exec(dispo);
    const nom = trouve ? trouve[1] : nomParDefaut || "fichier";
    const lien = document.createElement("a");
    lien.href = URL.createObjectURL(blob);
    lien.download = nom;
    document.body.append(lien);
    lien.click();
    lien.remove();
    setTimeout(() => URL.revokeObjectURL(lien.href), 10000);
    return nom;
  }

  let ufrEnCache = null;
  const listeUfr = (forcer) => {
    if (!ufrEnCache || forcer) ufrEnCache = requete("GET", "/ufr").catch((e) => { ufrEnCache = null; throw e; });
    return ufrEnCache;
  };

  CD.api = {
    ErreurApi,
    get: (chemin, params) => requete("GET", chemin, { params }),
    post: (chemin, json) => requete("POST", chemin, { json }),
    put: (chemin, json) => requete("PUT", chemin, { json }),
    supprimer: (chemin) => requete("DELETE", chemin),
    postFormulaire: (chemin, form) => requete("POST", chemin, { form }),
    putFormulaire: (chemin, form) => requete("PUT", chemin, { form }),
    telecharger,
    listeUfr,
    session: () => session,
    ouvrirSession: (jeton) => sauver(jeton),
    fermerSession: () => sauver(null),
  };
})();
