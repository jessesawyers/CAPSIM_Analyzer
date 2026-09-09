from decimal import Decimal

from capsim_analyzer.json_codec import report_from_json, report_to_dict, report_to_json
from tests.fixtures.round_0_expected import round_0_report


def test_json_has_version_and_iso_dates():
    payload = report_to_dict(round_0_report())

    assert payload["schema_version"] == "1.0"
    assert payload["report"]["report_date"] == "2026-12-31"
    assert payload["report"]["products"][3]["list_price"] == "33.00"
    assert payload["report"]["company_financials"][0]["balance_sheet"]["cash"] == "3434"


def test_json_is_serializable():
    document = report_to_json(round_0_report())

    assert '"schema_version": "1.0"' in document
    assert '"simulation_id": "C165051"' in document


def test_json_round_trip_preserves_core_values():
    original = round_0_report()
    restored = report_from_json(report_to_json(original))

    assert restored.simulation_id == original.simulation_id
    assert restored.product_by_name("Aft") == original.product_by_name("Aft")
    assert restored.company_financials[0].balance_sheet["total_assets"] == Decimal("96225")
