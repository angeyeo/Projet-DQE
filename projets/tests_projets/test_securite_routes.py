"""Garde-fou : AUCUNE route /api/ n'est accessible anonymement, sauf la
liste blanche explicite des routes d'authentification publiques."""

import re

from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APITestCase

PUBLIQUES = {
    # Documentation sans données client, montée uniquement lorsque DEBUG=True.
    "/api/schema/", "/api/docs/", "/api/v1/schema/", "/api/v1/docs/",
    "/api/token/", "/api/token/refresh/", "/api/token/verify/",
    "/api/v1/token/", "/api/v1/token/refresh/", "/api/v1/token/verify/",
    "/api/auth/token/", "/api/auth/token/refresh/",
    "/api/auth/inscription/", "/api/auth/activer/",
    "/api/auth/mot-de-passe-oublie/", "/api/auth/reinitialiser-mot-de-passe/",
    "/api/v1/auth/token/", "/api/v1/auth/token/refresh/",
    "/api/v1/auth/inscription/", "/api/v1/auth/activer/",
    "/api/v1/auth/mot-de-passe-oublie/", "/api/v1/auth/reinitialiser-mot-de-passe/",
}


def _routes(patterns, prefixe=""):
    for p in patterns:
        motif = prefixe + str(p.pattern)
        if isinstance(p, URLResolver):
            yield from _routes(p.url_patterns, motif)
        elif isinstance(p, URLPattern):
            yield motif


def _concretiser(motif):
    url = motif.lstrip("^").rstrip("$").replace("\\Z", "").replace("\\.", ".")
    url = re.sub(r"<[^>]+>", "1", url)
    url = re.sub(r"\(\?P<[^>]+>[^)]+\)", "1", url)
    url = re.sub(r"\.\(\?P<format>[^)]*\)/?", "", url)
    return "/" + url.lstrip("/")


class AucuneRouteAnonymeTestCase(APITestCase):
    def test_toutes_les_routes_api_exigent_une_authentification(self):
        urls = sorted({_concretiser(m) for m in _routes(get_resolver().url_patterns)})
        urls = [u for u in urls if u.startswith("/api/") and "format" not in u and "(" not in u]
        self.assertGreater(len(urls), 30)
        ouvertes = []
        for url in urls:
            if url in PUBLIQUES:
                continue
            for methode in ("get", "post"):
                r = getattr(self.client, methode)(url, {}, format="json")
                if r.status_code not in (401, 403, 404, 405):
                    ouvertes.append(f"{methode.upper()} {url} -> {r.status_code}")
        self.assertEqual(ouvertes, [], "Routes accessibles sans authentification")
