"""Read-only Census geography and OpenFEMA lookups; no survivor information stored."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import SafeError


TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"
FEMA = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"


def check_cancel(cancel):
    if cancel and cancel.is_set():
        raise SafeError("Conversation ended.")


def read_json(url, params, cancel=None):
    check_cancel(cancel)
    try:
        request = Request(url + "?" + urlencode(params), headers={"User-Agent": "CrisisConnect/0.2", "Accept": "application/json"})
        with urlopen(request, timeout=20) as response:
            raw = response.read(4_000_001)
        check_cancel(cancel)
        if len(raw) > 4_000_000:
            raise ValueError()
        result = json.loads(raw)
        if not isinstance(result, dict) or "error" in result:
            raise ValueError()
        return result
    except SafeError:
        raise
    except Exception:
        raise SafeError("The public data service is unavailable. Please try again; no disaster conclusion was made.") from None


def distance_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, value))))


@dataclass(frozen=True)
class Place:
    label: str
    state: str
    state_fips: str
    county_fips: str
    latitude: float
    longitude: float


class CensusPlaces:
    def __init__(self, get=read_json):
        self.get = get
        self.states = None

    def resolve(self, spoken, cancel=None):
        # Accept only a short city/state utterance, never an address or free-form biography.
        text = re.sub(r"^(?:i am in|i'm in|i live in|my location is)\s+", "", spoken.strip(), flags=re.I).strip(" .")
        if not 3 <= len(text) <= 100 or any(not (c.isalpha() or c in " .,'-") for c in text) or re.search(r"\b(name|address|account|password|social security)\b", text, re.I):
            return None
        if self.states is None:
            payload = self.get(TIGER + "/State_County/MapServer/0/query",
                               {"where": "1=1", "outFields": "STATE,STUSAB,NAME", "returnGeometry": "false", "f": "json"}, cancel)
            self.states = self.features(payload)
            if any(not all(isinstance(state.get(key), str) for key in ("NAME", "STUSAB", "STATE"))
                   or not re.fullmatch(r"\d{2}", state["STATE"]) for state in self.states):
                self.states = None
                raise SafeError("Census returned incomplete state data. Please try again.")
        matches = []
        for state in self.states:
            for name in (state["NAME"], state["STUSAB"]):
                match = re.fullmatch(r"(.+?)[,\s]+" + re.escape(name), text, re.I)
                if match:
                    matches.append((len(name), match[1].strip(" ,"), state))
        if not matches:
            return None
        _, city, state = max(matches, key=lambda item: item[0])
        city_sql = city.upper().replace("'", "''")
        candidates = []
        for layer in (4, 5):
            payload = self.get(TIGER + f"/Places_CouSub_ConCity_SubMCD/MapServer/{layer}/query",
                               {"where": f"STATE='{state['STATE']}' AND UPPER(BASENAME)='{city_sql}'",
                                "outFields": "NAME,STATE,INTPTLAT,INTPTLON", "returnGeometry": "false", "f": "json"}, cancel)
            candidates.extend(self.features(payload))
        if len(candidates) != 1:
            return None
        place = candidates[0]
        try:
            lat, lon = float(place["INTPTLAT"]), float(place["INTPTLON"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError()
            payload = self.get("https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
                               {"x": lon, "y": lat, "benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"}, cancel)
            counties = payload["result"]["geographies"]["Counties"]
            if len(counties) != 1 or counties[0]["STATE"] != state["STATE"]:
                return None
            return Place(f"{place['NAME']}, {state['STUSAB']}", state["STUSAB"], state["STATE"], counties[0]["COUNTY"], lat, lon)
        except (KeyError, TypeError, ValueError):
            raise SafeError("Census returned incomplete location data. Please try again.") from None

    @staticmethod
    def features(payload):
        if not isinstance(payload.get("features"), list) or payload.get("exceededTransferLimit"):
            raise SafeError("Census returned incomplete location data. Please try again.")
        try:
            return [item["attributes"] for item in payload["features"]]
        except (KeyError, TypeError):
            raise SafeError("Census returned incomplete location data. Please try again.") from None


class FEMADeclarations:
    def __init__(self, lookback_days=30, get=read_json, now=None):
        self.lookback_days, self.get = lookback_days, get
        self.now = now or (lambda: datetime.now(timezone.utc))

    def find(self, place, cancel=None):
        now = self.now()
        since = now - timedelta(days=self.lookback_days)
        if not re.fullmatch(r"\d{2}", place.state_fips) or not re.fullmatch(r"\d{3}", place.county_fips):
            raise SafeError("The location has no valid FEMA county code.")
        # A recent incident window, not an inference that a hazard is active right now.
        query = (f"fipsStateCode eq '{place.state_fips}' and "
                 f"(fipsCountyCode eq '{place.county_fips}' or fipsCountyCode eq '000') and "
                 f"incidentBeginDate ge '{since.strftime('%Y-%m-%dT00:00:00.000Z')}' and "
                 f"incidentBeginDate le '{now.strftime('%Y-%m-%dT23:59:59.999Z')}'")
        payload = self.get(FEMA, {"$filter": query, "$orderby": "declarationDate desc", "$top": 1000}, cancel)
        records = payload.get("DisasterDeclarationsSummaries")
        if not isinstance(records, list):
            raise SafeError("FEMA returned an incomplete response. Please try again.")
        for record in records:
            try:
                start = datetime.fromisoformat(record["incidentBeginDate"].replace("Z", "+00:00"))
                declared = datetime.fromisoformat(record["declarationDate"].replace("Z", "+00:00"))
                if (record["fipsStateCode"] == place.state_fips
                        and record["fipsCountyCode"] in (place.county_fips, "000")
                        and since.date() <= start.date() <= now.date() and declared.date() <= now.date()):
                    return {key: record[key] for key in ("disasterNumber", "incidentType", "declarationTitle", "incidentBeginDate", "designatedArea")}
            except (KeyError, TypeError, ValueError):
                raise SafeError("FEMA returned an incomplete declaration. Please try again.") from None
        if len(records) >= 1000:
            raise SafeError("FEMA returned too many declarations to verify. Please try again later.")
        return None
