from __future__ import annotations
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / 'source_reference/original_siax_workflow.json'
workflow = json.loads(source_path.read_text(encoding='utf-8'))
by_id = {n['id']: n for n in workflow['nodes']}
new_nodes = []
new_links = []
next_link = max(max((l[0] for l in workflow['links']), default=0), workflow.get('last_link_id', 0)) + 1


def mk_node(nid, typ, title, pos, size, inputs, outputs, widgets=None, order=50):
    return {
        'id': nid, 'type': typ, 'pos': pos, 'size': size, 'flags': {}, 'order': order,
        'mode': 0, 'inputs': inputs, 'outputs': outputs,
        'properties': {'Node name for S&R': typ}, 'widgets_values': widgets or [], 'title': title,
    }


def inp(name, typ, link=None, widget=False):
    value = {'name': name, 'type': typ, 'link': link}
    if widget:
        value['widget'] = {'name': name}
    return value


def out(name, typ, links=None):
    return {'name': name, 'type': typ, 'links': links or []}


def add(node):
    new_nodes.append(node)
    by_id[node['id']] = node
    return node


def connect(src, src_slot, dst, dst_slot, typ):
    global next_link
    link_id = next_link
    next_link += 1
    new_links.append([link_id, src, src_slot, dst, dst_slot, typ])
    by_id[src]['outputs'][src_slot].setdefault('links', []).append(link_id)
    by_id[dst]['inputs'][dst_slot]['link'] = link_id
    return link_id


def clone_node(src_id, new_id, title, pos, order):
    node = copy.deepcopy(by_id[src_id])
    node['id'] = new_id
    node['title'] = title
    node['pos'] = pos
    node['order'] = order
    for item in node.get('inputs', []):
        item['link'] = None
    for item in node.get('outputs', []):
        item['links'] = []
    return add(node)


# 300: one global contract from the full-frame SIAX output.
add(mk_node(300, 'IGE_GlobalLogicCompiler', 'IGE · Global Logic Compiler', [-2450, 1450], [340, 195],
    [inp('source_image', 'IMAGE'), inp('geometry_file', 'STRING', widget=True), inp('policy_file', 'STRING', widget=True), inp('iteration_state_json', 'STRING', widget=True)],
    [out('GLOBAL_CONTRACT', 'IGE_CONTRACT'), out('GLOBAL_ACTION_MAP', 'IGE_ACTION_MAP'), out('GEOMETRY_GUARD', 'IGE_GUARD_MAP'), out('CONTRACT_REPORT_JSON', 'STRING'), out('GLOBAL_CONDITIONING_PROMPT', 'STRING')],
    ['object_geometry.provisional.json', 'global_logic_policy.json', '{}'], 50))

# 301: project parent contract to the actual TTP runtime metadata.
add(mk_node(301, 'IGE_TTPSubsetProjector', 'IGE · TTP Global-to-Subset Projector', [-2040, 1450], [370, 220],
    [inp('global_contract', 'IGE_CONTRACT'), inp('tile_images', 'IMAGE'), inp('positions', 'LIST'), inp('original_size', 'TUPLE'), inp('grid_size', 'TUPLE')],
    [out('TILE_SUBSETS', 'IGE_SUBSETS'), out('SUBSET_TASKS_JSON', 'STRING'), out('EXECUTION_GROUPS_JSON', 'STRING')], [], 51))

# 308: a real pre-sampler denoise mask; geometry attenuation stays disabled until alignment is operator-confirmed.
add(mk_node(308, 'IGE_TileNoiseMask', 'IGE · Tile Latent Noise Mask', [-1620, 1450], [350, 190],
    [inp('tile_subsets', 'IGE_SUBSETS'), inp('encoded_tiles', 'LATENT'), inp('refine_noise_weight', 'FLOAT', widget=True), inp('guarded_refine_noise_weight', 'FLOAT', widget=True), inp('generate_noise_weight', 'FLOAT', widget=True)],
    [out('TILE_LATENT_NOISE_MASK', 'MASK'), out('NOISE_MASK_REPORT_JSON', 'STRING')], [1.0, 0.25, 1.0], 52))

# 309: stock ComfyUI node; masks the candidate-B latent before sampling.
add(mk_node(309, 'SetLatentNoiseMask', 'Set Tile Noise Mask · Candidate B', [-1210, 1450], [280, 110],
    [inp('samples', 'LATENT'), inp('mask', 'MASK')], [out('LATENT', 'LATENT')], [], 53))

