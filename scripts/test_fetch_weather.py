import unittest
from pathlib import Path
import fetch_weather as fw

FIXTURE = Path(__file__).parent / "fixtures" / "IDQ11306.xml"


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.issue = fw.parse_product(FIXTURE.read_bytes())

    def test_title_is_mackay_coast(self):
        self.assertEqual(self.issue["_title"], "Mackay Coast: Bowen to St Lawrence")

    def test_issued_present(self):
        self.assertRegex(self.issue["issued"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

    def test_synopsis_nonempty(self):
        self.assertTrue(self.issue["synopsis"])

    def test_four_periods(self):
        self.assertEqual(len(self.issue["periods"]), 4)

    def test_tonight_label_and_winds(self):
        p0 = self.issue["periods"][0]
        self.assertEqual(p0["label"], "Tonight")
        self.assertIn("knots", p0["winds"])

    def test_following_day_label_format(self):
        # e.g. "Wed 8 Jul"
        self.assertRegex(self.issue["periods"][1]["label"], r"^[A-Z][a-z]{2} \d{1,2} [A-Z][a-z]{2}$")

    def test_all_fields_keys(self):
        self.assertEqual(set(self.issue["periods"][0]), {"label", "winds", "seas", "swell", "weather"})

    def test_bad_xml_raises(self):
        with self.assertRaises(ValueError):
            fw.parse_product(b"<product></product>")


class MergeTest(unittest.TestCase):
    def _issue(self, issued):
        return {"issued": issued, "synopsis": "s", "warning": None,
                "periods": [{"label": "Tonight", "winds": "Southeasterly 15 to 20 knots",
                             "seas": None, "swell": None, "weather": None}],
                "_title": "Mackay Coast: Bowen to St Lawrence"}

    def test_first_merge_shape(self):
        d = fw.merge(None, self._issue("2026-07-07T15:00:00+10:00"), "2026-07-07T05:30:00Z")
        self.assertEqual(d["product"], "IDQ11306")
        self.assertEqual(d["title"], "Mackay Coast: Bowen to St Lawrence")
        self.assertIn("Bureau of Meteorology", d["attribution"])
        self.assertEqual(len(d["history"]), 1)
        self.assertEqual(d["history"][0]["fetched"], "2026-07-07T05:30:00Z")

    def test_dedupe_same_issue(self):
        a = fw.merge(None, self._issue("2026-07-07T15:00:00+10:00"), "F1")
        b = fw.merge(a, self._issue("2026-07-07T15:00:00+10:00"), "F2")
        self.assertEqual(len(b["history"]), 1)

    def test_prepend_newest_first(self):
        a = fw.merge(None, self._issue("2026-07-07T09:00:00+10:00"), "F1")
        b = fw.merge(a, self._issue("2026-07-07T15:00:00+10:00"), "F2")
        self.assertEqual([h["issued"] for h in b["history"]],
                         ["2026-07-07T15:00:00+10:00", "2026-07-07T09:00:00+10:00"])

    def test_cap_at_20(self):
        d = None
        for i in range(21):
            d = fw.merge(d, self._issue(f"2026-07-{i + 1:02d}T15:00:00+10:00"), "F")
        self.assertEqual(len(d["history"]), 20)
        self.assertEqual(d["history"][0]["issued"], "2026-07-21T15:00:00+10:00")


if __name__ == "__main__":
    unittest.main()
