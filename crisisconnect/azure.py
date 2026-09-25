"""Real Azure adapters. Only invoked in explicitly selected live mode.

No conversation logging. Tests inject transport and client factories; live credentials
and real Azure service behavior must still be verified in the user's subscription.
"""
from datetime import date
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .config import SafeError, endpoint
from .core import NEEDS, redact, validate_intent, usable_record


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward an authorization header to a redirected host.


class JsonHTTP:
    def __init__(self):
        self.opener = build_opener(NoRedirect())

    def request(self, method, url, headers=None, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
        try:
            with self.opener.open(req, timeout=25) as response:
                payload = response.read(2_000_001)
                if len(payload) > 2_000_000:
                    raise SafeError("Service response exceeded the allowed size.")
                return json.loads(payload) if payload else {}
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise SafeError(f"Azure HTTP {status}. Check resource access, configuration, and quota; no response body was logged.") from None
        except (URLError, TimeoutError, OSError):
            raise SafeError("Azure connection failed or timed out. Check connectivity; no content was logged.") from None
        except (ValueError, TypeError):
            raise SafeError("Azure returned an unreadable response.") from None


class AzureServices:
    def __init__(self, settings, http=None, token_provider=None, sms_factory=None, email_factory=None):
        self.settings = settings
        self.http = http or JsonHTTP()
        self.token_provider = token_provider
        self._credential = None
        self.sms_factory = sms_factory
        self.email_factory = email_factory

    def credential(self):
        if self._credential is None:
            try:
                from azure.identity import DefaultAzureCredential
                self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
            except ImportError:
                raise SafeError("Install requirements-live.txt and sign in with az login first.") from None
        return self._credential

    def token(self, scope):
        if self.token_provider:
            return self.token_provider(scope)
        try:
            return self.credential().get_token(scope).token
        except SafeError:
            raise
        except Exception:
            raise SafeError("Azure sign-in failed. Run az login and verify role assignments.") from None

    def translate(self, text, target, source="en"):
        if target not in ("en", "es", "bn") or source not in ("en", "es", "bn"):
            raise SafeError("Unsupported translation language.")
        if target == source:
            return text
        base = endpoint(self.settings.translator_endpoint, (".cognitiveservices.azure.com",))
        # Keep canonical URLs and phone numbers out of machine translation.
        protected = []
        def stash(match):
            protected.append(match.group(0))
            return f"CRISISCONNECTKEEP{len(protected)-1}TOKEN"
        safe = re.sub(r"https://[^\s]+|\b\d{3}-\d{3}-\d{4}\b|\b911\b", stash, text)
        url = base + "/translator/text/v3.0/translate?" + urlencode({"api-version": "3.0", "from": source, "to": target})
        result = self.http.request("POST", url,
            {"Authorization": "Bearer " + self.token("https://cognitiveservices.azure.com/.default")},
            [{"Text": safe}])
        try:
            translated = result[0]["translations"][0]["text"]
            for i, value in enumerate(protected):
                marker = f"CRISISCONNECTKEEP{i}TOKEN"
                if translated.count(marker) != 1:
                    raise SafeError("Translation changed a protected contact or source marker. Use the original and ask for language support.")
                translated = translated.replace(marker, value)
            return translated
        except (KeyError, IndexError, TypeError):
            raise SafeError("Translator returned an unexpected response.") from None

    def search(self, session):
        base = endpoint(self.settings.search_endpoint, (".search.windows.net",))
        index = self.settings.search_index
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,127}", index):
            raise SafeError("Invalid AI Search index name.")
        state = session.state.replace("'", "''")
        county = session.county.replace("'", "''")
        body = {"search": "*", "top": 100,
                "filter": f"approved eq true and is_demo eq false and (state eq 'US' or state eq '{state}') and (county eq '' or county eq '{county}')",
                "select": "id,title,body,title_es,body_es,source_url,reviewed_at,expires_on,need,state,county,approved,is_demo"}
        result = self.http.request("POST", base + f"/indexes/{quote(index)}/docs/search?" + urlencode({"api-version": self.settings.search_api}),
            {"Authorization": "Bearer " + self.token("https://search.azure.com/.default")}, body)
        try:
            return [r for r in result["value"] if r.get("need") in session.needs
                    and usable_record(r, session.state, session.county)]
        except (KeyError, TypeError):
            raise SafeError("AI Search returned an unexpected response.") from None

    def sms(self, destination, body):
        base = endpoint(self.settings.acs_endpoint, (".communication.azure.com",))
        if not self.settings.sms_sender:
            raise SafeError("Configure ACS_SMS_SENDER after sender verification.")
        try:
            if self.sms_factory:
                client = self.sms_factory()
            else:
                from azure.communication.sms import SmsClient
                client = SmsClient(base, self.credential())
            result = list(client.send(from_=self.settings.sms_sender, to=[destination], message=body,
                                      enable_delivery_report=True))
            if not result or not result[0].successful:
                raise SafeError("ACS did not accept this SMS. Check the sender and destination configuration.")
            return {"status": "provider_accepted", "id": result[0].message_id,
                    "detail": "Accepted by ACS, not confirmation of handset delivery."}
        except ImportError:
            raise SafeError("Install requirements-live.txt for ACS messaging.") from None
        except SafeError:
            raise
        except Exception:
            raise SafeError("SMS outcome is unknown. Do not automatically retry; inspect ACS before sending again.") from None

    def email(self, destination, body):
        base = endpoint(self.settings.acs_endpoint, (".communication.azure.com",))
        if not self.settings.email_sender:
            raise SafeError("Configure ACS_EMAIL_SENDER from a verified linked email domain.")
        message = {"senderAddress": self.settings.email_sender,
                   "recipients": {"to": [{"address": destination}]},
                   "content": {"subject": "Your CrisisConnect action plan — prototype", "plainText": body}}
        try:
            if self.email_factory:
                client = self.email_factory()
            else:
                from azure.communication.email import EmailClient
                client = EmailClient(base, self.credential())
            poller = client.begin_send(message)
            result = poller.result(timeout=45)
            state = result.get("status", "")
            if state == "Succeeded":
                return {"status": "provider_accepted", "id": result.get("id", ""),
                        "detail": "Email send operation succeeded; inbox delivery is not confirmed."}
            raise SafeError("Email is pending or failed. Inspect ACS before retrying.")
        except ImportError:
            raise SafeError("Install requirements-live.txt for ACS messaging.") from None
        except SafeError:
            raise
        except Exception:
            raise SafeError("Email outcome is unknown. Do not automatically retry; inspect ACS first.") from None

    def index_documents(self, records):
        """Operator-only explicit setup command, never called by the GUI."""
        base = endpoint(self.settings.search_endpoint, (".search.windows.net",))
        index = self.settings.search_index
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,127}", index):
            raise SafeError("Invalid index name.")
        strings = ("id", "title", "body", "title_es", "body_es", "source_url", "reviewed_at", "expires_on", "need", "state", "county")
        fields = [{"name": n, "type": "Edm.String", "key": n == "id", "searchable": n in ("title", "body"),
                   "filterable": n in ("need", "state", "county")} for n in strings]
        fields += [{"name": n, "type": "Edm.Boolean", "filterable": True} for n in ("approved", "is_demo")]
        head = {"Authorization": "Bearer " + self.token("https://search.azure.com/.default")}
        path = base + f"/indexes/{quote(index)}"
        q = "?" + urlencode({"api-version": self.settings.search_api})
        self.http.request("PUT", path + q, head, {"name": index, "fields": fields})
        result = self.http.request("POST", path + "/docs/index" + q, head,
                                   {"value": [{**r, "@search.action": "mergeOrUpload"} for r in records]})
        if not result.get("value") or any(r.get("status") is not True for r in result["value"]):
            raise SafeError("At least one record failed to index. Inspect the index with sanitized diagnostics.")
        return len(result["value"])
