import React from 'react';
import { HelpCircle } from 'lucide-react';

// Aide « comment exporter mon plan » (issue #95). Le .pln d'ArchiCAD est un
// format fermé : il ne peut pas être lu, il faut l'exporter en IFC ou DXF.
export default function AideExport() {
  return (
    <details className="aide-export">
      <summary>
        <HelpCircle size={16} aria-hidden="true" />
        <span>Comment exporter mon plan depuis AutoCAD ou ArchiCAD ?</span>
      </summary>
      <div className="aide-export-colonnes">
        <section aria-labelledby="aide-autocad">
          <h4 id="aide-autocad">AutoCAD (.dwg)</h4>
          <ol>
            <li>Vérifiez les unités : commande <kbd>UNITES</kbd>, « Unités d&apos;insertion » en mètres, centimètres ou millimètres.</li>
            <li><strong>Fichier &gt; Enregistrer sous</strong>, type <strong>« AutoCAD 2018 DXF (*.dxf) »</strong>, puis déposez le DXF.</li>
            <li>Pour que les poteaux soient lus, dessinez-les en <strong>blocs</strong> sur un calque dont le nom contient
              « POTEAU » (ex. POTEAUX) ou « COLUMN ». Sinon, utilisez l&apos;onglet « Plan d&apos;architecte » et placez-les à la main.</li>
          </ol>
          <p className="texte-discret">
            Un .dwg peut aussi être déposé tel quel : il est converti en DXF sur le serveur quand le convertisseur y est
            installé, sinon un message vous demande le DXF.
          </p>
        </section>
        <section aria-labelledby="aide-archicad">
          <h4 id="aide-archicad">ArchiCAD (.pln)</h4>
          <ol>
            <li><strong>Fichier &gt; Enregistrer sous</strong>, type <strong>« IFC »</strong> (recommandé) : poteaux, poutres
              et niveaux sont conservés.</li>
            <li>Ou, depuis la vue en plan du rez-de-chaussée, <strong>Enregistrer sous</strong> au format <strong>« DXF »</strong>.</li>
          </ol>
          <p className="texte-discret">
            Le fichier .pln lui-même ne peut pas être lu : c&apos;est un format fermé de Graphisoft, sans lecteur public.
          </p>
        </section>
      </div>
    </details>
  );
}
