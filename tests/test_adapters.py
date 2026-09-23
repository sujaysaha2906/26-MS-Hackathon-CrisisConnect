from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from crisisconnect.azure import AzureServices, JsonHTTP
from crisisconnect.config import Settings, SafeError
from crisisconnect.core import Session, load_json


class CaptureHTTP:
    def __init__(self, result): self.result, self.calls = result, []
    def request(self, method, url, headers=None, body=None):
        self.calls.append((method, url, headers, body))
        return self.result


class AdapterTests(unittest.TestCase):
    def test_translator_route_and_protected_contacts(self):
        http = CaptureHTTP([{"translations":[{"text":"Consulte CRISISCONNECTKEEP0TOKEN y llame al CRISISCONNECTKEEP1TOKEN."}]}])
        a = AzureServices(Settings(translator_endpoint="https://test.cognitiveservices.azure.com"), http, lambda s: "TEST_TOKEN")
        out = a.translate("Visit https://www.usa.gov/ and call 800-621-3362.", "es")
        method, url, headers, body = http.calls[0]
        self.assertIn("/translator/text/v3.0/translate?", url)
        self.assertIn("api-version=3.0", url)
        self.assertEqual(headers["Authorization"], "Bearer TEST_TOKEN")
        self.assertNotIn("800-621-3362", body[0]["Text"])
        self.assertIn("https://www.usa.gov/", out)
        self.assertIn("800-621-3362", out)

    def test_translator_corruption_blocks(self):
        a = AzureServices(Settings(translator_endpoint="https://test.cognitiveservices.azure.com"),
                          CaptureHTTP([{"translations":[{"text":"lost marker"}]}]), lambda s:"TEST")
        with self.assertRaises(SafeError): a.translate("Call 911", "es")

    def test_search_request_and_client_filter(self):
        record = {**load_json("resources.json")[0], "reviewed_at":date.today().isoformat(), "expires_on":""}
        http = CaptureHTTP({"value":[record, {**record,"id":"bad","state":"CA"}, {**record,"id":"demo","is_demo":True}]})
        a = AzureServices(Settings(search_endpoint="https://test.search.windows.net"), http, lambda s:"TEST")
        result = a.search(Session(needs={"shelter"}))
        self.assertEqual(len(result), 1)
        self.assertIn("is_demo eq false", http.calls[0][3]["filter"])
        self.assertIn("state eq 'VA'", http.calls[0][3]["filter"])

    def test_search_escapes_county(self):
        http = CaptureHTTP({"value":[]})
        a = AzureServices(Settings(search_endpoint="https://test.search.windows.net"), http, lambda s:"TEST")
        a.search(Session(county="O'Brien", needs={"food"}))
        self.assertIn("O''Brien", http.calls[0][3]["filter"])

    def test_sms_sdk_contract_and_status(self):
        class Result: successful=True; message_id="test-message"
        class Client:
            def send(self, **kwargs): self.args=kwargs; return [Result()]
        client=Client()
        a=AzureServices(Settings(acs_endpoint="https://test.communication.azure.com",sms_sender="+12025550100"), sms_factory=lambda:client)
        result=a.sms("+12025550123", "Synthetic test")
        self.assertEqual(client.args["to"], ["+12025550123"])
        self.assertTrue(client.args["enable_delivery_report"])
        self.assertEqual(result["status"], "provider_accepted")
        self.assertNotEqual(result["status"], "delivered")

    def test_email_sdk_contract(self):
        class Poller:
            def result(self, timeout): return {"status":"Succeeded","id":"test-operation"}
        class Client:
            def begin_send(self, message): self.message=message; return Poller()
        client=Client()
        a=AzureServices(Settings(acs_endpoint="https://test.communication.azure.com",email_sender="sender@example.com"), email_factory=lambda:client)
        result=a.email("tester@example.com", "Synthetic plan")
        self.assertEqual(client.message["content"]["plainText"], "Synthetic plan")
        self.assertEqual(client.message["recipients"]["to"][0]["address"], "tester@example.com")
        self.assertEqual(result["status"], "provider_accepted")

    def test_sms_rejection_not_reported_as_success(self):
        class Result: successful=False
        class Client:
            def send(self, **kwargs): return [Result()]
        a=AzureServices(Settings(acs_endpoint="https://test.communication.azure.com",sms_sender="+12025550100"), sms_factory=Client)
        with self.assertRaises(SafeError): a.sms("+12025550123", "Synthetic test")

    def test_index_upload_partial_failure(self):
        http = CaptureHTTP({"value":[{"status":False}]})
        a=AzureServices(Settings(search_endpoint="https://test.search.windows.net"),http,lambda s:"TEST")
        with self.assertRaises(SafeError): a.index_documents(load_json("resources.json"))


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"received":json.loads(body)}).encode())
            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302); self.send_header("Location", "/secret"); self.end_headers()
                else:
                    self.send_response(401); self.end_headers(); self.wfile.write(b"PRIVATE PROVIDER DATA")
        cls.server=ThreadingHTTPServer(("127.0.0.1",0), Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def test_real_local_http_json_roundtrip(self):
        result=JsonHTTP().request("POST", self.base, body={"synthetic":"hello"})
        self.assertEqual(result["received"]["synthetic"], "hello")

    def test_no_provider_body_leak(self):
        with self.assertRaises(SafeError) as cm: JsonHTTP().request("GET", self.base)
        self.assertNotIn("PRIVATE", str(cm.exception))
        self.assertIn("401", str(cm.exception))

    def test_auth_redirect_is_blocked(self):
        with self.assertRaises(SafeError) as cm:
            JsonHTTP().request("GET", self.base+"/redirect", {"Authorization":"Bearer TEST"})
        self.assertIn("302", str(cm.exception))
