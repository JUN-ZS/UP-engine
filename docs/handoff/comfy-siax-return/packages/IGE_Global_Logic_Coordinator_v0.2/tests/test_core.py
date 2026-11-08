import json
import unittest
import numpy as np
from ige_logic.core import compile_contract,project_subsets,validate_child_action,ContractError
from ige_logic.ttp import positions_from_ttp_tile_dimensions
from ige_logic.reconcile import apply_logic_gate,reconcile_tiles
from ige_logic.audit import audit_candidate


def mini_geometry(w=64,h=32,status='assistant_provisional'):
    return {
      'schema_version':'ige-object-geometry/1.0','geometry_status':status,
      'source':{'width':w,'height':h,'sha256':'test'},
      'object':{'id':'subject','bbox_xyxy':[20,8,36,24],
                'polygon_xy':[[20,8],[36,8],[36,24],[20,24]],
                'landmarks':{'top':[28,8]}},
      'tolerances':{'bbox_iou_min':0.9,'silhouette_iou_min':0.85,'landmark_max_px':12},
      'provenance':{'operator_confirmation':'pending'}
    }


def mini_policy():
    return {'schema_version':'ige-global-logic-policy/0.1','policy_id':'test','revision':1,
      'default_action':'REFINE','default_constraints':{'allow_new_semantics':False,'allow_geometry_change':False},
      'rules':[{'id':'subject-geometry','scope':'object','object_id':'subject','action':'REFINE','priority':10,
                'constraints':{'preserve_silhouette':True,'preserve_landmarks':True}}],
      'operator_regions':[],
      'hierarchy':{'child_may_weaken_parent':False},
      'reconciliation':{'overlap_mean_abs_difference_threshold':0.05,'overlap_p95_abs_difference_threshold':0.20}}


