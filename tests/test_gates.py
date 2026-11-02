import unittest
from ige.gates import AcceptanceReport, GateResult, HARD_GATE_NAMES


class GateTests(unittest.TestCase):
    def test_missing_gate_fails_closed(self):
        report = AcceptanceReport(tuple(GateResult(n, True) for n in HARD_GATE_NAMES[:-1]), {})
        self.assertFalse(report.accepted)

    def test_soft_quality_cannot_override_failed_hard_gate(self):
        gates = tuple(GateResult(n, n != "topology") for n in HARD_GATE_NAMES)
        report = AcceptanceReport(gates, {"sharpness": 1.0, "texture": 1.0})
        self.assertFalse(report.accepted)
