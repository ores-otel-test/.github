import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_fleet import EVENTS, STATES, transition, validate  # noqa: E402


class FleetContractTests(unittest.TestCase):
    def test_manifest_and_relation(self) -> None:
        self.assertEqual(validate(), {"repositories": 42, "transitions": 20})

    def test_relation_is_total_and_terminal_states_are_absorbing(self) -> None:
        for state in STATES:
            for event in EVENTS:
                result = transition(state, event)
                self.assertIn(result.state, STATES)
        for state in ("passed", "failed"):
            for event in EVENTS:
                self.assertEqual(transition(state, event).state, state)

    def test_values_outside_closed_alphabet_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            transition("unknown", "dispatch")
        with self.assertRaises(ValueError):
            transition("declared", "unknown")


if __name__ == "__main__":
    unittest.main()
