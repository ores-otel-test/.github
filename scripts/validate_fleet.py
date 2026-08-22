#!/usr/bin/env python3
"""Validate the declared test fleet and its total run-lifecycle relation."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = ("declared", "queued", "running", "passed", "failed")
EVENTS = ("dispatch", "start", "succeed", "fail")


@dataclass(frozen=True)
class Transition:
    state: str
    action: str


def transition(state: str, event: str) -> Transition:
    """Pure total relation; invalid values fail closed outside the model."""
    if state not in STATES or event not in EVENTS:
        raise ValueError(f"invalid fleet transition pair {state!r}:{event!r}")

    match state, event:
        case "declared", "dispatch":
            return Transition("queued", "queue")
        case "queued", "start":
            return Transition("running", "start")
        case "running", "succeed":
            return Transition("passed", "pass")
        case "running", "fail":
            return Transition("failed", "fail")
        case ("passed" | "failed"), _:
            return Transition(state, "ignore")
        case _:
            return Transition(state, "ignore")


def load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate(workspace: Path | None = None) -> dict[str, int]:
    manifest = load_json(ROOT / "fleet" / "repositories.json")
    vectors = load_json(ROOT / "fleet" / "lifecycle-vectors.json")

    if manifest.get("schema") != "ores-otel-test/repository-fleet/v1":
        raise ValueError("fleet manifest schema drifted")
    repositories = manifest.get("repositories")
    minimum = manifest.get("minimumRepositoryCount")
    if not isinstance(repositories, list) or not isinstance(minimum, int):
        raise ValueError("fleet manifest shape is invalid")
    if len(repositories) < minimum:
        raise ValueError(f"fleet has {len(repositories)} repositories; expected at least {minimum}")

    names: set[str] = set()
    for entry in repositories:
        if not isinstance(entry, dict):
            raise ValueError("every fleet entry must be an object")
        name = entry.get("name")
        workflow = entry.get("workflow")
        kind = entry.get("kind")
        if not all(isinstance(value, str) and value for value in (name, workflow, kind)):
            raise ValueError(f"invalid fleet entry: {entry!r}")
        if name in names:
            raise ValueError(f"duplicate repository: {name}")
        names.add(name)
        if "/" in workflow or not workflow.endswith((".yml", ".yaml")):
            raise ValueError(f"unsafe workflow name for {name}: {workflow}")
        if workspace is not None:
            repository = workspace / name
            workflow_path = repository / ".github" / "workflows" / workflow
            if not (repository / ".git").exists():
                raise ValueError(f"missing local repository: {repository}")
            if not workflow_path.is_file():
                raise ValueError(f"missing workflow: {workflow_path}")

    if vectors.get("schema") != "ores-otel-test/fleet-run-lifecycle/v1":
        raise ValueError("fleet lifecycle schema drifted")
    if vectors.get("states") != list(STATES) or vectors.get("events") != list(EVENTS):
        raise ValueError("fleet lifecycle alphabet drifted")
    cases = vectors.get("cases")
    if not isinstance(cases, list):
        raise ValueError("fleet lifecycle cases must be an array")
    expected_pairs = {(state, event) for state in STATES for event in EVENTS}
    seen_pairs: set[tuple[str, str]] = set()
    rank = {"declared": 0, "queued": 1, "running": 2, "passed": 3, "failed": 3}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("every lifecycle case must be an object")
        pair = (case.get("state"), case.get("event"))
        if pair not in expected_pairs or pair in seen_pairs:
            raise ValueError(f"invalid or duplicate lifecycle pair: {pair!r}")
        seen_pairs.add(pair)
        actual = transition(*pair)
        if actual != Transition(case.get("expectedState"), case.get("expectedAction")):
            raise ValueError(f"lifecycle refinement failed for {pair!r}: {actual!r}")
        if rank[actual.state] < rank[pair[0]]:
            raise ValueError(f"lifecycle regressed for {pair!r}: {actual!r}")
    if seen_pairs != expected_pairs:
        raise ValueError(f"lifecycle relation is not total; missing {expected_pairs - seen_pairs}")

    return {"repositories": len(names), "transitions": len(seen_pairs)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    report = validate(args.workspace)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
