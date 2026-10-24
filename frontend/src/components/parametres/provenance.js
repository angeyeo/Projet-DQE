import { etiquetteSourceIA } from '../ui/sourceIA.js';

export const champsProvenance = {
  nombreNiveaux: 'nb_niveaux', typeUsage: 'usage_batiment',
  porteeX: 'portee_x', porteeY: 'portee_y',
  hauteurEtage: 'hauteur_etage', contrainteSol: 'contrainte_sol_kn_m2',
};

export function accepterProposition(formulaire, valeurs, resultat) {
  const acceptationsIA = { ...(formulaire.acceptationsIA || {}) };
  for (const [champ, valeur] of Object.entries(valeurs)) {
    acceptationsIA[champ] = {
      jeton: resultat.preuve_proposition, valeur, source: resultat.source,
    };
  }
  return { ...valeurs, acceptationsIA };
}

export function acceptationsVersApi(formulaire) {
  return Object.fromEntries(Object.entries(formulaire.acceptationsIA || {})
    .filter(([champ]) => champsProvenance[champ])
    .map(([champ, acceptation]) => [champsProvenance[champ], acceptation.jeton]));
}

export function libelleProvenance(formulaire, champ) {
  const attente = formulaire.acceptationsIA?.[champ];
  const origine = formulaire.provenanceParametres?.[champsProvenance[champ]];
  const actuelle = formulaire[champ];
  const reference = attente?.valeur ?? formulaire.valeursSauvegardees?.[champ];
  const identique = String(actuelle ?? '') === String(reference ?? '')
    || (actuelle !== '' && reference !== '' && actuelle != null && reference != null
      && Number.isFinite(Number(actuelle)) && Number(actuelle) === Number(reference));
  if (attente || origine?.valeur_proposee != null) {
    const modifiee = !identique || (!attente && origine?.origine === 'modifiee_apres_ia');
    const source = attente?.source || origine?.source;
    return `${modifiee ? 'Modifiée après proposition' : 'Proposition acceptée'} · ${etiquetteSourceIA(source)} · À vérifier${attente ? ' · À enregistrer' : ''}`;
  }
  return null;
}