# 310-312: duplicate the sampler/decode/batch path for B, preserving the original A path untouched.
clone_node(67, 310, 'SamplerCustomAdvanced · Candidate B', [-800, 1450], 54)
clone_node(96, 311, 'VAEDecodeTiled · Candidate B', [-410, 1450], 55)
clone_node(237, 312, 'ImageListToImageBatch · Candidate B', [-50, 1450], 56)

# 313-315: duplicate conditioning path; original blank-prompt A remains untouched.
clone_node(42, 313, 'CLIPTextEncode · Global Logic B', [-2450, 1780], 57)
clone_node(73, 314, 'FluxGuidance · Global Logic B', [-2040, 1780], 58)
clone_node(72, 315, 'BasicGuider · Global Logic B', [-1620, 1780], 59)

# 302-307: post-decode pixel gate, consensus, audit, feedback, preview and candidate save.
add(mk_node(302, 'IGE_ApplyLogicGate', 'IGE · Tile Logic Gate', [360, 1450], [320, 165],
    [inp('original_tiles', 'IMAGE'), inp('refined_tiles', 'IMAGE'), inp('tile_subsets', 'IGE_SUBSETS')],
    [out('LOGIC_GATED_TILES', 'IMAGE'), out('GATE_REPORT_JSON', 'STRING')], [], 60))
add(mk_node(303, 'IGE_GlobalReconciler', 'IGE · Global Consensus Reconciler', [750, 1450], [355, 180],
    [inp('source_image', 'IMAGE'), inp('gated_tiles', 'IMAGE'), inp('tile_subsets', 'IGE_SUBSETS')],
    [out('GLOBAL_COMPOSITE', 'IMAGE'), out('UPDATED_SUBSETS', 'IGE_SUBSETS'), out('RECONCILE_REPORT_JSON', 'STRING')], [], 61))
add(mk_node(304, 'IGE_GlobalAcceptanceAudit', 'IGE · Global Acceptance Audit', [1170, 1450], [355, 205],
    [inp('source_image', 'IMAGE'), inp('candidate_image', 'IMAGE'), inp('tile_subsets', 'IGE_SUBSETS'), inp('observations_json', 'STRING', widget=True)],
    [out('GLOBAL_AUDIT_JSON', 'STRING')], ['{}'], 62))
add(mk_node(305, 'IGE_IterationFeedback', 'IGE · Iteration Feedback Compiler', [1590, 1450], [355, 195],
    [inp('global_contract', 'IGE_CONTRACT'), inp('audit_json', 'STRING'), inp('operator_feedback_json', 'STRING', widget=True)],
    [out('NEXT_ITERATION_STATE_JSON', 'STRING')], ['{}'], 63))
add(mk_node(306, 'IGE_LogicMapPreview', 'IGE · Global Logic Map Preview', [-2450, 2050], [340, 80],
    [inp('global_contract', 'IGE_CONTRACT')], [out('LOGIC_MAP_PREVIEW', 'IMAGE')], [], 64))
add(mk_node(307, 'SaveImage', 'Save IGE Global Candidate B', [1170, 1800], [330, 85],
    [inp('images', 'IMAGE'), inp('filename_prefix', 'STRING', widget=True)],
    [out('image_urls', 'STRING'), out('images', 'IMAGE')], ['IGE/GlobalLogic_Candidate_B'], 65))

# Global contract and actual runtime TTP metadata.
connect(34, 0, 300, 0, 'IMAGE')
connect(300, 0, 301, 0, 'IGE_CONTRACT')
connect(36, 0, 301, 1, 'IMAGE')
connect(36, 1, 301, 2, 'LIST')
connect(36, 2, 301, 3, 'TUPLE')
connect(36, 3, 301, 4, 'TUPLE')
connect(301, 0, 308, 0, 'IGE_SUBSETS')
connect(129, 0, 308, 1, 'LATENT')
connect(308, 0, 309, 1, 'MASK')
connect(129, 0, 309, 0, 'LATENT')
connect(309, 0, 310, 4, 'LATENT')

# Candidate-B global conditioning only; original A prompt path remains unchanged.
connect(254, 1, 313, 0, 'CLIP')
connect(300, 4, 313, 1, 'STRING')
connect(313, 0, 314, 0, 'CONDITIONING')
connect(314, 0, 315, 1, 'CONDITIONING')
connect(254, 0, 315, 0, 'MODEL')

# Candidate-B sampling and decode path; shares original seed/model/sampler/sigma/VAE settings.
connect(70, 0, 310, 0, 'NOISE')
connect(315, 0, 310, 1, 'GUIDER')
connect(68, 0, 310, 2, 'SAMPLER')
connect(69, 0, 310, 3, 'SIGMAS')
connect(310, 0, 311, 0, 'LATENT')
connect(31, 0, 311, 1, 'VAE')
connect(311, 0, 312, 0, 'IMAGE')

