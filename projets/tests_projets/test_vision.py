import io
from django.test import SimpleTestCase
from PIL import Image
from projets.services.assistant_ia.vision import (
    valider_physique_image,
    parser_annotation_structurelle,
    determiner_type_normalise,
    orchestrer_ocr_local,
)


def generer_image_jpeg_valide() -> bytes:
    """Génère en mémoire une vraie petite image JPEG."""
    img = Image.new("RGB", (10, 10), color="red")
    stream = io.BytesIO()
    img.save(stream, format="JPEG")
    return stream.getvalue()


def generer_image_png_valide() -> bytes:
    """Génère en mémoire une vraie petite image PNG."""
    img = Image.new("RGBA", (10, 10), color="blue")
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    return stream.getvalue()


class TestValidationPhysiqueImage(SimpleTestCase):
    def test_image_jpeg_valide_acceptee(self):
        img_bytes = generer_image_jpeg_valide()
        # Ne doit pas lever d'erreur
        valider_physique_image(img_bytes, "image/jpeg")

    def test_image_png_valide_acceptee(self):
        img_bytes = generer_image_png_valide()
        # Ne doit pas lever d'erreur
        valider_physique_image(img_bytes, "image/png")

    def test_rejet_bytes_vides(self):
        with self.assertRaises(ValueError) as ctx:
            valider_physique_image(b"", "image/jpeg")
        self.assertIn("ne doit pas être vide", str(ctx.exception))

    def test_rejet_non_bytes(self):
        with self.assertRaises(ValueError) as ctx:
            valider_physique_image("chaine_de_caracteres", "image/jpeg")
        self.assertIn("doivent être de type bytes", str(ctx.exception).lower())

    def test_rejet_mime_type_inconnu(self):
        img_bytes = generer_image_jpeg_valide()
        with self.assertRaises(ValueError) as ctx:
            valider_physique_image(img_bytes, "application/pdf")
        self.assertIn("non supporté", str(ctx.exception))

    def test_rejet_bytes_invalides_jpeg(self):
        with self.assertRaises(ValueError) as ctx:
            valider_physique_image(b"donnees_aleatoires_non_jpeg", "image/jpeg")
        self.assertIn("corrompue ou illisible", str(ctx.exception))

    def test_rejet_image_corrompue_verify(self):
        # On altère une vraie image pour corrompre sa structure
        img_bytes = generer_image_jpeg_valide()
        corrupted_bytes = img_bytes[:-10] + b"\x00" * 10
        with self.assertRaises(ValueError) as ctx:
            valider_physique_image(corrupted_bytes, "image/jpeg")
        self.assertIn("corrompue", str(ctx.exception))

    def test_rejet_mime_jpeg_vrai_png(self):
        png_bytes = generer_image_png_valide()
        with self.assertRaises(ValueError) as ctx:
            valider_physique_image(png_bytes, "image/jpeg")
        self.assertIn("Incohérence format", str(ctx.exception))

    def test_rejet_mime_png_vrai_jpeg(self):
        jpeg_bytes = generer_image_jpeg_valide()
        with self.assertRaises(ValueError) as ctx:
            valider_physique_image(jpeg_bytes, "image/png")
        self.assertIn("Incohérence format", str(ctx.exception))


class TestParserAnnotationStructurelle(SimpleTestCase):
    def test_repere_sans_dimensions(self):
        self.assertIsNone(parser_annotation_structurelle("P2"))
        self.assertIsNone(parser_annotation_structurelle("S1"))
        self.assertIsNone(parser_annotation_structurelle("SF10"))

    def test_annotation_S1_nominal(self):
        res = parser_annotation_structurelle("S1(170x170x40)")
        self.assertIsNotNone(res)
        self.assertEqual(res["valeurs"], [170.0, 170.0, 40.0])
        self.assertIsNone(res["unite"])

    def test_annotation_P2_nominal(self):
        res = parser_annotation_structurelle("P2(30x30)")
        self.assertIsNotNone(res)
        self.assertEqual(res["valeurs"], [30.0, 30.0])
        self.assertIsNone(res["unite"])

    def test_annotation_multiplication_unicode(self):
        res = parser_annotation_structurelle("S1(170 × 170 × 40)")
        self.assertIsNotNone(res)
        self.assertEqual(res["valeurs"], [170.0, 170.0, 40.0])

    def test_annotation_x_majuscule_et_espaces(self):
        res = parser_annotation_structurelle("S1( 170 X 170 X 40 )")
        self.assertIsNotNone(res)
        self.assertEqual(res["valeurs"], [170.0, 170.0, 40.0])

    def test_syntaxe_incomplete_ou_ambigue(self):
        # Parenthèse non fermée
        self.assertIsNone(parser_annotation_structurelle("S1(170x170"))
        # Dimensions vides dans parenthèses
        self.assertIsNone(parser_annotation_structurelle("S1()"))
        # Lettres au milieu des dimensions
        self.assertIsNone(parser_annotation_structurelle("S1(170xabcx40)"))
        # Nombre de dimensions farfelues mais syntaxe OK
        res = parser_annotation_structurelle("SF1(50x30x40x20)")
        self.assertEqual(res["valeurs"], [50.0, 30.0, 40.0, 20.0])


