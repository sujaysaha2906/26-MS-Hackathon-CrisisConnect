import json
from pathlib import Path
import unittest
from unittest.mock import patch

from crisisconnect.config import Settings, SafeError


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parent / "config.json"
        reader = patch.object(Path, "read_text", autospec=True)
        self.reader = reader.start()
        self.addCleanup(reader.stop)

    def write(self, value):
        self.reader.return_value = json.dumps(value)

    def test_file_settings_take_precedence_over_environment(self):
        self.write({"AZURE_VOICELIVE_ENDPOINT": "https://example.services.ai.azure.com/",
                    "AZURE_VOICELIVE_MODEL": "configured-model"})
        with patch.dict("os.environ", {"AZURE_VOICELIVE_ENDPOINT": "https://other.services.ai.azure.com"}):
            settings = Settings.from_file(path=self.path)
        self.assertEqual(settings.voice_endpoint, "https://example.services.ai.azure.com")
        self.assertEqual(settings.voice_model, "configured-model")
        self.assertEqual(settings.voice_name, Settings().voice_name)

    def test_missing_or_malformed_file_has_actionable_error(self):
        self.reader.side_effect = FileNotFoundError()
        with self.assertRaisesRegex(SafeError, "config.json"):
            Settings.from_file(path=self.path)
        self.reader.side_effect = None
        self.reader.return_value = "{broken"
        with self.assertRaisesRegex(SafeError, "valid JSON"):
            Settings.from_file(path=self.path)

    def test_rejects_invalid_shapes_types_and_endpoints(self):
        for value in ([], {"AZURE_VOICELIVE_ENDPOINT": 42},
                      {"AZURE_VOICELIVE_MODEL": " "},
                      {"AZURE_VOICELIVE_ENDPOINT": "http://example.com"},
                      {"AZURE_VOICELIVE_ENDPOINT": "https://example.services.ai.azure.com:invalid"}):
            with self.subTest(value=value):
                self.write(value)
                with self.assertRaises(SafeError):
                    Settings.from_file(path=self.path)

    def test_packaged_app_loads_config_beside_executable(self):
        self.write({"AZURE_VOICELIVE_ENDPOINT": "https://example.services.ai.azure.com"})
        with patch("sys.frozen", True, create=True), patch("sys.executable", str(self.path.parent / "app.exe")):
            self.assertEqual(Settings.from_file().voice_endpoint, "https://example.services.ai.azure.com")
        self.reader.assert_called_once_with(self.path, encoding="utf-8-sig")

    def test_workflow_settings_and_invalid_retry_limits(self):
        self.write({"LOCATION_MAX_RETRIES": 5, "FEMA_LOOKBACK_DAYS": 14})
        settings = Settings.from_file(path=self.path)
        self.assertEqual(settings.location_max_retries, 5)
        self.assertEqual(settings.fema_lookback_days, 14)
        for value in (0, -1, True, "3", 3.5, 21):
            self.write({"LOCATION_MAX_RETRIES": value})
            with self.assertRaises(SafeError):
                Settings.from_file(path=self.path)
