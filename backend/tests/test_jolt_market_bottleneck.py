import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[2] / "tools" / "jolt_market_bottleneck.py"
    spec = importlib.util.spec_from_file_location("jolt_market_bottleneck", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checkpoint_parser_keeps_completed_lines_after_partial_timeout() -> None:
    module = _module()
    events = module._decode_lines(
        b'{"stage":"_scope_data","event":"start","at_seconds":1.2}\n'
        b'{"stage":"_scope_data","event":"finish","at_seconds":3.2,"duration_seconds":2.0}\n'
        b'{"stage":"_deduplicate_market_postings","event":"start","at_seconds":3.2}\n'
        b'{"stage":'
    )
    assert len(events) == 3
    assert events[-1]["stage"] == "_deduplicate_market_postings"
