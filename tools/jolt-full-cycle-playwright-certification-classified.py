from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

RESTART_PATH = Path(__file__).with_name(
    "jolt-full-cycle-playwright-certification-restart.py"
)

PROHIBITED_PHRASES = (
    "start supervised capture",
    "start capture",
    "run capture",
    "apply externally",
    "submit application",
    "send message",
)
DESTRUCTIVE_PHRASES = (
    "delete",
    "remove",
    "reset",
    "clear",
    "discard",
    "trash",
)


def load_restart() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "jolt_full_cycle_restart_with_classification", RESTART_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load restart certification from {RESTART_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalized_text(control: dict[str, str]) -> str:
    return " ".join(
        value.strip().lower()
        for value in (control.get("text", ""), control.get("name", ""))
        if value.strip()
    )


def classify_control(control: dict[str, str]) -> tuple[str, str]:
    tag = control.get("tag", "").lower()
    text = normalized_text(control)
    href = control.get("href", "").strip().lower()

    if tag == "a" and href:
        if href.startswith(("http://127.0.0.1", "http://localhost", "#", "/")):
            return "safe", "Internal navigation or local application link."
        if href.startswith(("http://", "https://", "mailto:", "tel:")):
            return "external", "Opens an external website or local mail/phone handler."
        return "unclassified", "Anchor uses an unreviewed URL scheme."

    if any(phrase in text for phrase in PROHIBITED_PHRASES):
        return "prohibited", "Live capture, external submission, or account action is not automated."

    if any(phrase in text for phrase in DESTRUCTIVE_PHRASES):
        return "destructive", "Local destructive/reset action; allowed only in disposable fixtures."

    if tag in {"button", "select", "input", "textarea", "summary"}:
        if control.get("disabled") == "true":
            return "safe", "Disabled local control observed without activation."
        if tag == "summary":
            return "safe", "Local disclosure control."
        if tag in {"input", "textarea", "select"}:
            return "safe", "Local form control operating on disposable certification data."
        return "safe", "Reviewed local UI action covered by the disposable certification boundary."

    return "unclassified", f"Interactive tag '{tag or '(missing)'}' has no reviewed policy."


def classify_inventory(
    inventory: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, int]]:
    classified: dict[str, list[dict[str, str]]] = {}
    counts = {
        "safe": 0,
        "destructive": 0,
        "external": 0,
        "prohibited": 0,
        "unclassified": 0,
    }
    for workspace, controls in inventory.items():
        classified_controls: list[dict[str, str]] = []
        for control in controls:
            classification, reason = classify_control(control)
            counts[classification] += 1
            classified_controls.append(
                {**control, "classification": classification, "classification_reason": reason}
            )
        classified[workspace] = classified_controls
    return classified, counts


def write_markdown(output_dir: Path, counts: dict[str, int]) -> None:
    lines = [
        "# JOLT full-cycle control classification",
        "",
        "Every control discovered in the initial visible state of each workspace is classified before release.",
        "",
        "| Classification | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in counts.items())
    lines.extend(
        [
            "",
            "- **safe**: local action or form control inside the disposable certification boundary.",
            "- **destructive**: local reset/removal action; never used against production data.",
            "- **external**: opens a website or system handler and is inventoried rather than followed blindly.",
            "- **prohibited**: live capture, application submission, messaging, or other account action.",
            "- **unclassified**: release-blocking control without an approved policy.",
        ]
    )
    (output_dir / "control-classification.md").write_text("\n".join(lines), encoding="utf-8")


def apply_classification(output_dir: Path) -> None:
    inventory_path = output_dir / "control-inventory.json"
    summary_path = output_dir / "certification-summary.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    classified, counts = classify_inventory(inventory)

    (output_dir / "control-classification.json").write_text(
        json.dumps(
            {
                "policy_version": "1",
                "counts": counts,
                "workspaces": classified,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_markdown(output_dir, counts)

    summary: dict[str, Any] = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["control_classification"] = counts
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if counts["unclassified"]:
        raise AssertionError(
            f"Control classification contains {counts['unclassified']} unclassified controls."
        )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-dir", type=Path, required=True)
    args, _ = parser.parse_known_args()

    restart = load_restart()
    result = int(restart.main())
    apply_classification(args.output_dir)
    print(json.dumps({"control_classification": "passed"}, indent=2))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
