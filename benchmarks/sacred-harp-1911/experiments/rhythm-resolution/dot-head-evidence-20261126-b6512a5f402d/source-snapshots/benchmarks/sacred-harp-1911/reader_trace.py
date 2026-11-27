"""Small, opt-in tracing helpers for the Sacred Harp reader experiments.

The writer hook records only calls that made it through the writer's final
serialization path. Rhythm decoding may call helpers speculatively; those
passes are intentionally not traced.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from fractions import Fraction
from typing import Any, Iterator


def _json_safe(value: Any) -> Any:
    """Convert common numpy/dataclass/container values into JSON-safe values."""
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Fraction):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # numpy scalar values expose item(); avoid importing numpy just for tracing.
    item = getattr(value, "item", None)
    if callable(item):
        return _json_safe(item())
    return str(value)


@contextmanager
def capture_writer_trace() -> Iterator[dict[str, list[dict[str, Any]]]]:
    """Capture successfully serialized notes while ``copisteria.write`` runs."""
    from copisteria import write

    original = write._note
    trace: dict[str, list[dict[str, Any]]] = {"emitted": []}

    def traced(*args, **kwargs):
        # Bind against the real signature so callers may use either positional
        # or keyword arguments without changing the hook's behavior.
        import inspect
        bound = inspect.signature(original).bind(*args, **kwargs)
        bound.apply_defaults()
        result = original(*args, **kwargs)
        e = bound.arguments["e"]
        meas = bound.arguments["meas"]
        number = meas.get("number") if hasattr(meas, "get") else None
        trace["emitted"].append({
            "e.si": e.si,
            "kind": e.kind,
            "x": e.x,
            "step": e.step,
            "octave": e.octave,
            "alter": e.alter,
            "typ": e.typ,
            "dots": e.dots,
            "tup": e.tup,
            "e.dur": str(e.dur),
            "dur": int(bound.arguments["dur"]),
            "voice": bound.arguments["voice"],
            "staff_no": bound.arguments["staff_no"],
            "measure_number": number,
        })
        return result

    write._note = traced
    try:
        yield trace
    finally:
        write._note = original


def serialize_reading(rd) -> dict[str, Any]:
    """Return the reading's layout symbols, model tokens, staves, and systems."""
    layout = rd.layout
    return _json_safe({
        "syms": [s.to_dict() for s in layout.syms],
        "tokens": rd.tok,
        "staves": [asdict(s) for s in layout.staves],
        "systems": [asdict(s) for s in layout.systems],
    })
