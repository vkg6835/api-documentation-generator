import io
import json
import unittest
from unittest.mock import patch

from app import llm


class ReadinessTests(unittest.TestCase):
    def status_for(self, names):
        response=io.BytesIO(json.dumps({"models":[{"name":name} for name in names]}).encode())
        with patch("app.llm.urllib.request.urlopen",return_value=response):
            return llm.model_status()

    def test_ready_and_busy_are_distinct(self):
        self.assertEqual(self.status_for([llm.MODEL])["state"],"ready")
        with llm.LOCK:
            status=self.status_for([llm.MODEL])
        self.assertTrue(status["available"])
        self.assertEqual(status["state"],"busy")

    def test_missing_model_has_install_action(self):
        status=self.status_for(["another-model:latest"])
        self.assertTrue(status["reachable"])
        self.assertFalse(status["available"])
        self.assertEqual(status["state"],"missing_model")
        self.assertIn("ollama pull "+llm.MODEL,status["action"])

    def test_offline_model_has_start_action(self):
        with patch("app.llm.urllib.request.urlopen",side_effect=OSError("offline")):
            status=llm.model_status()
        self.assertFalse(status["reachable"])
        self.assertEqual(status["state"],"unavailable")
        self.assertIn("Start Ollama",status["action"])

    def test_malformed_model_response_does_not_break_health(self):
        for payload in (b"not-json",b"[]",b'{"models":null}'):
            with self.subTest(payload=payload),patch("app.llm.urllib.request.urlopen",return_value=io.BytesIO(payload)):
                self.assertFalse(llm.model_status()["available"])
