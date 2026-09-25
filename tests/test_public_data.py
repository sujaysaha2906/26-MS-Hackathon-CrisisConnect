from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from crisisconnect.config import SafeError
from crisisconnect.public_data import CensusPlaces, FEMADeclarations, Place


PLACE = Place("Richmond city, VA", "VA", "51", "760", 37.54, -77.43)
NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def record(**changes):
    result = dict(fipsStateCode="51", fipsCountyCode="760", incidentBeginDate="2026-09-20T00:00:00.000Z",
                  declarationDate="2026-09-21T00:00:00.000Z", disasterNumber=123,
                  incidentType="Flood", declarationTitle="Synthetic flood", designatedArea="Richmond city")
    result.update(changes)
    return result


class FEMATests(unittest.TestCase):
    def find(self, rows):
        self.get = Mock(return_value={"DisasterDeclarationsSummaries": rows})
        return FEMADeclarations(get=self.get, now=lambda: NOW).find(PLACE)

    def test_recent_matching_county_or_statewide_declaration(self):
        for county in ("760", "000"):
            self.assertEqual(self.find([record(fipsCountyCode=county)])["disasterNumber"], 123)
        params = self.get.call_args.args[1]
        self.assertIn("fipsStateCode eq '51'", params["$filter"])
        self.assertIn("fipsCountyCode eq '760'", params["$filter"])
        self.assertIn("2026-08-26", params["$filter"])

    def test_wrong_county_wrong_state_old_or_future_records_are_not_matches(self):
        for changes in (dict(fipsCountyCode="001"), dict(fipsStateCode="06"),
                        dict(incidentBeginDate="2020-01-01T00:00:00Z"),
                        dict(incidentBeginDate="2026-10-01T00:00:00Z"),
                        dict(declarationDate="2026-10-01T00:00:00Z")):
            with self.subTest(changes=changes):
                self.assertIsNone(self.find([record(**changes)]))

    def test_empty_success_is_not_the_same_as_service_error(self):
        self.assertIsNone(self.find([]))
        with self.assertRaises(SafeError):
            FEMADeclarations(get=Mock(return_value={}), now=lambda: NOW).find(PLACE)
        with self.assertRaises(SafeError):
            self.find([{}])
        with self.assertRaises(SafeError):
            FEMADeclarations(get=Mock(side_effect=SafeError("offline"))).find(PLACE)

    def test_lookback_is_configurable(self):
        result = FEMADeclarations(lookback_days=5, get=Mock(return_value={"DisasterDeclarationsSummaries": [record(incidentBeginDate="2026-09-01T00:00:00Z")]}), now=lambda: NOW).find(PLACE)
        self.assertIsNone(result)


class CensusTests(unittest.TestCase):
    def setUp(self):
        self.get = Mock(side_effect=[
            {"features": [{"attributes": {"NAME": "Virginia", "STUSAB": "VA", "STATE": "51"}}]},
            {"features": [{"attributes": {"NAME": "Richmond city", "STATE": "51", "INTPTLAT": "37.54", "INTPTLON": "-77.43"}}]},
            {"features": []},
            {"result": {"geographies": {"Counties": [{"STATE": "51", "COUNTY": "760"}]}}},
        ])

    def test_city_and_state_resolve_to_public_point_and_fips(self):
        self.assertEqual(CensusPlaces(self.get).resolve("I am in Richmond, Virginia."), PLACE)
        self.assertIn("UPPER(BASENAME)='RICHMOND'", self.get.call_args_list[1].args[1]["where"])

    def test_address_and_confidential_text_never_sent_to_geocoder(self):
        for text in ("123 Main Street, Virginia", "my name is Jane, Virginia", "test@example.com", "my account number is 1234"):
            self.assertIsNone(CensusPlaces(self.get).resolve(text))
        self.get.assert_not_called()

    def test_ambiguous_city_is_not_silently_selected(self):
        get = Mock(side_effect=[self.get.side_effect.__next__(), {"features": []}, {"features": []}])
        self.assertIsNone(CensusPlaces(get).resolve("Unknown, VA"))

    def test_truncated_service_response_is_failure(self):
        with self.assertRaises(SafeError):
            CensusPlaces.features({"features": [], "exceededTransferLimit": True})