class TestDeterminerTypeNormalise(SimpleTestCase):
    def test_mapping_prioritaire_SF_avant_S(self):
        self.assertEqual(determiner_type_normalise("SF1"), "semelle_filante")
        self.assertEqual(determiner_type_normalise("SF_10"), "semelle_filante")
        # Semelle simple
        self.assertEqual(determiner_type_normalise("S1"), "semelle")
        self.assertEqual(determiner_type_normalise("S_2"), "semelle")

    def test_autres_mappings_nominaux(self):
        self.assertEqual(determiner_type_normalise("CH1"), "chainage")
        self.assertEqual(determiner_type_normalise("LG2"), "longrine")
        self.assertEqual(determiner_type_normalise("P5"), "poteau")
        self.assertEqual(determiner_type_normalise("R1"), "poutre")
        self.assertEqual(determiner_type_normalise("D12"), "dalle")

    def test_repere_inconnu(self):
        self.assertIsNone(determiner_type_normalise("XYZ1"))
        self.assertIsNone(determiner_type_normalise("Bizarre_element"))


class TestOrchestrateurOCRLocal(SimpleTestCase):
    def setUp(self):
        self.jpeg_bytes = generer_image_jpeg_valide()

    def test_orchestration_nominale(self):
        ocr_brut = {
            "annotations_lues": [
                {"texte_lu": "S1(170x170x40)", "repere": "S1"},
                {"texte_lu": "P2", "repere": "P2"},
                {"texte_lu": "Bizarre1", "repere": "Bizarre1"},
            ],
            "textes_non_classes": ["Note générale : béton C25/30"],
        }

        res = orchestrer_ocr_local(self.jpeg_bytes, "image/jpeg", ocr_brut)
        
        # Validations du contrat OCR V1
        self.assertEqual(res["source"], "MOCK")
        self.assertTrue(res["validation_humaine_requise"])
        self.assertEqual(res["textes_non_classes"], ["Note générale : béton C25/30"])
        
        annotations = res["annotations_lues"]
        self.assertEqual(len(annotations), 3)

        # S1(170x170x40)
        self.assertEqual(annotations[0]["texte_lu"], "S1(170x170x40)")
        self.assertEqual(annotations[0]["repere"], "S1")
        self.assertEqual(annotations[0]["type_normalise"], "semelle")
        self.assertEqual(annotations[0]["dimensions_parsees"]["valeurs"], [170.0, 170.0, 40.0])
        self.assertIsNone(annotations[0]["dimensions_parsees"]["unite"])

        # P2
        self.assertEqual(annotations[1]["texte_lu"], "P2")
        self.assertEqual(annotations[1]["repere"], "P2")
        self.assertEqual(annotations[1]["type_normalise"], "poteau")
        self.assertIsNone(annotations[1]["dimensions_parsees"])

        # Bizarre1 (inconnu mais conservé)
        self.assertEqual(annotations[2]["texte_lu"], "Bizarre1")
        self.assertEqual(annotations[2]["repere"], "Bizarre1")
        self.assertIsNone(annotations[2]["type_normalise"])
        self.assertIsNone(annotations[2]["dimensions_parsees"])

    def test_conservation_conforme_dans_texte_lu(self):
        # Le mot "conforme" ne doit pas être filtré dans texte_lu
        ocr_brut = {
            "annotations_lues": [
                {"texte_lu": "S1 conforme", "repere": "S1"}
            ],
            "textes_non_classes": []
        }
        res = orchestrer_ocr_local(self.jpeg_bytes, "image/jpeg", ocr_brut)
        self.assertEqual(res["annotations_lues"][0]["texte_lu"], "S1 conforme")

    def test_rejet_orchestration_si_image_invalide(self):
        ocr_brut = {
            "annotations_lues": [],
            "textes_non_classes": []
        }
        # Doit échouer sur la validation d'image avant même de regarder le JSON
        with self.assertRaises(ValueError):
            orchestrer_ocr_local(b"faux_bytes", "image/jpeg", ocr_brut)
