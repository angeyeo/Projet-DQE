import React, { useEffect, useState } from 'react';
import { Loader2, UploadCloud } from 'lucide-react';
import { dqeService } from '../../api/dqeService';
import Alerte from '../ui/Alerte';
import EditeurPoteaux from './EditeurPoteaux';
import { MESSAGE_STRUCTURE_SAISIE } from './messages';


// Mode « Plan d'architecte » (issue #93) : le DXF d'architecte (murs,
// mobilier, pièces) sert de FOND ; l'utilisateur place lui-même les poteaux.
// Le logiciel n'en déduit aucun à partir des murs ou des pièces. Les poteaux
// sont envoyés au serveur au moment du calcul (« Enregistrer et calculer »).
export default function PlanArchitecte({ projectData, updateProjectData, assurerProjet }) {
  const [fond, setFond] = useState(null);
  const [etat, setEtat] = useState({ chargement: false, erreur: null });
  const projetId = projectData.id;

  // Réouverture d'un projet : relit le fond déjà déposé.
  useEffect(() => {
    if (!projetId || fond) return;
    let actif = true;
    dqeService.getFondPlan(projetId)
      .then((f) => { if (actif) setFond(f); })
      .catch((err) => {
        // 404 : aucun plan d'architecte déposé pour ce projet (état normal).
        if (actif && err.status !== 404) setEtat({ chargement: false, erreur: err.message });
      });
    return () => { actif = false; };
  }, [projetId, fond]);

  const deposer = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // permet de redéposer le même fichier (issue #88)
    if (!file) return;
    if (!/\.(dxf|dwg)$/i.test(file.name)) {
      setEtat({ chargement: false, erreur: 'Le mode « Plan d’architecte » accepte les fichiers DXF ou DWG : exportez le plan en DXF depuis votre logiciel (voir l’aide ci-dessous).' });
      return;
    }
    setEtat({ chargement: true, erreur: null });
    try {
      const id = await assurerProjet();
      const f = await dqeService.importerPlanArchitecte(id, file);
      setFond(f);
      updateProjectData({
        planArchitecte: true,
        ifcImporte: false,
        planFileName: file.name,
        planFileSize: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
      });
      setEtat({ chargement: false, erreur: null });
    } catch (err) {
      setEtat({ chargement: false, erreur: `Fond de plan non chargé : ${err.message}` });
    }
  };

  const poteaux = projectData.poteauxSaisis || [];

  return (
    <section className="plan-architecte" aria-labelledby="titre-plan-architecte">
      <h3 id="titre-plan-architecte" className="sr-only">Plan d&apos;architecte</h3>
      <Alerte type="attention" titre={MESSAGE_STRUCTURE_SAISIE}>
        Le plan d&apos;architecte sert uniquement de fond : placez vous-même chaque poteau. Le logiciel n&apos;en déduit
        aucun à partir des murs ou des pièces. Les éléments créés porteront l&apos;origine « saisi ».
      </Alerte>

      <div className="plan-architecte-depot">
        <label className="btn btn-secondary">
          {etat.chargement ? <Loader2 size={16} className="spin" /> : <UploadCloud size={16} />}
          <span>{fond ? 'Remplacer le plan d’architecte (DXF ou DWG)' : 'Déposer le plan d’architecte (DXF ou DWG)'}</span>
          <input type="file" accept=".dxf,.dwg" className="sr-only" onChange={deposer} disabled={etat.chargement} />
        </label>
        {fond && (
          <span className="texte-discret">
            {projectData.planFileName ? `${projectData.planFileName} · ` : ''}
            {fond.largeur_m.toLocaleString('fr-FR')} × {fond.profondeur_m.toLocaleString('fr-FR')} m · unités du fichier : {fond.unite}
          </span>
        )}
      </div>

      {etat.erreur && <Alerte type="erreur">{etat.erreur}</Alerte>}
      {fond?.avertissements?.length > 0 && <Alerte type="attention" liste={fond.avertissements} />}

      {fond ? (
        <>
          <EditeurPoteaux fond={fond} poteaux={poteaux}
            onChange={(liste) => updateProjectData({ poteauxSaisis: liste })} />
          <p className="texte-discret">
            Chaque poteau doit avoir au moins un voisin aligné en X et un en Y : un poteau isolé n&apos;est pas calculé
            (il est signalé). Poutres et semelles sont créées par le moteur entre les poteaux placés, au calcul.
          </p>
        </>
      ) : (
        !etat.chargement && (
          <p className="texte-discret etat-vide-compact">
            Déposez le DXF (ou DWG) de l&apos;architecte (en mètres, centimètres ou millimètres) pour l&apos;afficher en fond et y placer les poteaux.
          </p>
        )
      )}
    </section>
  );
}
