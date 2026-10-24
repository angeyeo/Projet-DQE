import { test } from 'node:test';
import assert from 'node:assert/strict';

import { creerErreurHTTP, detailsErreur, messageErreur, normaliserBaseApi } from './clientUtils.js';

const stockage = new Map();
globalThis.localStorage = {
  getItem: (key) => stockage.get(key) ?? null,
  setItem: (key, value) => stockage.set(key, String(value)),
  removeItem: (key) => stockage.delete(key),
};
const evenements = [];
globalThis.CustomEvent = class CustomEvent { constructor(type) { this.type = type; } };
globalThis.window = {
  dispatchEvent: (event) => evenements.push(event.type),
  URL: {
    createObjectURL: () => 'blob:test-download',
    revokeObjectURL: () => {},
  },
};
const telechargement = { clique: 0, ajoute: 0, retire: 0 };
globalThis.document = {
  body: { appendChild: () => { telechargement.ajoute += 1; } },
  createElement: () => ({
    click: () => { telechargement.clique += 1; },
    remove: () => { telechargement.retire += 1; },
  }),
};

const service = await import(`./dqeService.js?test=${Date.now()}`);

function viderSession() {
  stockage.clear();
  evenements.length = 0;
}

function reponse(status, data, headers = {}) {
  return new Response(data === null ? null : JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

test('la base par défaut et les bases personnalisées pointent vers /api/v1/', () => {
  assert.equal(service.API_BASE_URL, '/api/v1');
  assert.equal(normaliserBaseApi('/api'), '/api/v1');
  assert.equal(normaliserBaseApi('/api/v1/'), '/api/v1');
  assert.equal(normaliserBaseApi('https://dqe.example/api/'), 'https://dqe.example/api/v1');
  assert.equal(normaliserBaseApi('https://dqe.example/api/api/v1/'), 'https://dqe.example/api/v1');
  assert.equal(normaliserBaseApi('https://dqe.example'), 'https://dqe.example/api/v1');
});

test('lit les enveloppes futures et les structures legacy sans perdre les détails métier', () => {
  const canonical = {
    error: { code: 'VALIDATION_ERROR', message: 'Corrigez le projet.', fields: { nb_niveaux: ['Maximum 20.'] }, details: {} },
    nb_niveaux: ['Maximum 20.'],
  };
  assert.equal(messageErreur(canonical, 400), 'Corrigez le projet.');
  assert.deepEqual(detailsErreur(canonical).fields, { nb_niveaux: ['Maximum 20.'] });
  assert.equal(messageErreur({ erreur: 'Données manquantes.', champs_manquants: [{ champ: 'portee_y' }] }, 400), 'Données manquantes.');
  assert.equal(messageErreur({ detail: 'Consentement requis.', code: 'AI_CONSENT_REQUIRED' }, 428), 'Consentement requis.');
  assert.deepEqual(detailsErreur({ lignes: { 2: 'Prix manquant.' } }).details.lignes,
    { 2: 'Prix manquant.' });
  assert.equal(messageErreur('<html>traceback</html>', 503), 'Service momentanément indisponible sur le serveur.');
});

test('401 renouvelle le JWT puis rejoue une seule fois la requête v1', async () => {
  viderSession();
  stockage.set('dqe_access_token', 'ancien');
  stockage.set('dqe_refresh_token', 'refresh-ancien');
  const appels = [];
  globalThis.fetch = async (url, options = {}) => {
    appels.push({ url: String(url), options });
    if (appels.length === 1) return reponse(401, { detail: 'Token expiré.' });
    if (String(url).endsWith('/auth/token/refresh/')) {
      assert.deepEqual(JSON.parse(options.body), { refresh: 'refresh-ancien' });
      return reponse(200, { access: 'nouveau', refresh: 'refresh-tourne' });
    }
    return reponse(200, { usages: [] });
  };

  assert.deepEqual(await service.dqeService.getReferentiel(), { usages: [] });
  assert.equal(appels[0].url, '/api/v1/referentiel/');
  assert.equal(appels[1].url, '/api/v1/auth/token/refresh/');
  assert.equal(appels[2].url, '/api/v1/referentiel/');
  assert.equal(appels[2].options.headers.Authorization, 'Bearer nouveau');
  assert.equal(stockage.get('dqe_access_token'), 'nouveau');
  assert.equal(stockage.get('dqe_refresh_token'), 'refresh-tourne');
});

test('un 401 sans renouvellement vide la session et déclenche l’événement d’expiration', async () => {
  viderSession();
  stockage.set('dqe_access_token', 'ancien');
  globalThis.fetch = async () => reponse(401, { detail: 'Session expirée.' });
  await assert.rejects(service.dqeService.getReferentiel(), (error) => {
    assert.equal(error.status, 401);
    assert.equal(error.message, 'Session expirée.');
    return true;
  });
  assert.equal(stockage.has('dqe_access_token'), false);
  assert.deepEqual(evenements, ['dqe:auth-expired']);
});

test('une panne réseau renvoie un message lisible sans détail technique', async () => {
  viderSession();
  globalThis.fetch = async () => { throw new Error('socket ECONNREFUSED 127.0.0.1'); };
  await assert.rejects(service.dqeService.getReferentiel(), (error) => {
    assert.equal(error.status, 0);
    assert.equal(error.code, 'NETWORK_ERROR');
    assert.match(error.message, /Serveur injoignable/);
    assert.doesNotMatch(error.message, /ECONNREFUSED|127\.0\.0\.1/);
    return true;
  });
});

test('multipart v1 garde le FormData et les noms de champs actuels', async () => {
  viderSession();
  let appel;
  class XMLHttpRequestFixture {
    constructor() { this.upload = {}; this.headers = {}; this.status = 0; this.responseText = ''; appel = this; }
    open(method, url) { this.method = method; this.url = url; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    send(body) {
      this.body = body;
      this.status = 200;
      this.responseText = JSON.stringify({ ok: true });
      this.onload();
    }
  }
  globalThis.XMLHttpRequest = XMLHttpRequestFixture;
  const plan = new Blob(['fixture IFC'], { type: 'application/octet-stream' });
  await service.dqeService.importerPlanIFC(41, plan);
  assert.equal(appel.url, '/api/v1/projets/41/importer_plan/');
  assert.equal(appel.method, 'POST');
  assert.ok(appel.body instanceof FormData);
  assert.equal(appel.body.get('fichier').size, plan.size);
  assert.equal(appel.headers['Content-Type'], undefined);
});

test('les téléchargements binaires v1 gardent le query param et le nom de fichier', async () => {
  viderSession();
  let url;
  globalThis.fetch = async (value) => {
    url = String(value);
    return new Response(new Blob(['%PDF test']), {
      status: 200,
      headers: { 'Content-Disposition': 'attachment; filename="DQE_41.pdf"' },
    });
  };
  telechargement.clique = telechargement.ajoute = telechargement.retire = 0;
  await service.dqeService.telechargerDQEFichier(41, 'pdf');
  assert.equal(url, '/api/v1/projets/41/generer-dqe/?export=pdf');
  assert.deepEqual(telechargement, { clique: 1, ajoute: 1, retire: 1 });
});

test('PDF, Excel, DXF et approvisionnement sont téléchargés via leurs routes v1', async () => {
  viderSession();
  const urls = [];
  globalThis.fetch = async (value) => {
    urls.push(String(value));
    return new Response(new Blob(['binary fixture']), {
      status: 200,
      headers: { 'Content-Disposition': 'attachment; filename="export-test.bin"' },
    });
  };
  telechargement.clique = telechargement.ajoute = telechargement.retire = 0;

  await service.dqeService.telechargerDQEFichier(41, 'pdf');
  await service.dqeService.telechargerDQEFichier(41, 'excel');
  await service.dqeService.telechargerPlanFondationDXF(41);
  await service.dqeService.telechargerApprovisionnementExcel(41);

  assert.deepEqual(urls, [
    '/api/v1/projets/41/generer-dqe/?export=pdf',
    '/api/v1/projets/41/generer-dqe/?export=excel',
    '/api/v1/projets/41/plan_fondation/?export=dxf',
    '/api/v1/projets/41/approvisionnement/?export=excel',
  ]);
  assert.deepEqual(telechargement, { clique: 4, ajoute: 4, retire: 4 });
});

test('les erreurs HTTP exposent code, fields et details tout en gardant err.data legacy', () => {
  const data = {
    erreur: 'Paramètres manquants.',
    champs_manquants: [{ champ: 'portee_y' }],
    error: { code: 'VALIDATION_ERROR', message: 'Paramètres manquants.', fields: {}, details: { champs_manquants: [{ champ: 'portee_y' }] } },
  };
  const error = creerErreurHTTP(data, 400);
  assert.equal(error.code, 'VALIDATION_ERROR');
  assert.deepEqual(error.data.champs_manquants, [{ champ: 'portee_y' }]);
  assert.deepEqual(error.details.champs_manquants, [{ champ: 'portee_y' }]);
});
