import { test } from 'node:test';
import assert from 'node:assert/strict';
import { classeSourceIA, etiquetteSourceIA } from './sourceIA.js';

test('les sources connues gardent une étiquette exacte', () => {
  assert.equal(etiquetteSourceIA('GEMINI'), 'Source : Gemini');
  assert.equal(etiquetteSourceIA('MOCK'), 'Source : MOCK (simulation)');
  assert.equal(etiquetteSourceIA('FALLBACK_LOCAL'), 'Source : Traitement local (sans IA)');
});

test('une source absente ou inconnue ne devient jamais Gemini', () => {
  for (const source of [undefined, null, '', 'AUTRE']) {
    assert.equal(etiquetteSourceIA(source), 'Source inconnue');
    assert.equal(classeSourceIA(source), 'inconnue');
  }
});
