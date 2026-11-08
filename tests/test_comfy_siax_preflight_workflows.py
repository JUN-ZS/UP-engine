import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs" / "handoff" / "comfy-siax-return"

WORKFLOWS = (
    PACK / "pc_高清探" / "workflow_ige_v03_dev_fp8_preflight.json",
    PACK / "pc_高清探" / "workflow_ige_v03_dev_fp8_local_preflight.json",
    PACK / "packages" / "IGE_Global_Logic_Coordinator_v0.2" / "source_reference"
    / "original_siax_with_ige_logic_coordinator_v0.2_preflight.json",
)

NODE_SNAPSHOTS = (
    PACK / "packages" / "ComfyUI_IGE_GlobalLogicCoordinator" / "nodes.py",
    PACK / "packages" / "IGE_Global_Logic_Coordinator_v0.2" / "custom_nodes"
    / "ComfyUI_IGE_GlobalLogicCoordinator" / "nodes.py",
)


def upstream_nodes(workflow, target_id):
    incoming = {}
    for link in workflow["links"]:
        _, source_id, _, dest_id, _, _ = link
        incoming.setdefault(dest_id, []).append(source_id)
    found = set()
    pending = [target_id]
    while pending:
        current = pending.pop()
        for parent in incoming.get(current, []):
            if parent not in found:
                found.add(parent)
                pending.append(parent)
    return found


def node_map(workflow):
    return {node["id"]: node for node in workflow["nodes"]}


def link_map(workflow):
    return {link[0]: link for link in workflow["links"]}


class TestComfySiaxPreflightWorkflows(unittest.TestCase):
    def test_each_patched_workflow_has_a_fail_closed_geometry_barrier(self):
        for path in WORKFLOWS:
            with self.subTest(path=str(path)):
                workflow = json.loads(path.read_text(encoding="utf-8"))
                nodes = node_map(workflow)
                links = link_map(workflow)

                self.assertEqual(nodes[342]["type"], "IGE_GlobalPreflightGate")
                self.assertEqual(nodes[343]["type"], "IGE_TileBatchBudgetGuard")
                self.assertEqual(nodes[342]["widgets_values"], [False])
                self.assertEqual(nodes[343]["widgets_values"], [1, 2048, 4096])

                self.assertEqual(links[471][1:5], [34, 0, 300, 0])
                self.assertEqual(links[529][1:5], [34, 0, 342, 0])
                self.assertEqual(links[530][1:5], [300, 0, 342, 1])
                self.assertEqual(links[234][1:5], [342, 0, 116, 0])

                self.assertEqual(links[532][1:5], [36, 0, 343, 0])
                self.assertEqual(links[285][1:5], [343, 0, 163, 0])
                self.assertEqual(links[473][1:5], [343, 0, 301, 1])
                self.assertEqual(links[494][1:5], [343, 0, 302, 0])

                # Both the original A sampler and candidate B sampler are downstream
                # of BOTH the global geometry gate and the tile resource gate.
                for sampler_id in (67, 310):
                    ancestors = upstream_nodes(workflow, sampler_id)
                    self.assertIn(342, ancestors)
                    self.assertIn(343, ancestors)
                    self.assertIn(300, ancestors)
                    self.assertIn(36, ancestors)

                # No duplicate link IDs or dangling node references.
                self.assertEqual(len(links), len(workflow["links"]))
                valid_node_ids = set(nodes)
                for link in workflow["links"]:
                    self.assertIn(link[1], valid_node_ids)
                    self.assertIn(link[3], valid_node_ids)

    def test_ige_node_snapshots_parse_and_register_both_guards(self):
        for path in NODE_SNAPSHOTS:
            with self.subTest(path=str(path)):
                source = path.read_text(encoding="utf-8")
                ast.parse(source, filename=str(path))
                self.assertIn("class IGE_GlobalPreflightGate:", source)
                self.assertIn("class IGE_TileBatchBudgetGuard:", source)
                self.assertIn('"IGE_GlobalPreflightGate": IGE_GlobalPreflightGate', source)
                self.assertIn('"IGE_TileBatchBudgetGuard": IGE_TileBatchBudgetGuard', source)
                self.assertIn("execution_allowed is True", source)
                self.assertIn("max_tiles_per_batch", source)

    def test_original_siax_baseline_remains_unmodified(self):
        original = PACK / "packages" / "IGE_Global_Logic_Coordinator_v0.2" / "source_reference" / "original_siax_workflow.json"
        workflow = json.loads(original.read_text(encoding="utf-8"))
        nodes = node_map(workflow)
        self.assertEqual(len(workflow["nodes"]), 29)
        self.assertNotIn(342, nodes)
        self.assertNotIn(343, nodes)
        self.assertEqual(nodes[67]["type"], "SamplerCustomAdvanced")


if __name__ == "__main__":
    unittest.main()
