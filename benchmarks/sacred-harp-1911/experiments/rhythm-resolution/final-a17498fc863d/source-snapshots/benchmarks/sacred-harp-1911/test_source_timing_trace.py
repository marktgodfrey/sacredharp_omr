from fractions import Fraction

from copisteria import write
from source_timing_trace import write_timed
from test_bar_recovery import _one_bar_reading


def test_timed_writer_uses_transformed_cut_and_restores_hooks():
    rd = _one_bar_reading()
    original_meter = write._page_meter
    original_write = write.write

    def transform(built, opening):
        return built, [Fraction(1)]

    xml, emitted, timing, selected = write_timed(rd, opening="2/4", bar_transform=transform)

    assert write._page_meter is original_meter
    assert write.write is original_write
    assert selected["opening"] == "2/4"
    assert selected["cuts"] == [Fraction(1)]
    assert timing["bars"]
    assert {row["selected_cut"] for row in timing["bars"]} == {"1"}
    assert timing["xml_inventory"]["measures"]
    assert all("invisible_padding_quarters" in row for row in timing["xml_inventory"]["measures"])
    assert emitted["emitted"]
