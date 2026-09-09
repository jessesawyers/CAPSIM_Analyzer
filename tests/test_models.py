from capsim_analyzer.enums import Company, Segment
from tests.fixtures.round_0_expected import round_0_report


def test_round_0_metadata_and_coverage():
    report = round_0_report()

    assert report.simulation_id == "C165051"
    assert report.round_number == 0
    assert len(report.companies) == 6
    assert set(report.segments) == set(Segment)
    assert len(report.products) == 30
    assert set(report.companies) == set(Company)
