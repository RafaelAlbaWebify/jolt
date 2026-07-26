from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected marker not found: {label}")
    return text.replace(old, new, 1)


def patch_workbench(root: Path) -> None:
    path = root / "backend/src/jolt/opportunity_workbench.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from jolt.application_readiness import readiness_payload\n",
        '''from jolt.application_readiness import (\n    PROFILE_VERSION_ID as READINESS_PROFILE_VERSION_ID,\n    READINESS_ENGINE_VERSION,\n    analyze_readiness,\n    readiness_payload,\n)\n''',
        "readiness preview imports",
    )
    text = replace_once(
        text,
        '''    readiness_report = latest_readiness_report(session, posting.id)\n    readiness = (\n        ApplicationReadinessSummary.model_validate(readiness_payload(readiness_report))\n        if readiness_report is not None\n        else None\n    )\n''',
        '''    readiness_report = latest_readiness_report(session, posting.id)\n    if readiness_report is not None:\n        readiness = ApplicationReadinessSummary.model_validate(readiness_payload(readiness_report))\n    else:\n        readiness_analysis = analyze_readiness(posting)\n        readiness = ApplicationReadinessSummary(\n            report_id="",\n            profile_version_id=READINESS_PROFILE_VERSION_ID,\n            engine_version=READINESS_ENGINE_VERSION,\n            **readiness_analysis.as_dict(),\n        )\n''',
        "ephemeral readiness preview",
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    patch_workbench(root)
    print("Read-only readiness preview follow-up applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
