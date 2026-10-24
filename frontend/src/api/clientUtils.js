const MESSAGES_STATUT = {
  0: "Serveur injoignable : vérifiez votre connexion ou réessayez dans un instant.",
  400: "Les données envoyées sont invalides.",
  401: "Votre session a expiré : reconnectez-vous.",
  403: "Vous n'avez pas les droits nécessaires pour cette action.",
  404: "Élément introuvable (supprimé, ou appartenant à un autre cabinet).",
  405: "Cette méthode n'est pas autorisée pour cette route.",
  409: "Action impossible dans l'état actuel de l'élément.",
  413: "Fichier trop volumineux.",
  428: "Votre accord est nécessaire pour utiliser l'assistance IA.",
  429: "Trop de requêtes : patientez quelques instants avant de réessayer.",
  500: "Une erreur interne est survenue. Réessayez plus tard.",
  502: "Le service externe est temporairement indisponible.",
  503: "Service momentanément indisponible sur le serveur.",
  504: "Le service demandé met trop de temps à répondre. Réessayez plus tard.",
};

const messageTexte = (value) => {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(messageTexte).filter(Boolean).join(' ');
  return '';
};

const CLES_STRUCTUREES = [
  'champs_manquants', 'problemes', 'lignes', 'elements_en_attente', 'elements', 'issues',
];
const CLES_META = new Set([
  'detail', 'erreur', 'message', 'code', 'error', 'fields', 'details', ...CLES_STRUCTUREES,
]);

export function normaliserBaseApi(configuree) {
  let base = String(configuree || '/api').trim().replace(/\/+$/, '');
  if (!base) base = '/api';
  const suffixeApi = base.match(/(?:\/(?:api|v1))+$/i)?.[0] || '';
  const prefixe = suffixeApi ? base.slice(0, -suffixeApi.length) : base;
  return `${prefixe}/api/v1` || '/api/v1';
}

export function detailsErreur(data) {
  const canonical = data?.error;
  const fields = canonical?.fields && typeof canonical.fields === 'object'
    ? canonical.fields
    : (data && typeof data === 'object'
      ? Object.fromEntries(Object.entries(data).filter(([key]) => !CLES_META.has(key)))
      : {});
  const details = canonical?.details && typeof canonical.details === 'object'
    ? canonical.details
    : (data && typeof data === 'object'
      ? Object.fromEntries(CLES_STRUCTUREES.filter((key) => key in data).map((key) => [key, data[key]]))
      : {});
  return { code: canonical?.code || data?.code || null, fields, details };
}

export function messageErreur(data, status) {
  const canonical = messageTexte(data?.error?.message);
  if (canonical) return canonical;
  if (typeof data === 'string' && !/<[^>]+>/.test(data)) return data;
  if (data && typeof data === 'object') {
    for (const key of ['erreur', 'detail', 'message']) {
      const message = messageTexte(data[key]);
      if (message) return message;
    }
    const parties = Object.entries(detailsErreur(data).fields)
      .map(([champ, value]) => {
        const message = messageTexte(value);
        return message ? `${champ === 'non_field_errors' ? '' : `${champ} : `}${message}` : '';
      })
      .filter(Boolean);
    if (parties.length) return parties.join(' — ');
  }
  return MESSAGES_STATUT[status] || `Erreur inattendue du serveur (code ${status}).`;
}

export function creerErreurHTTP(data, status, messagePersonnalise = null) {
  const error = new Error(messagePersonnalise || messageErreur(data, status));
  const normalisee = detailsErreur(data);
  error.status = status;
  error.data = data;
  error.code = normalisee.code;
  error.fields = normalisee.fields;
  error.details = normalisee.details;
  return error;
}
