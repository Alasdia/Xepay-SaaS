#!/usr/bin/env python3
"""Génère, pour chaque route marketing listée dans ROUTES, une copie statique
de marketing.html avec sa propre balise <title>, <meta name="description">
et <link rel="canonical"> dans le <head>.

Ne touche ni à marketing.html, ni à router.js, ni au rendu client dans
#marketing-view : les fichiers générés chargent le même router.js et gardent
<main id="marketing-view"></main> vide, à l'identique. Seules les trois
balises de <head> ci-dessus varient d'un fichier à l'autre.

Usage : python3 frontend/scripts/generate-seo-pages.py
Écrit les fichiers dans frontend/pages/seo/<route>.html.
Script à relancer à la main si marketing.html ou les métadonnées d'une route
changent - il n'est pas exécuté par Vercel au déploiement (pas de build step
dans ce projet), seulement en local avant de committer les fichiers générés.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent  # frontend/
TEMPLATE_PATH = ROOT / "pages" / "marketing.html"
OUT_DIR = ROOT / "pages" / "seo"

BASE_URL = "https://www.xepay.finance"

# Mêmes titres/descriptions que l'objet SEO côté client dans
# marketing/router.js (updateSeo) - gardés identiques pour que le <head>
# statique et ce que le JS écrit ensuite ne divergent jamais.
ROUTES = {
    "fonctionnalite": {
        "title": "Fonctionnalités — Paiement en ligne, liens et factures | Xepay",
        "description": "Découvrez les fonctionnalités Xepay : paiements en ligne, liens de paiement, multi-devises XOF/EUR/USD, factures, rapports et gestion des équipes.",
    },
    "tarif": {
        "title": "Tarifs et offres | Xepay",
        "description": "Consultez les offres Xepay et choisissez les outils de paiement et de gestion adaptés à votre activité.",
    },
    "api": {
        "title": "API de paiement et webhooks | Xepay",
        "description": "Connectez Xepay à votre site ou application avec des clés API et des webhooks pour intégrer vos flux de paiement.",
    },
    "a-propos": {
        "title": "À propos de Xepay | Paiements fintech en Afrique de l'Ouest",
        "description": "Découvrez Xepay et sa mission : simplifier l'encaissement des paiements internationaux pour les entrepreneurs et entreprises de la zone UEMOA.",
    },
    "documentation": {
        "title": "Documentation et guides | Xepay",
        "description": "Consultez les guides Xepay pour créer des liens de paiement, encaisser vos clients et gérer vos opérations.",
    },
    "centre-aide": {
        "title": "Centre d'aide Xepay | Questions fréquentes",
        "description": "Trouvez des réponses sur votre compte Xepay, les paiements, les liens de paiement et l'utilisation de la plateforme.",
    },
    "securite": {
        "title": "Sécurité des paiements et des données | Xepay",
        "description": "En savoir plus sur les principes de sécurité de Xepay et la protection des paiements et des données.",
    },
    "mentions-legales": {
        "title": "Mentions légales | Xepay",
        "description": "Informations légales relatives au site Xepay et à son éditeur, Alasdia Technologies LLC.",
    },
    "cookies": {
        "title": "Politique de cookies | Xepay",
        "description": "Consultez les informations de Xepay sur l'utilisation des cookies.",
    },
    # Absent de l'objet SEO côté client (marketing/router.js) - pas dans le
    # scope de cette correction, uniquement le <head> statique ici.
    "presse": {
        "title": "Presse et kit média | Xepay",
        "description": "Ressources presse Xepay : présentation de la plateforme, contact presse et kit média pour les journalistes et créateurs de contenu.",
    },
}

OLD_TITLE = "<title>Xepay — Paiements fintech, de l'Afrique de l'Ouest au monde</title>"
OLD_DESC = '<meta name="description" content="Xepay aide les entreprises et marchands d\'Afrique de l\'Ouest à encaisser des paiements en ligne, créer des liens de paiement et suivre leurs flux en XOF, EUR et USD.">'
OLD_CANONICAL = '<link rel="canonical" href="https://www.xepay.finance/accueil">'


def main():
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert template.count(OLD_TITLE) == 1, "title /accueil introuvable ou dupliqué dans marketing.html"
    assert template.count(OLD_DESC) == 1, "meta description /accueil introuvable ou dupliquée dans marketing.html"
    assert template.count(OLD_CANONICAL) == 1, "canonical /accueil introuvable ou dupliqué dans marketing.html"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for route, meta in ROUTES.items():
        html = template
        html = html.replace(OLD_TITLE, f"<title>{meta['title']}</title>")
        html = html.replace(
            OLD_DESC,
            f'<meta name="description" content="{meta["description"]}">',
        )
        html = html.replace(
            OLD_CANONICAL,
            f'<link rel="canonical" href="{BASE_URL}/{route}">',
        )
        out_path = OUT_DIR / f"{route}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"wrote {out_path.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