class TestCore(unittest.TestCase):
    def setUp(self):
        self.comp=compile_contract((32,64),mini_geometry(),mini_policy(),'src')
        self.pos=[(0,0,40,32),(24,0,64,32)]
        self.sub=project_subsets(self.comp,self.pos,(64,32),(2,1),(32,40),2)

    def test_child_cannot_weaken_parent(self):
        with self.assertRaises(ContractError): validate_child_action('PRESERVE','GENERATE')
        validate_child_action('GENERATE','REFINE')
        validate_child_action('REFINE','REJECT')

    def test_generate_cannot_be_default_or_global_unbounded_rule(self):
        p=mini_policy(); p['default_action']='GENERATE'
        with self.assertRaises(ContractError): compile_contract((32,64),mini_geometry(),p)
        p=mini_policy(); p['rules']=[{'id':'global-gen','scope':'global','action':'GENERATE','operator_confirmed':True}]
        with self.assertRaises(ContractError): compile_contract((32,64),mini_geometry(),p)

    def test_global_rule_projection_is_invariant_to_tile_grid(self):
        # Same parent action map, different valid tile grids; every tile receives
        # the exact slice of the same global map and reconciles a global candidate.
        candidate=np.linspace(0.0,1.0,32*64*3,dtype=np.float32).reshape(32,64,3)
        grids=[
            ([(0,0,40,32),(24,0,64,32)],(2,1),(32,40)),
            ([(0,0,40,32),(12,0,52,32),(24,0,64,32)],(3,1),(32,40)),
        ]
        outputs=[]
        for positions,grid,tile_hw in grids:
            sub=project_subsets(self.comp,positions,(64,32),grid,tile_hw,len(positions))
            pieces=[]
            for entry,box in zip(sub['tiles'],sub['boxes']):
                l,t,r,b=box['position_xyxy']
                self.assertTrue(np.array_equal(entry['action_map'],self.comp['action_map'][t:b,l:r]))
                pieces.append(candidate[t:b,l:r].copy())
            rebuilt,report=reconcile_tiles(np.zeros_like(candidate),np.stack(pieces),sub)
            self.assertEqual(report['overlap_conflict_pixels'],0)
            outputs.append(rebuilt)
        self.assertTrue(np.allclose(outputs[0],candidate))
        self.assertTrue(np.allclose(outputs[1],candidate))

    def test_generate_requires_operator_confirmation(self):
        p=mini_policy(); p['operator_regions']=[{'id':'new-bg','scope':'polygon','action':'GENERATE','polygon_xy':[[1,1],[6,1],[6,6],[1,6]]}]
        with self.assertRaises(ContractError): compile_contract((32,64),mini_geometry(),p)
        p['operator_regions'][0]['operator_confirmed']=True
        c=compile_contract((32,64),mini_geometry(),p)
        self.assertEqual(int((c['action_map']==2).sum()),36)

    def test_global_geometry_rule_projects_to_all_intersecting_subsets(self):
        self.assertEqual(self.sub['contract']['contract_id'],self.sub['tiles'][0]['task']['global_contract_id'])
        self.assertEqual(self.sub['contract']['contract_id'],self.sub['tiles'][1]['task']['global_contract_id'])
        self.assertIn('subject-geometry',self.sub['tiles'][0]['task']['rule_ids_inherited'])
        self.assertIn('subject-geometry',self.sub['tiles'][1]['task']['rule_ids_inherited'])
        self.assertGreater(self.sub['tiles'][0]['task']['geometry_guard_pixels'],0)
        self.assertGreater(self.sub['tiles'][1]['task']['geometry_guard_pixels'],0)

    def test_ttp_position_adapter_and_complete_coverage(self):
        pos,grid=positions_from_ttp_tile_dimensions(64,32,40,32)
        self.assertEqual(grid,(2,1)); self.assertEqual(pos,self.pos)
        cover=np.zeros((32,64),dtype=np.uint8)
        for l,t,r,b in pos: cover[t:b,l:r]+=1
        self.assertEqual(int((cover==0).sum()),0)
        self.assertEqual(int((cover>1).sum()),16*32)

    def test_overlap_conflict_falls_back_to_original(self):
        src=np.full((32,64,3),0.1,dtype=np.float32)
        a=np.full((2,32,40,3),0.8,dtype=np.float32)
        a[1]=0.2
        merged,report=reconcile_tiles(src,a,self.sub)
        self.assertEqual(report['overlap_conflict_pixels'],16*32)
        self.assertFalse(report['overlap_consensus_pass'])
        self.assertEqual([x['tile_id'] for x in report['failed_subsets']], ['tile_0000', 'tile_0001'])
        self.assertTrue(all(x['overlap_conflict_pixels'] == 16*32 for x in report['subset_overlap_diagnostics']))
        self.sub['reconcile_report']=report
        audit=audit_candidate(src,merged,self.sub,{})
        self.assertEqual(len(audit['failed_subsets']),2)
        self.assertIn('one_or_more_tile_subsets_failed_overlap_consensus',audit['warnings'])
        # Conflicting 16-pixel overlap is unchanged from source.
        self.assertTrue(np.allclose(merged[:,24:40],src[:,24:40]))
        # Non-overlap areas use their one tile candidate.
        self.assertTrue(np.allclose(merged[:,:24],0.8))
        self.assertTrue(np.allclose(merged[:,40:],0.2))
        self.assertEqual(report['uncovered_pixels'],0)

    def test_overlap_consensus_is_written(self):
        src=np.full((32,64,3),0.1,dtype=np.float32)
        a=np.full((2,32,40,3),0.6,dtype=np.float32); a[1]=0.62
        merged,report=reconcile_tiles(src,a,self.sub)
        self.assertEqual(report['overlap_conflict_pixels'],0)
        self.assertTrue(np.allclose(merged[:,24:40],0.61,atol=1e-6))

    def test_preserve_zone_restores_original_pixels(self):
        p=mini_policy(); p['operator_regions']=[{'id':'freeze-left','scope':'polygon','action':'PRESERVE','polygon_xy':[[0,0],[12,0],[12,32],[0,32]]}]
        c=compile_contract((32,64),mini_geometry(),p)
        sub=project_subsets(c,self.pos,(64,32),(2,1),(32,40),2)
        src=np.full((2,32,40,3),0.1,dtype=np.float32); gen=np.full_like(src,0.9)
        gated,report=apply_logic_gate(src,gen,sub)
        self.assertTrue(np.allclose(gated[0,:,:12],0.1))
        self.assertTrue(np.allclose(gated[0,:,13:],0.9))

    def test_outside_ttp_coverage_is_preserved_and_provisional_blocks_acceptance(self):
        src=np.full((32,64,3),0.1,dtype=np.float32)
        tiles=np.full((2,32,40,3),0.2,dtype=np.float32)
        merged,rr=reconcile_tiles(src,tiles,self.sub); self.sub['reconcile_report']=rr
        audit=audit_candidate(src,merged,self.sub,{})
        self.assertEqual(audit['status'],'BLOCKED_PENDING_GEOMETRY_ACCEPTANCE')
        self.assertEqual(audit['outside_coverage_changed_pixels'],0)
        self.assertIn('geometry_contract_not_operator_confirmed',audit['warnings'])

    def test_iteration_feedback_carries_parent_state_without_promoting_rules(self):
        from ige_logic.core import make_iteration_feedback
        first = self.comp['contract']
        feedback = make_iteration_feedback(first, {'warnings': ['needs_review'], 'failed_subsets': []}, {'note': 'retain geometry'})
        next_comp = compile_contract((32,64), mini_geometry(), mini_policy(), 'src', feedback)
        self.assertEqual(next_comp['contract']['state']['iteration'], 1)
        self.assertEqual(next_comp['contract']['state']['state_id'], feedback['state_id'])
        self.assertEqual(next_comp['contract']['state']['parent_contract_id'], first['contract_id'])
        self.assertFalse(next_comp['contract']['state']['promotion_allowed'])
        self.assertEqual(next_comp['contract']['rules_digest'], first['rules_digest'])
        feedback2 = make_iteration_feedback(next_comp['contract'], {'warnings': [], 'failed_subsets': []}, {})
        self.assertEqual(feedback2['parent_state_id'], feedback['state_id'])
        self.assertFalse(feedback2['automatic_policy_changes'])

    def test_candidate_outside_coverage_change_fails(self):
        src=np.full((32,64,3),0.1,dtype=np.float32)
        partial=project_subsets(self.comp,[(0,0,40,32)],(64,32),(1,1),(32,40),1)
        tiles=np.full((1,32,40,3),0.2,dtype=np.float32)
        merged,rr=reconcile_tiles(src,tiles,partial); partial['reconcile_report']=rr
        merged[0,63]=0.9
        audit=audit_candidate(src,merged,partial,{})
        self.assertEqual(audit['status'],'FAIL')
        self.assertIn('pixels_outside_ttp_coverage_changed',audit['violations'])


if __name__=='__main__': unittest.main()
