from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
NODE_FILE = ROOT / "custom_nodes/ComfyUI-SIAX-MultiImage/nodes.py"
spec = importlib.util.spec_from_file_location("siaux_multimage_nodes_test", NODE_FILE)
node_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node_module)


class FakeComfyTensor:
    def __init__(self, array):
        self.array = np.asarray(array)

    def detach(self):
        return self

    def to(self, *_args, **_kwargs):
        return self

    def numpy(self):
        return self.array


class ComfyNodeContractTests(unittest.TestCase):
    def test_custom_node_registry_has_five_nodes(self):
        expected = {"SIAXMultiImageFeatureMatches", "SIAXMultiImageGeometryRegistration",
                    "SIAXApplyGeometryTransform", "SIAXMultiImageStitch", "SIAXJSONReportPreview"}
        self.assertEqual(set(node_module.NODE_CLASS_MAPPINGS), expected)
        self.assertEqual(set(node_module.NODE_DISPLAY_NAME_MAPPINGS), expected)
        self.assertTrue(node_module.SIAXJSONReportPreview.OUTPUT_NODE)

    def test_geometry_node_stays_pending_until_threshold_is_set(self):
        points = [[5,5],[45,5],[5,45],[45,45],[25,18],[18,30]]
        anchors = [{"name": f"p{i}", "xy_a": p, "xy_b": p} for i,p in enumerate(points)]
        payload = json.dumps({"schema_version":"siaux-multiview-anchors/1.0-manual",
            "matches":[{"image_a":"image_0","image_b":"image_1","anchors":anchors}]})
        image = FakeComfyTensor(np.zeros((1,64,64,3),dtype=np.float32))
        transforms, report = node_module.SIAXMultiImageGeometryRegistration().register(
            image,image,payload,"image_0",10.0,0.0,100.0,False)
        self.assertEqual(json.loads(transforms)["geometry_gate"],"pending_threshold_not_declared")
        self.assertEqual(json.loads(report)["status"],"solved_candidate")

    def test_node_refuses_missing_image_port(self):
        payload = json.dumps({"schema_version":"siaux-multiview-anchors/1.0",
            "matches":[{"image_a":"image_0","image_b":"image_2","anchors":[]}]})
        image = FakeComfyTensor(np.zeros((1,64,64,3),dtype=np.float32))
        with self.assertRaisesRegex(ValueError,"unprovided image ports"):
            node_module.SIAXMultiImageGeometryRegistration().register(
                image,image,payload,"image_0",10.0,0.0,100.0,False)

    def test_json_report_preview_returns_comfy_text_output(self):
        payload = json.dumps({"geometry_gate":"pending_threshold_not_declared"})
        result = node_module.SIAXJSONReportPreview().show_report(payload)
        self.assertEqual(json.loads(result["ui"]["text"][0])["geometry_gate"],
                         "pending_threshold_not_declared")


class WorkflowJsonContractTests(unittest.TestCase):
    def test_workflow_links_and_node_ports_are_consistent(self):
        workflow = json.loads((ROOT/"workflows/SIAX_MultiImage_Geometric_Registration_v0.1.json").read_text())
        nodes = {node["id"]:node for node in workflow["nodes"]}
        self.assertEqual(workflow["version"],0.4)
        self.assertEqual(nodes[5]["widgets_values"][2],0.0)
        for link in workflow["links"]:
            link_id, source_id, source_slot, target_id, target_slot, _ = link
            self.assertIn(link_id,nodes[source_id]["outputs"][source_slot]["links"])
            self.assertEqual(nodes[target_id]["inputs"][target_slot]["link"],link_id)
        for node_id in (4,5,6,7,8,9,16,17):
            node = nodes[node_id]
            cls = node_module.NODE_CLASS_MAPPINGS[node["type"]]
            types = cls.INPUT_TYPES()
            names = list(types["required"])+list(types.get("optional",{}))
            self.assertTrue(set(x["name"] for x in node["inputs"]).issubset(set(names)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
