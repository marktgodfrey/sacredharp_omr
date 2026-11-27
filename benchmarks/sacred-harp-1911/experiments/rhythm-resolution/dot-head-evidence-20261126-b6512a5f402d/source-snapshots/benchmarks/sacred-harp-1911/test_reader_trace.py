from dataclasses import dataclass, field
from fractions import Fraction
from xml.etree.ElementTree import Element

from copisteria import write
from reader_trace import capture_writer_trace, serialize_reading


@dataclass
class FakeEvent:
    si: int = 7
    kind: str = "note"
    x: float = 12.5
    step: str = "B"
    octave: int = 4
    alter: int = 0
    typ: str = "eighth"
    dots: int = 1
    tup: str = "none"
    dur: Fraction = Fraction(3, 4)


def test_capture_records_only_after_original_returns(monkeypatch):
    calls = []

    def stub(meas, e, dur, voice, staff_no, whole_rest=False):
        calls.append((meas, e, dur, voice, staff_no, whole_rest))
        return "serialized-note"

    monkeypatch.setattr(write, "_note", stub)
    original = write._note
    event = FakeEvent()
    measure = Element("measure", number="12")
    with capture_writer_trace() as trace:
        result = write._note(measure, event, 36, 2, 1)
        assert result == "serialized-note"
        assert write._note is not original
        assert len(calls) == 1
        assert trace["emitted"] == [{
            "e.si": 7, "kind": "note", "x": 12.5, "step": "B", "octave": 4,
            "alter": 0, "typ": "eighth", "dots": 1, "tup": "none", "e.dur": "3/4",
            "dur": 36, "voice": 2, "staff_no": 1, "measure_number": "12",
        }]
    assert write._note is original


def test_capture_restores_after_writer_failure(monkeypatch):
    def failing(meas, e, dur, voice, staff_no, whole_rest=False):
        raise RuntimeError("serialize failed")

    monkeypatch.setattr(write, "_note", failing)
    original = write._note
    with capture_writer_trace() as trace:
        try:
            write._note(Element("measure"), FakeEvent(), 1, 1, None)
        except RuntimeError:
            pass
        else:
            raise AssertionError("writer failure should pass through")
        assert trace["emitted"] == []
    assert write._note is original


def test_serialize_reading_is_json_safe_and_keeps_frontend_candidates():
    class Sym:
        def to_dict(self):
            return {"i": 3, "cand": True, "p": 0.2}

    @dataclass
    class Staff:
        bars: list[int] = field(default_factory=lambda: [3])
        sp: float = 10.0

    @dataclass
    class System:
        staves: list[int] = field(default_factory=lambda: [0])

    class Layout:
        syms = [Sym()]
        staves = [Staff()]
        systems = [System()]

    class Reading:
        layout = Layout()
        tok = {3: {"real": {"p": 0.4}, "cls": {"v": "note_quarter"}}}

    result = serialize_reading(Reading())
    assert result["syms"][0]["cand"] is True
    assert result["tokens"]["3"]["real"]["p"] == 0.4
    assert result["staves"][0]["bars"] == [3]
