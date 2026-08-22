import io
import json
import base64
from unittest import mock
from django.test import SimpleTestCase
from PIL import Image

from projets.services.assistant_ia.client import GeminiAIClient, MockAIClient, get_ai_client, LLMServiceError
from projets.services.assistant_ia.vision import (
    valider_physique_image,
    parser_annotation_structurelle,
    determiner_type_normalise,
    orchestrer_ocr_local,
    analyser_plan_2d,
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
        valider_physique_image(img_bytes, "image/jpeg")

    def test_image_png_valide_acceptee(self):
        img_bytes = generer_image_png_valide()
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
        self.assertIsNone(parser_annotation_structurelle("S1(170x170"))
        self.assertIsNone(parser_annotation_structurelle("S1()"))
        self.assertIsNone(parser_annotation_structurelle("S1(170xabcx40)"))
        res = parser_annotation_structurelle("SF1(50x30x40x20)")
        self.assertEqual(res["valeurs"], [50.0, 30.0, 40.0, 20.0])


class TestDeterminerTypeNormalise(SimpleTestCase):
    def test_mapping_prioritaire_SF_avant_S(self):
        self.assertEqual(determiner_type_normalise("SF1"), "semelle_filante")
        self.assertEqual(determiner_type_normalise("SF_10"), "semelle_filante")
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

        self.assertEqual(res["source"], "MOCK")
        self.assertTrue(res["validation_humaine_requise"])
        self.assertEqual(res["textes_non_classes"], ["Note générale : béton C25/30"])

        annotations = res["annotations_lues"]
        self.assertEqual(len(annotations), 3)

        self.assertEqual(annotations[0]["texte_lu"], "S1(170x170x40)")
        self.assertEqual(annotations[0]["repere"], "S1")
        self.assertEqual(annotations[0]["type_normalise"], "semelle")
        self.assertEqual(annotations[0]["dimensions_parsees"]["valeurs"], [170.0, 170.0, 40.0])
        self.assertIsNone(annotations[0]["dimensions_parsees"]["unite"])

        self.assertEqual(annotations[1]["texte_lu"], "P2")
        self.assertEqual(annotations[1]["repere"], "P2")
        self.assertEqual(annotations[1]["type_normalise"], "poteau")
        self.assertIsNone(annotations[1]["dimensions_parsees"])

        self.assertEqual(annotations[2]["texte_lu"], "Bizarre1")
        self.assertEqual(annotations[2]["repere"], "Bizarre1")
        self.assertIsNone(annotations[2]["type_normalise"])
        self.assertIsNone(annotations[2]["dimensions_parsees"])

    def test_conservation_conforme_dans_texte_lu(self):
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
        with self.assertRaises(ValueError):
            orchestrer_ocr_local(b"faux_bytes", "image/jpeg", ocr_brut)


class TestVisionClientMultimodal(SimpleTestCase):
    def setUp(self):
        self.jpeg_bytes = generer_image_jpeg_valide()
        self.png_bytes = generer_image_png_valide()

    def test_mock_client_vision_déterministe(self):
        client = MockAIClient()
        res_str = client.appeler_llm_vision("Prompt", self.jpeg_bytes, "image/jpeg")
        res = json.loads(res_str)
        self.assertIn("annotations_lues", res)
        self.assertNotIn("type_normalise", res["annotations_lues"][0])
        self.assertNotIn("dimensions_parsees", res["annotations_lues"][0])

    def test_gemini_vision_payload_formattage(self):
        client = GeminiAIClient(api_key="KEY_TEST")
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": '{"annotations_lues":[], "textes_non_classes":[]}'}]}}]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as spy_urlopen:
            client.appeler_llm_vision("Test prompt ocr", self.jpeg_bytes, "image/jpeg")

            # Analyse de la requête
            req = spy_urlopen.call_args[0][0]
            self.assertEqual(req.headers.get("X-goog-api-key"), "KEY_TEST")

            # Payload validation
            payload = json.loads(req.data.decode("utf-8"))
            parts = payload["contents"][0]["parts"]
            self.assertEqual(len(parts), 2)
            self.assertEqual(parts[0]["text"], "Test prompt ocr")

            inline_data = parts[1]["inlineData"]
            self.assertEqual(inline_data["mimeType"], "image/jpeg")
            decoded_bytes = base64.b64encode(self.jpeg_bytes).decode("utf-8")
            self.assertEqual(inline_data["data"], decoded_bytes)

    def test_gemini_vision_rejet_mime_types(self):
        client = GeminiAIClient(api_key="KEY_TEST")
        with self.assertRaises(ValueError):
            client.appeler_llm_vision("Prompt", self.jpeg_bytes, "application/pdf")
        with self.assertRaises(ValueError):
            client.appeler_llm_vision("Prompt", self.jpeg_bytes, "image/gif")

    def test_gemini_vision_rejet_bytes_invalides(self):
        client = GeminiAIClient(api_key="KEY_TEST")
        with self.assertRaises(ValueError):
            client.appeler_llm_vision("Prompt", b"", "image/jpeg")
        with self.assertRaises(ValueError):
            client.appeler_llm_vision("Prompt", "non_bytes", "image/jpeg")


class TestVisionServiceOrchestration(SimpleTestCase):
    def setUp(self):
        self.jpeg_bytes = generer_image_jpeg_valide()

    @mock.patch("projets.services.assistant_ia.vision.get_ai_client")
    def test_analyser_plan_2d_nominale_mock(self, mock_get_client):
        mock_client = MockAIClient()
        mock_get_client.return_value = mock_client

        res = analyser_plan_2d(self.jpeg_bytes, "image/jpeg")
        self.assertEqual(res["source"], "MOCK")
        self.assertTrue(res["validation_humaine_requise"])
        self.assertEqual(len(res["annotations_lues"]), 2)

        s1 = res["annotations_lues"][0]
        self.assertEqual(s1["texte_lu"], "S1(170x170x40)")
        self.assertEqual(s1["repere"], "S1")
        self.assertEqual(s1["type_normalise"], "semelle")
        self.assertEqual(s1["dimensions_parsees"]["valeurs"], [170.0, 170.0, 40.0])

        p2 = res["annotations_lues"][1]
        self.assertEqual(p2["texte_lu"], "P2")
        self.assertEqual(p2["repere"], "P2")
        self.assertEqual(p2["type_normalise"], "poteau")
        self.assertIsNone(p2["dimensions_parsees"])

    @mock.patch("projets.services.assistant_ia.vision.get_ai_client")
    def test_analyser_plan_2d_gemini_success(self, mock_get_client):
        mock_client = mock.MagicMock(spec=GeminiAIClient)
        mock_client.appeler_llm_vision.return_value = json.dumps({
            "annotations_lues": [
                {"texte_lu": "SF1(50x30)", "repere": "SF1"}
            ],
            "textes_non_classes": []
        })
        mock_get_client.return_value = mock_client

        res = analyser_plan_2d(self.jpeg_bytes, "image/jpeg")
        self.assertEqual(res["source"], "GEMINI")
        self.assertEqual(len(res["annotations_lues"]), 1)
        self.assertEqual(res["annotations_lues"][0]["type_normalise"], "semelle_filante")
        self.assertEqual(res["annotations_lues"][0]["dimensions_parsees"]["valeurs"], [50.0, 30.0])

    @mock.patch("projets.services.assistant_ia.vision.get_ai_client")
    def test_analyser_plan_2d_json_markdown_support(self, mock_get_client):
        mock_client = mock.MagicMock(spec=GeminiAIClient)
        mock_client.appeler_llm_vision.return_value = '```json\n{"annotations_lues": [{"texte_lu": "LG1", "repere": "LG1"}], "textes_non_classes": []}\n```'
        mock_get_client.return_value = mock_client

        res = analyser_plan_2d(self.jpeg_bytes, "image/jpeg")
        self.assertEqual(res["source"], "GEMINI")
        self.assertEqual(res["annotations_lues"][0]["type_normalise"], "longrine")

    @mock.patch("projets.services.assistant_ia.vision.get_ai_client")
    def test_analyser_plan_2d_fallback_sur_llm_error(self, mock_get_client):
        mock_client = mock.MagicMock(spec=GeminiAIClient)
        mock_client.appeler_llm_vision.side_effect = LLMServiceError("Timeout service", code="LLM_TIMEOUT", status_code=504)
        mock_get_client.return_value = mock_client

        res = analyser_plan_2d(self.jpeg_bytes, "image/jpeg")

        self.assertEqual(res["source"], "FALLBACK_LOCAL")
        self.assertEqual(res["annotations_lues"], [])
        self.assertEqual(res["textes_non_classes"], [])
        self.assertTrue(res["validation_humaine_requise"])
        self.assertIn("L'analyse automatique du plan n'est pas disponible", res["message"])

    @mock.patch("projets.services.assistant_ia.vision.get_ai_client")
    def test_analyser_plan_2d_fallback_sur_json_invalide(self, mock_get_client):
        mock_client = mock.MagicMock(spec=GeminiAIClient)
        mock_client.appeler_llm_vision.return_value = "Pas du JSON"
        mock_get_client.return_value = mock_client

        res = analyser_plan_2d(self.jpeg_bytes, "image/jpeg")

        self.assertEqual(res["source"], "FALLBACK_LOCAL")
        self.assertEqual(res["annotations_lues"], [])

    def test_analyser_plan_2d_rejet_immediat_sans_appel_si_image_invalide(self):
        with mock.patch("projets.services.assistant_ia.vision.get_ai_client") as spy_get_client:
            with self.assertRaises(ValueError):
                analyser_plan_2d(b"faux_jpeg_invalide", "image/jpeg")
            spy_get_client.assert_not_called()
