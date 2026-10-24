import { test } from 'node:test';
import assert from 'node:assert/strict';
import { champsNlp } from './champsNlp.js';

test('Lx seule ne remplit jamais Ly', () => {
  assert.deepEqual(champsNlp({ portee_x_m: 4, portee_y_m: null }), { porteeX: '4' });
});
test('les deux axes sont repris indépendamment', () => {
  assert.deepEqual(champsNlp({ portee_x_m: 4, portee_y_m: 6 }), { porteeX: '4', porteeY: '6' });
});
test('aucune affectation depuis une portée sans axe ou une donnée absente', () => {
  assert.deepEqual(champsNlp({ portee_m: 4, portee_y_m: '', nombre_niveaux: null }), {});
  assert.deepEqual(champsNlp(null), {});
});
test('la reprise partielle conserve les autres valeurs du formulaire', () => {
  const avant = { porteeX: '3', porteeY: '7', hauteurEtage: '3' };
  assert.deepEqual({ ...avant, ...champsNlp({ portee_x_m: 4 }) },
    { porteeX: '4', porteeY: '7', hauteurEtage: '3' });
});
