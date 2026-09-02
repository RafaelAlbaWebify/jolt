from __future__ import annotations

import hashlib
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import Session

from jolt.market_intelligence_exchange import build_market_intelligence_exchange


def build_market_preparation_pack(session: Session) -> bytes:
    """Build a compatibility archive from source-first market evidence only.

    The unified AI work package is the authoritative workflow. This archive remains for
    compatibility and intentionally excludes local Evaluation recommendations, fit scores,
    ranking scores, and evaluation reasons.
    """

    exchange = build_market_intelligence_exchange(session)
    dataset = exchange.model_dump(mode="json")
    readme = """# Legacy JOLT Market Preparation Compatibility Pack

This compatibility export contains the same source-first Market Intelligence exchange evidence used by the unified AI workflow.

It deliberately excludes JOLT-local recommendations, fit scores, ranking scores, and evaluation reasons.

Preferred workflow: Data tools -> Export AI work package -> analyze in ChatGPT -> Import AI update.
"""
    files = {
        "README.md": readme.encode("utf-8"),
        "data/market_intelligence_exchange.json": json.dumps(
            dataset, indent=2, ensure_ascii=False, sort_keys=True
        ).encode("utf-8"),
    }
    manifest = {
        "pack_type": "jolt_market_preparation_compatibility",
        "pack_version": 2,
        "authoritative_workflow": "jolt_ai_work_package",
        "files": {
            name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in sorted(files.items())
        },
    }
    files["manifest.json"] = json.dumps(
        manifest, indent=2, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")

    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
