import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class TestWorkflowGraph(unittest.TestCase):
    def setUp(self):
        self.workflow=json.loads((ROOT/'source_reference/original_siax_with_ige_logic_coordinator_v0.2.json').read_text())
        self.nodes={n['id']:n for n in self.workflow['nodes']}
        self.links={l[0]:l for l in self.workflow['links']}

    def find_link(self, src, dst, dst_slot=None):
        return [l for l in self.workflow['links'] if l[1]==src and l[3]==dst and (dst_slot is None or l[4]==dst_slot)]

    def test_original_siax_path_retained_and_all_links_resolve(self):
        for nid,typ in {134:'ImageUpscaleWithModel',36:'TTP_Image_Tile_Batch',67:'SamplerCustomAdvanced',96:'VAEDecodeTiled',237:'ImageListToImageBatch',127:'TTP_Image_Assy'}.items():
            self.assertIn(nid,self.nodes)
            self.assertEqual(self.nodes[nid]['type'],typ)
        link_ids=set()
        for lid,src,ss,dst,ds,typ in self.workflow['links']:
            self.assertIn(src,self.nodes); self.assertIn(dst,self.nodes)
            self.assertTrue(0<=ss<len(self.nodes[src]['outputs']))
            self.assertTrue(0<=ds<len(self.nodes[dst]['inputs']))
            self.assertTrue(self.nodes[src]['outputs'][ss]['type'] in (typ,'*') or typ=='*')
            self.assertTrue(self.nodes[dst]['inputs'][ds]['type'] in (typ,'*') or typ=='*')
            self.assertNotIn(lid,link_ids); link_ids.add(lid)

    def test_baseline_A_is_unmodified(self):
        # Original blank prompt and original sampler/decode/assembly path remain exact.
        self.assertEqual(self.nodes[42]['widgets_values'], [''])
        self.assertTrue(self.find_link(42,73))
        self.assertTrue(self.find_link(73,72))
        self.assertTrue(self.find_link(72,67))
        self.assertTrue(self.find_link(67,96))
        self.assertTrue(self.find_link(96,237))
        self.assertTrue(self.find_link(237,127))
        self.assertTrue(self.find_link(127,128))
        self.assertFalse(self.find_link(300,42))
        self.assertEqual(self.nodes[300]['inputs'][3]['name'], 'iteration_state_json')

    def test_candidate_B_is_separate_and_noise_mask_precedes_sampler(self):
        self.assertEqual(self.nodes[309]['type'],'SetLatentNoiseMask')
        self.assertEqual(self.nodes[310]['type'],'SamplerCustomAdvanced')
        self.assertTrue(self.find_link(301,308))
        self.assertTrue(self.find_link(129,308))
        self.assertTrue(self.find_link(308,309))
        self.assertTrue(self.find_link(129,309))
        self.assertTrue(self.find_link(309,310,4))
        self.assertTrue(self.find_link(310,311))
        self.assertTrue(self.find_link(311,312))
        self.assertTrue(self.find_link(312,302,1))
        self.assertTrue(self.find_link(300,313,1))
        self.assertTrue(self.find_link(313,314))
        self.assertTrue(self.find_link(314,315))
        self.assertTrue(self.find_link(315,310,1))
        self.assertTrue(self.find_link(303,307))

    def test_actual_ttp_metadata_is_projector_input(self):
        self.assertTrue(self.find_link(36,301,1))
        self.assertTrue(self.find_link(36,301,2))
        self.assertTrue(self.find_link(36,301,3))
        self.assertTrue(self.find_link(36,301,4))

if __name__=='__main__': unittest.main()
