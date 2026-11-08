import unittest
import numpy as np
from ige_logic.core import compile_contract, project_subsets
from ige_logic.masks import build_tile_noise_masks


def fixture(confirmed=False):
    geo = {
        'schema_version':'ige-object-geometry/1.0',
        'geometry_status':'operator_confirmed' if confirmed else 'assistant_provisional',
        'source':{'width':64,'height':32,'sha256':'test'},
        'object':{'id':'subject','bbox_xyxy':[16,8,32,24],
                  'polygon_xy':[[16,8],[32,8],[32,24],[16,24]]},
        'tolerances':{},
        'provenance':{'operator_confirmation':'confirmed' if confirmed else 'pending'}
    }
    pol = {
        'schema_version':'ige-global-logic-policy/0.1','policy_id':'mask-test','revision':1,
        'default_action':'REFINE',
        'default_constraints':{'allow_new_semantics':False,'allow_geometry_change':False},
        'rules':[{'id':'subject-guard','scope':'object','object_id':'subject','action':'REFINE',
                  'constraints':{'preserve_silhouette':True,'preserve_landmarks':True}}],
        'operator_regions':[{'id':'freeze-left','scope':'polygon','action':'PRESERVE',
                             'polygon_xy':[[0,0],[8,0],[8,32],[0,32]]}],
        'reconciliation':{},
        'source_alignment_status':'operator_confirmed' if confirmed else 'pending_operator_registration_to_siax_output'
    }
    compiled=compile_contract((32,64),geo,pol,'src')
    positions=[(0,0,40,32),(24,0,64,32)]
    subsets=project_subsets(compiled,positions,(64,32),(2,1),(32,40),2)
    return subsets


class TestTileNoiseMasks(unittest.TestCase):
    def test_mask_shape_and_preserve_zero(self):
        sub=fixture(False)
        masks,report=build_tile_noise_masks(sub,(2,4,4,5))
        self.assertEqual(masks.shape,(2,4,5))
        self.assertEqual(float(masks.min()),0.0)
        self.assertFalse(report['geometry_guard_enabled'])
        self.assertEqual(report['guarded_refine_pixels_image_space'],0)

    def test_registered_geometry_guard_attenuates_refine(self):
        sub=fixture(True)
        masks,report=build_tile_noise_masks(sub,(2,4,4,5),1.0,0.2,1.0)
        self.assertTrue(report['geometry_guard_enabled'])
        self.assertGreater(report['guarded_refine_pixels_image_space'],0)
        self.assertTrue(np.any(masks < 1.0))
        self.assertEqual(float(masks.min()),0.0)  # explicit PRESERVE remains hard zero

    def test_unknown_or_invalid_scale_fails_closed(self):
        sub=fixture(False)
        with self.assertRaises(ValueError):
            build_tile_noise_masks(sub,(2,4,5,5))
        with self.assertRaises(ValueError):
            build_tile_noise_masks(sub,(2,4,4,5),guarded_refine_noise_weight=1.5)


if __name__=='__main__':
    unittest.main()