# Output gate and global reconciliation. A remains node 67 -> 96 -> 237 -> 127 -> 128.
connect(36, 0, 302, 0, 'IMAGE')
connect(312, 0, 302, 1, 'IMAGE')
connect(301, 0, 302, 2, 'IGE_SUBSETS')
connect(34, 0, 303, 0, 'IMAGE')
connect(302, 0, 303, 1, 'IMAGE')
connect(301, 0, 303, 2, 'IGE_SUBSETS')
connect(34, 0, 304, 0, 'IMAGE')
connect(303, 0, 304, 1, 'IMAGE')
connect(303, 1, 304, 2, 'IGE_SUBSETS')
connect(300, 0, 305, 0, 'IGE_CONTRACT')
connect(304, 0, 305, 1, 'STRING')
connect(300, 0, 306, 0, 'IGE_CONTRACT')
connect(303, 0, 307, 0, 'IMAGE')

workflow['nodes'].extend(new_nodes)
workflow['links'].extend(new_links)
workflow['last_node_id'] = max(n['id'] for n in workflow['nodes'])
workflow['last_link_id'] = next_link - 1

out_path = ROOT / 'source_reference/original_siax_with_ige_logic_coordinator_v0.2.json'
out_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding='utf-8')

spec = {
    'schema_version': 'ige-comfyui-workflow-integration/0.2',
    'source_workflow': 'original_siax_workflow.json',
    'patched_workflow': out_path.name,
    'architecture': 'Keep the original SIAX/TTP path as A. Candidate B duplicates the sampler/decode/batch path and adds global prompt + tile noise masks + post-decode pixel gate + global overlap consensus.',
    'baseline_A': {
        'path': 'original node 42 blank prompt -> 73 FluxGuidance -> 72 BasicGuider -> 67 SamplerCustomAdvanced -> 96 VAEDecodeTiled -> 237 ImageListToImageBatch -> 127 TTP_Image_Assy -> 128 SaveImage',
        'modified': False
    },
    'candidate_B': {
        'path': 'global contract -> TTP subset projection -> tile noise mask -> SetLatentNoiseMask -> duplicated sampler/decode/batch -> logic gate -> global consensus -> audit',
        'nodes': {'compiler': 300, 'projector': 301, 'noise_mask': 308, 'set_latent_noise_mask': 309, 'sampler': 310, 'decoder': 311, 'batch': 312, 'clip_text': 313, 'flux_guidance': 314, 'basic_guider': 315, 'pixel_gate': 302, 'reconciler': 303, 'audit': 304, 'iteration_feedback': 305, 'logic_preview': 306, 'save_candidate': 307},
        'shared_original_inputs': ['model/LoRA stack node 254', 'noise node 70', 'sampler node 68', 'sigma schedule node 69', 'VAE loader node 31'],
        'global_prompt': 'Injected only into B conditioning; A retains original blank prompt.',
        'noise_mask': 'Per-tile MASK batch is built from parent action map. PRESERVE/REJECT=0; REFINE/GENERATE configurable; geometry guard attenuation is disabled until geometry and source coordinates are operator-confirmed.',
        'pixel_gate': 'After decode, restores exact source pixels for PRESERVE/REJECT zones.',
        'overlap': 'Writes overlap only when candidate tiles agree; disagreement abstains to original source pixels.'
    },
    'runtime_truth': {
        'tile_positions_source': 'Actual runtime POSITIONS/ORIGINAL_SIZE/GRID_SIZE emitted by original TTP_Image_Tile_Batch node 36.',
        'offline_helper': 'ige_logic.ttp is only an offline fixture builder; never substitute it for node 36 runtime metadata in production.',
        'conditioning': 'The B sampler still has one shared global conditioning. Per-tile local prompts are grouped for compatibility reporting; a separate group execution adapter is still required if groups differ.',
        'geometry': 'Noise attenuation is a soft denoising constraint, not proof of silhouette/identity preservation. Geometry acceptance still requires registered coordinates, operator confirmation and observations.'
    },
    'added_links': new_links,
    'known_blockers': [
        'Geometry remains assistant_provisional; source-coordinate registration to actual SIAX output is pending.',
        'The geometry guard is deliberately inactive in the noise mask until the above registration and operator confirmation are complete.',
        'No real ComfyUI UI execution, SIAX inference, GPU run or Cloud job was performed in this environment.'
    ]
}
(ROOT / 'source_reference/workflow_integration_spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'workflow': str(out_path), 'nodes': len(workflow['nodes']), 'links': len(workflow['links']), 'added_nodes': len(new_nodes), 'added_links': len(new_links), 'baseline_A_unmodified': True}, indent=2))
