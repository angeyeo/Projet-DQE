"""Preuve signée des valeurs structurées, sans description ni image."""
from django.core import signing
from uuid import uuid4
from django.utils import timezone
from rest_framework.exceptions import ValidationError

CHAMPS = {
    'nombre_niveaux': 'nb_niveaux', 'usage_batiment': 'usage_batiment',
    'portee_x_m': 'portee_x', 'portee_y_m': 'portee_y',
    'hauteur_niveau_m': 'hauteur_etage', 'contrainte_sol_kn_m2': 'contrainte_sol_kn_m2',
}
SALT = 'dqe.proposition-parametres.v1'


def signer_proposition(resultat, utilisateur):
    if resultat.get('source') not in {'GEMINI', 'MOCK'}:
        return None
    valeurs = {champ: resultat['donnees'][cle] for cle, champ in CHAMPS.items()
               if resultat.get('donnees', {}).get(cle) not in (None, '')}
    return signing.dumps({'id': str(uuid4()), 'utilisateur': utilisateur.pk, 'source': resultat['source'],
                          'valeurs': valeurs}, salt=SALT)


def verifier_acceptations(acceptations, attrs, utilisateur):
    preuves = {}
    for champ, jeton in acceptations.items():
        if champ not in CHAMPS.values() or champ not in attrs:
            raise ValidationError({'acceptations_ia': 'Paramètre absent ou non autorisé.'})
        try:
            preuve = signing.loads(jeton, salt=SALT, max_age=86400)
        except (signing.BadSignature, TypeError, ValueError):
            raise ValidationError({'acceptations_ia': 'Proposition invalide ou expirée.'})
        if (preuve.get('utilisateur') != utilisateur.pk
                or preuve.get('source') not in {'GEMINI', 'MOCK'}
                or champ not in preuve.get('valeurs', {})):
            raise ValidationError({'acceptations_ia': 'Proposition non autorisée.'})
        preuves[champ] = preuve
    return preuves


def construire_provenance(instance, attrs, preuves, utilisateur):
    provenance = dict(instance.provenance_parametres or {}) if instance else {}
    maintenant = timezone.now().isoformat()
    for champ in CHAMPS.values():
        if champ not in attrs:
            continue
        ancien = provenance.get(champ, {})
        preuve = preuves.get(champ)
        change = instance is None or getattr(instance, champ) != attrs[champ]
        if preuve:
            proposee = preuve['valeurs'][champ]
            # Une sauvegarde répétée avec le même jeton ne redéfinit pas l'acceptation.
            identite = preuve['id']
            if ancien.get('proposition_id') != identite:
                ancien = {'origine': 'ia_acceptee', 'valeur_proposee': proposee,
                          'source': preuve['source'], 'accepte_par': utilisateur.pk,
                          'accepte_le': maintenant, 'proposition_id': identite}
            if attrs[champ] != proposee:
                if change or ancien.get('origine') != 'modifiee_apres_ia':
                    ancien = {**ancien, 'origine': 'modifiee_apres_ia',
                              'modifie_par': utilisateur.pk, 'modifie_le': maintenant}
            provenance[champ] = ancien
        elif change:
            if 'valeur_proposee' in ancien:
                provenance[champ] = {**ancien, 'origine': 'modifiee_apres_ia',
                                     'modifie_par': utilisateur.pk, 'modifie_le': maintenant}
            elif attrs[champ] not in (None, '') or instance is not None:
                provenance[champ] = {'origine': 'manuelle', 'modifie_par': utilisateur.pk,
                                     'modifie_le': maintenant}
    return provenance
