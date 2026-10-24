import { test } from 'node:test';
import assert from 'node:assert/strict';
import { accepterProposition, acceptationsVersApi, libelleProvenance } from './provenance.js';

test('acceptation et modification avant sauvegarde gardent la preuve initiale', () => {
  const f = { porteeY: '7', ...accepterProposition({}, { porteeX: '4' }, { preuve_proposition: 'signature', source: 'GEMINI' }) };
  assert.equal(f.porteeY, '7');
  assert.match(libelleProvenance(f, 'porteeX'), /Proposition acceptée.*Source : Gemini.*À vérifier/);
  f.porteeX = '5';
  assert.match(libelleProvenance(f, 'porteeX'), /Modifiée après proposition/);
  assert.deepEqual(acceptationsVersApi(f), { portee_x: 'signature' });
});
test('rechargement, modification et historique inconnu', () => {
  const f = { porteeX: '4', valeursSauvegardees: { porteeX: '4' }, provenanceParametres: {
    portee_x: { origine: 'ia_acceptee', source: 'MOCK', valeur_proposee: 4 },
  } };
  assert.match(libelleProvenance(f, 'porteeX'), /MOCK \(simulation\).*À vérifier/);
  assert.equal(libelleProvenance(f, 'porteeY'), null);
  assert.match(libelleProvenance({ ...f, porteeX: '5' }, 'porteeX'), /Modifiée après proposition/);
  assert.match(libelleProvenance({ ...f, porteeX: '4.0' }, 'porteeX'), /Proposition acceptée/);
  assert.deepEqual(acceptationsVersApi(f), {});
});

test('une provenance sans source fiable reste inconnue', () => {
  const f = { porteeX: '4', valeursSauvegardees: { porteeX: '4' }, provenanceParametres: {
    portee_x: { origine: 'ia_acceptee', valeur_proposee: 4 },
  } };
  assert.match(libelleProvenance(f, 'porteeX'), /Source inconnue/);
  assert.doesNotMatch(libelleProvenance(f, 'porteeX'), /Gemini/);
});
