import unittest
import hashlib
import numpy as np
import torch
from pathlib import Path
from custom_nodes.ComfyUI_IGE_GlobalLogicCoordinator.nodes import NODE_CLASS_MAPPINGS

ROOT=Path(__file__).resolve().parents[1]

class TestComfyNodes(unittest.TestCase):
    def test_all_nodes_registered(self):
        self.assertEqual(len(NODE_CLASS_MAPPINGS),10)

    def test_end_to_end_node_plumbing(self):
        image=torch.full((1,32,64,3),0.15,dtype=torch.float32)
        geometry='''{"schema_version":"ige-object-geometry/1.0","geometry_status":"assistant_provisional","source":{"width":64,"height":32},"object":{"id":"subject","bbox_xyxy":[20,8,36,24],"polygon_xy":[[20,8],[36,8],[36,24],[20,24]],"landmarks":{}},"tolerances":{"bbox_iou_min":0.9,"silhouette_iou_min":0.85,"landmark_max_px":12},"provenance":{"operator_confirmation":"pending"}}'''
        policy='''{"schema_version":"ige-global-logic-policy/0.1","policy_id":"node-test","revision":1,"default_action":"REFINE","default_constraints":{"allow_new_semantics":false,"allow_geometry_change":false},"rules":[{"id":"subject","scope":"object","object_id":"subject","action":"REFINE","constraints":{"preserve_silhouette":true}}],"operator_regions":[],"hierarchy":{"child_may_weaken_parent":false},"reconciliation":{"overlap_mean_abs_difference_threshold":0.05,"overlap_p95_abs_difference_threshold":0.2}}'''
        import tempfile,json
        with tempfile.TemporaryDirectory() as td:
            gp=Path(td)/'g.json'; pp=Path(td)/'p.json'; gp.write_text(geometry);pp.write_text(policy)
            contract,*_=NODE_CLASS_MAPPINGS['IGE_GlobalLogicCompiler']().compile(image,str(gp),str(pp))
        tiles=torch.full((2,32,40,3),0.2,dtype=torch.float32)
        subsets,*_=NODE_CLASS_MAPPINGS['IGE_TTPSubsetProjector']().project(contract,tiles,[(0,0,40,32),(24,0,64,32)],(64,32),(2,1))
        gated,_=NODE_CLASS_MAPPINGS['IGE_ApplyLogicGate']().apply(torch.full_like(tiles,0.15),tiles,subsets)
        merged,updated,report=NODE_CLASS_MAPPINGS['IGE_GlobalReconciler']().reconcile(image,gated,subsets)
        audit,=NODE_CLASS_MAPPINGS['IGE_GlobalAcceptanceAudit']().audit(image,merged,updated,'{}')
        self.assertEqual(tuple(merged.shape),(1,32,64,3))
        self.assertIn('BLOCKED_PENDING_GEOMETRY_ACCEPTANCE',audit)
        self.assertIn('RECONCILED_WITH_ABSTENTION',report)
        noise_mask, mask_report = NODE_CLASS_MAPPINGS['IGE_TileNoiseMask']().build(updated, {'samples': torch.zeros((2, 4, 4, 5))}, 1.0, 0.25, 1.0)
        self.assertEqual(tuple(noise_mask.shape), (2, 4, 5))
        self.assertIn('geometry_guard_enabled', mask_report)


    def test_global_preflight_gate_passes_only_for_matching_confirmed_source(self):
        image = torch.full((1, 8, 12, 3), 0.25, dtype=torch.float32)
        arr = image.numpy()
        source_hash = hashlib.sha256(
            np.round(np.clip(arr[0], 0, 1) * 255).astype(np.uint8).tobytes()
        ).hexdigest()
        bundle = {
            "source_shape": [8, 12],
            "source_hash": source_hash,
            "contract": {
                "contract_id": "unit-test",
                "canvas": {"width": 12, "height": 8},
                "source_sha256": source_hash,
                "geometry_status": "operator_confirmed",
                "geometry_operator_confirmation": "operator_confirmed",
                "source_alignment_status": "operator_confirmed"
            }
        }
        with self.assertRaisesRegex(RuntimeError, "IGE_PREFLIGHT_BLOCKED"):
            NODE_CLASS_MAPPINGS["IGE_GlobalPreflightGate"]().gate(image, bundle, False)
        passed_image, report = NODE_CLASS_MAPPINGS["IGE_GlobalPreflightGate"]().gate(image, bundle, True)
        self.assertIs(passed_image, image)
        self.assertIn('"status": "PASS"', report)

    def test_global_preflight_gate_blocks_shape_mismatch(self):
        image = torch.full((1, 8, 12, 3), 0.25, dtype=torch.float32)
        arr = image.numpy()
        source_hash = hashlib.sha256(
            np.round(np.clip(arr[0], 0, 1) * 255).astype(np.uint8).tobytes()
        ).hexdigest()
        bundle = {
            "source_shape": [8, 10],
            "source_hash": source_hash,
            "contract": {
                "contract_id": "unit-test",
                "canvas": {"width": 10, "height": 8},
                "source_sha256": source_hash,
                "geometry_status": "operator_confirmed",
                "geometry_operator_confirmation": "operator_confirmed",
                "source_alignment_status": "operator_confirmed"
            }
        }
        with self.assertRaisesRegex(RuntimeError, "IGE_PREFLIGHT_BLOCKED"):
            NODE_CLASS_MAPPINGS["IGE_GlobalPreflightGate"]().gate(image, bundle, True)

    def test_tile_batch_budget_gate_blocks_multi_tile_batches_before_sampler(self):
        tiles = torch.zeros((2, 16, 16, 3), dtype=torch.float32)
        with self.assertRaisesRegex(RuntimeError, "IGE_RESOURCE_BUDGET_BLOCKED"):
            NODE_CLASS_MAPPINGS["IGE_TileBatchBudgetGuard"]().guard(
                tiles, max_tiles_per_batch=1, min_free_vram_mb=512, min_free_ram_mb=512
            )

if __name__=='__main__': unittest.main()
