"""Local policy and plans. No secrets, automatic sending, or network calls."""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import json
import re
import sys

NEEDS = ("shelter", "food", "recovery", "documents", "human")
EVENTS = ("flood", "hurricane", "wildfire", "other")
LANGUAGES = {"English": "en", "Español": "es", "বাংলা (live translation)": "bn"}
ALLOWED_HOSTS = {"www.usa.gov", "www.disasterassistance.gov", "www.fema.gov",
                 "egateway.fema.gov", "www.fns.usda.gov", "consumer.ftc.gov"}
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR GU VI AS MP".split())


def asset(name):
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "data" / name


def load_json(name):
    return json.loads(asset(name).read_text(encoding="utf-8"))


def redact(text):
    text = re.sub(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b", "[identity number removed]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)", "[number removed]", text)
    return text[:4000]


def approved_url(url):
    p = urlsplit(url)
    return p.scheme == "https" and p.hostname in ALLOWED_HOSTS and not p.username and not p.password


def usable_record(record, state, county, today=None):
    today = today or date.today()
    required = ("id", "title", "body", "source_url", "reviewed_at", "need", "state", "county")
    if any(not isinstance(record.get(k), str) for k in required):
        return False
    if record.get("approved") is not True or record.get("is_demo") is not False:
        return False
    if record["need"] not in NEEDS or not approved_url(record["source_url"]):
        return False
    if record["state"] not in ("US", state) or record["county"] not in ("", county):
        return False
    try:
        reviewed = date.fromisoformat(record["reviewed_at"])
        if reviewed > today or (today - reviewed).days > 30:
            return False
        expires = record.get("expires_on")
        if expires and date.fromisoformat(expires) < today:
            return False
    except (ValueError, TypeError):
        return False
    return True


@dataclass
class Session:
    state: str = "VA"
    county: str = "Richmond city"
    event: str = "flood"
    incident_date: str = ""
    language: str = "en"
    needs: set = field(default_factory=set)
    urgent: bool = False
    scenario: str = ""

    def validate(self):
        if self.state not in STATES:
            raise ValueError("Choose a valid two-letter U.S. state or territory code.")
        if not self.county.strip() or len(self.county) > 80 or any(c in self.county for c in "\n\r\t"):
            raise ValueError("Enter a city or county (up to 80 characters), not a street address.")
        if self.event not in EVENTS or self.language not in ("en", "es", "bn"):
            raise ValueError("Choose a supported event and language.")
        if self.incident_date:
            try:
                if date.fromisoformat(self.incident_date) > date.today():
                    raise ValueError()
            except ValueError:
                raise ValueError("Use an incident date in YYYY-MM-DD format, no later than today.")


def demo_intent(text):
    words = text.casefold()
    mapping = {
        "shelter": ("shelter", "stay", "evacuat", "homeless", "refugio", "alojamiento"),
        "food": ("food", "hungry", "meal", "water", "comida", "alimentos", "hambre"),
        "recovery": ("damage", "repair", "money", "flood", "insurance", "fema", "daño", "inund"),
        "documents": ("lost my id", "lost id", "document", "identification", "identificación", "perdí mi"),
        "human": ("human", "person", "appeal", "immigration", "representative", "persona", "apelación")}
    found = [k for k, choices in mapping.items() if any(w in words for w in choices)]
    # Deliberately conservative: any possible urgency is surfaced for user confirmation.
    urgent = any(w in words for w in ("trapped", "cannot breathe", "can't breathe", "immediate danger", "medical emergency", "atrapad", "no puedo respirar"))
    return {"needs": found or ["human"], "urgent": urgent}


def validate_intent(value):
    if not isinstance(value, dict) or set(value) != {"needs", "urgent"}:
        raise ValueError("AI intent response has an invalid shape.")
    if type(value["urgent"]) is not bool or not isinstance(value["needs"], list):
        raise ValueError("AI intent response has invalid types.")
    if not value["needs"] or any(x not in NEEDS for x in value["needs"]):
        raise ValueError("AI intent response has an unsupported need.")
    return {"needs": list(dict.fromkeys(value["needs"])), "urgent": value["urgent"]}


def make_plan(session, records, mode="demo", today=None):
    session.validate()
    es = session.language == "es" and mode == "demo"
    def tr(a, b): return b if es else a
    eligible = [r for r in records if r.get("need") in session.needs and usable_record(r, session.state, session.county, today)]
    # A deterministic plan avoids adding unsupported facts during summarization.
    lines = [tr("CRISISCONNECT — YOUR ACTION PLAN", "CRISISCONNECT — SU PLAN DE ACCIÓN"),
             tr("SIMULATION — NOT A REAL INCIDENT" if mode == "demo" else "PROTOTYPE — VERIFY WITH THE AGENCY",
                "SIMULACIÓN — NO ES UN INCIDENTE REAL"),
             f"{session.county}, {session.state} | {session.event} | {session.incident_date or tr('Date not provided', 'Fecha no indicada')}",
             tr("No eligibility, award, declaration, deadline, or shelter capacity is confirmed here.",
                "Aquí no se confirma elegibilidad, monto, declaración, plazo ni capacidad de refugios."), ""]
    if session.urgent:
        lines.extend([tr("PRIORITY: If you are in immediate danger or have a medical emergency, call 911. This app cannot dispatch help.",
                         "PRIORIDAD: Si hay peligro inmediato o una emergencia médica, llame al 911. Esta aplicación no envía ayuda."), ""])
    if not eligible:
        lines += [tr("No current approved matching record was found. Ask a representative to verify options for your location and incident.",
                     "No se encontró un registro aprobado y vigente. Pida a un representante que verifique sus opciones."),
                  "https://www.usa.gov/state-emergency-management", ""]
    for i, r in enumerate(eligible[:5], 1):
        lines.extend([f"{i}. {r.get('title_es', r['title']) if es else r['title']}",
                      r.get('body_es', r['body']) if es else r['body'],
                      f"{tr('Source', 'Fuente')}: {r['source_url']}",
                      f"{tr('Reviewed', 'Revisado')}: {r['reviewed_at']}", ""])
    lines.extend([tr("Before applying: confirm your affected location, incident dates, program opening, required documents, and deadline with the agency.",
                     "Antes de solicitar: confirme ubicación, fechas, programa, documentos y plazo con la agencia."),
                  tr("FEMA application help: 800-621-3362. Request language or accessibility support.",
                     "Ayuda para solicitar a FEMA: 800-621-3362. Pida apoyo de idioma o accesibilidad."),
                  "https://www.usa.gov/disaster-assistance",
                  tr("Fraud check: FEMA does not charge application fees. Verify the official contact before sharing personal information.",
                     "Prevenga fraudes: FEMA no cobra por solicitar ayuda. Verifique el contacto antes de compartir datos."),
                  "https://consumer.ftc.gov/consumer-alerts/2025/07/spot-avoid-fema-impersonators",
                  tr("Human handoff: referral only; no representative has been contacted.",
                     "Ayuda humana: solo referencias; no se ha contactado a un representante.")])
    return "\n".join(lines)


def plan_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_spoken_text(text):
    # Spoken output must match the approved words, including digits; punctuation may vary.
    return re.sub(r"[^\w]+", "", text.casefold())
