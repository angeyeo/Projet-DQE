import io
import re
from PIL import Image
from .schemas import valider_reponse_ocr

# Expression régulière pour le parsing déterministe des dimensions entre parenthèses.
# Gère les espaces optionnels autour des délimiteurs x, X ou ×.
# Exemple de cible : "S1(170x170x40)" -> "170x170x40", "P2(30x30)" -> "30x30"
REGEX_PARENTHESES = re.compile(r"\(([^)]+)\)")
REGEX_DIMENSIONS = re.compile(r"^\d+(?:\.\d+)?(?:\s*[xX×]\s*\d+(?:\.\d+)?)*$")
REGEX_NOMBRE = re.compile(r"\d+(?:\.\d+)?")

# Ordre obligatoire des préfixes du plus spécifique au plus générique.
MAPPING_PREFIXES = [
    ("SF", "semelle_filante"),
    ("CH", "chainage"),
    ("LG", "longrine"),
    ("P", "poteau"),
    ("R", "poutre"),  # Convention issue du plan de référence à faire confirmer par le technicien
    ("D", "dalle"),
    ("S", "semelle"),
]


def valider_physique_image(image_bytes: bytes, mime_type: str) -> None:
    """
    Effectue une validation physique stricte de l'image binaire avec Pillow.
    Vérifie la non-vacuité, les types MIME acceptés, le format réel et l'absence de corruption.
    Lève ValueError si l'image est invalide ou incohérente.
    """
    if not isinstance(image_bytes, bytes):
        raise ValueError("Les données de l'image doivent être de type bytes.")
    if not image_bytes:
        raise ValueError("L'image ne doit pas être vide.")

    mime_type_clean = str(mime_type).strip().lower()
    if mime_type_clean not in {"image/jpeg", "image/png"}:
        raise ValueError(f"Type MIME '{mime_type_clean}' non supporté. Types autorisés : image/jpeg, image/png")

    try:
        # Première passe : ouverture et vérification de structure
        stream = io.BytesIO(image_bytes)
        img = Image.open(stream)
        real_format = img.format.lower() if img.format else ""
        
        # Comparaison du vrai format détecté avec le MIME déclaré
        if mime_type_clean == "image/jpeg" and real_format not in {"jpeg", "jpg"}:
            raise ValueError(f"Incohérence format : type MIME déclaré 'image/jpeg' mais format réel détecté '{real_format}'.")
        if mime_type_clean == "image/png" and real_format != "png":
            raise ValueError(f"Incohérence format : type MIME déclaré 'image/png' mais format réel détecté '{real_format}'.")

        img.verify()
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"L'image est corrompue ou illisible (verify failed) : {exc}") from exc

    try:
        # Deuxième passe : décodage complet des pixels
        stream_second = io.BytesIO(image_bytes)
        img_second = Image.open(stream_second)
        img_second.load()
    except Exception as exc:
        raise ValueError(f"L'image est tronquée ou corrompue (load failed) : {exc}") from exc


def parser_annotation_structurelle(texte_lu: str) -> dict | None:
    """
    Parse de manière déterministe les dimensions situées exclusivement entre parenthèses.
    Exemple : "S1(170x170x40)" -> {"valeurs": [170.0, 170.0, 40.0], "unite": None}
    L'ordre brut d'apparition est préservé, aucune unité n'est inventée.
    Retourne None si aucune dimension n'est trouvée, ou si la syntaxe est ambiguë/incomplète.
    """
    if not isinstance(texte_lu, str) or not texte_lu.strip():
        return None

    texte_clean = texte_lu.strip()
    match_paren = REGEX_PARENTHESES.search(texte_clean)
    if not match_paren:
        return None

    contenu = match_paren.group(1).strip()
    # Nettoyage des espaces pour valider la structure uniforme du groupe de dimensions (ex: "170 x 170" -> "170x170")
    # Remplacement de × (symbole de multiplication unicode) et X par x pour la regex de structure
    contenu_normalise = contenu.replace(" ", "").replace("X", "x").replace("×", "x")

    if not REGEX_DIMENSIONS.match(contenu_normalise):
        return None  # syntaxe ambiguë ou incomplète

    # Extraction ordonnée de tous les nombres
    nombres_str = REGEX_NOMBRE.findall(contenu)
    valeurs = [float(n) for n in nombres_str]
    
    if not valeurs:
        return None

    return {
        "valeurs": valeurs,
        "unite": None,
    }


def determiner_type_normalise(repere: str) -> str | None:
    """
    Détermine le type normalisé d'un élément structurel à partir de son repère.
    Traite d'abord les préfixes les plus spécifiques pour éviter les collisions (ex: SF avant S).
    """
    if not isinstance(repere, str) or not repere.strip():
        return None

    repere_upper = repere.strip().upper()
    for prefixe, type_nom in MAPPING_PREFIXES:
        # On vérifie si le repère commence par le préfixe suivi optionnellement de chiffres/lettres
        if repere_upper.startswith(prefixe):
            # Cas particulier pour éviter que CH n'intercepte pas des repères bizarres n'ayant pas de chiffres,
            # mais ici on fait un startswith propre et ordonné.
            return type_nom

    return None


def orchestrer_ocr_local(image_bytes: bytes, mime_type: str, ocr_brut: dict) -> dict:
    """
    Orchestrateur local (Partie 1) :
    1. Valide physiquement l'image avec Pillow.
    2. Valide le schéma du JSON OCR brut.
    3. Effectue le mapping local des repères et le parsing local des dimensions.
    4. Retourne le contrat de données final enrichi.
    """
    # 1. Validation de l'image (lève ValueError si invalide)
    valider_physique_image(image_bytes, mime_type)

    # 2. Validation du schéma OCR brut
    validated_ocr = valider_reponse_ocr(ocr_brut)

    # 3. Traitement local et enrichissement des annotations
    annotations_enrichies = []
    for item in validated_ocr["annotations_lues"]:
        texte_lu = item["texte_lu"]
        repere = item["repere"]

        type_normalise = determiner_type_normalise(repere)
        dimensions = parser_annotation_structurelle(texte_lu)

        annotations_enrichies.append({
            "texte_lu": texte_lu,
            "repere": repere,
            "type_normalise": type_normalise,
            "dimensions_parsees": dimensions,
        })

    return {
        "annotations_lues": annotations_enrichies,
        "textes_non_classes": validated_ocr["textes_non_classes"],
        "source": "MOCK",
        "validation_humaine_requise": True,
    }
