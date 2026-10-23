import React, { useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';
import { dqeService } from '../../api/dqeService';

// Note de calcul du projet (issue #96) : PDF produit par le serveur à partir
// des seules valeurs du moteur et des données du projet.
export default function BoutonNoteCalcul({ projetId, variante = 'btn-secondary' }) {
  const [etat, setEtat] = useState({ enCours: false, erreur: null });
  if (!projetId) return null;

  const telecharger = async () => {
    setEtat({ enCours: true, erreur: null });
    try {
      await dqeService.telechargerNoteCalcul(projetId);
      setEtat({ enCours: false, erreur: null });
    } catch (err) {
      const champs = err.data?.champs_manquants;
      setEtat({ enCours: false, erreur: champs?.length ? `${err.message} Manque : ${champs.join(', ')}.` : err.message });
    }
  };

  return (
    <span className="bouton-note-calcul">
      <button type="button" className={`btn ${variante}`} onClick={telecharger} disabled={etat.enCours}
        title="Justification des sections, de l'acier et des quantités, à remettre à un auditeur">
        {etat.enCours ? <Loader2 size={16} className="spin" /> : <FileText size={16} />} <span>Note de calcul</span>
      </button>
      {etat.erreur && <span className="bouton-note-calcul-erreur" role="alert">{etat.erreur}</span>}
    </span>
  );
}
