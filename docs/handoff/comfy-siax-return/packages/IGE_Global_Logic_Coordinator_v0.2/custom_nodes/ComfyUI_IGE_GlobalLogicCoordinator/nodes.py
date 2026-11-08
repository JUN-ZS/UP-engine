from __future__ import annotations
import hashlib, json, os, sys
from pathlib import Path
import numpy as np
import torch

# The package is self-contained inside this custom_nodes directory.
PLUGIN_ROOT = Path(__file__).resolve().parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from ige_logic.core import compile_contract, project_subsets, load_json, make_iteration_feedback
from ige_logic.reconcile import apply_logic_gate, reconcile_tiles
from ige_logic.audit import audit_candidate
from ige_logic.coordinator import summarize_subset_compatibility
from ige_logic.masks import build_tile_noise_masks
from ige_logic.execution_gate import validate_execution_authorization


def _resolve_path(value: str) -> Path:
    raw=Path(str(value)).expanduser()
    candidates=[]
    if raw.is_absolute(): candidates.append(raw)
    else:
        candidates.append(Path.cwd()/raw)
        try:
            import folder_paths
            candidates.append(Path(folder_paths.get_input_directory())/raw)
        except Exception:
            pass
        candidates.append(PLUGIN_ROOT/'config'/raw.name)
        candidates.append(PLUGIN_ROOT/'config'/raw)
    for p in candidates:
        if p.exists() and p.is_file(): return p.resolve()
    raise FileNotFoundError(f"Cannot resolve config file {value!r}. Put it under ComfyUI/input/ige_contracts/ or the plugin config directory.")


def _to_np(image):
    if not isinstance(image, torch.Tensor):
        raise TypeError(f"Expected ComfyUI IMAGE torch.Tensor, got {type(image).__name__}")
    return image.detach().float().cpu().numpy()


def _to_tensor(array, like=None):
    a=np.ascontiguousarray(array,dtype=np.float32)
    t=torch.from_numpy(a)
    if like is not None:
        t=t.to(device=like.device,dtype=like.dtype if like.is_floating_point() else torch.float32)
    return t


def _json_text(obj):
    return json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x: x.tolist() if isinstance(x,np.ndarray) else str(x))


class IGE_GlobalLogicCompiler:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "source_image": ("IMAGE",),
            "geometry_file": ("STRING", {"default":"object_geometry.provisional.json"}),
            "policy_file": ("STRING", {"default":"global_logic_policy.json"}),
            "iteration_state_json": ("STRING", {"default":"{}", "multiline": True})
        }}
    RETURN_TYPES=("IGE_CONTRACT","IGE_ACTION_MAP","IGE_GUARD_MAP","STRING","STRING")
    RETURN_NAMES=("GLOBAL_CONTRACT","GLOBAL_ACTION_MAP","GEOMETRY_GUARD","CONTRACT_REPORT_JSON","GLOBAL_CONDITIONING_PROMPT")
    FUNCTION="compile"
    CATEGORY="IGE/Global Logic"

    def compile(self, source_image, geometry_file, policy_file, iteration_state_json="{}"):
        src=_to_np(source_image)
        if src.ndim!=4 or src.shape[0]!=1:
            raise ValueError(f"Global source_image must be batch size 1, received {src.shape}")
        geometry=load_json(_resolve_path(geometry_file))
        policy=load_json(_resolve_path(policy_file))
        iteration_state=json.loads(iteration_state_json or "{}")
        source_hash=hashlib.sha256(np.round(np.clip(src[0],0,1)*255).astype(np.uint8).tobytes()).hexdigest()
        compiled=compile_contract(src.shape[1:3],geometry,policy,source_hash,iteration_state or None)
        bundle={**compiled,"source_shape":list(src.shape[1:3]),"source_hash":source_hash,
                "geometry":geometry,"policy":policy}
        return (bundle,compiled["action_map"],compiled["geometry_guard"],_json_text(compiled["contract"]),compiled["contract"]["global_conditioning_prompt"])


class IGE_TTPSubsetProjector:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "global_contract": ("IGE_CONTRACT",),
            "tile_images": ("IMAGE",),
            "positions": ("LIST",),
            "original_size": ("TUPLE",),
            "grid_size": ("TUPLE",)
        }}
    RETURN_TYPES=("IGE_SUBSETS","STRING","STRING")
    RETURN_NAMES=("TILE_SUBSETS","SUBSET_TASKS_JSON","EXECUTION_GROUPS_JSON")
    FUNCTION="project"
    CATEGORY="IGE/Global Logic"

    def project(self, global_contract, tile_images, positions, original_size, grid_size):
        tiles=_to_np(tile_images)
        if tiles.ndim!=4: raise ValueError(f"TTP tile batch must be BHWC, got {tiles.shape}")
        h,w=tiles.shape[1:3]
        subsets=project_subsets(global_contract,positions,original_size,grid_size,(h,w),tiles.shape[0])
        tasks={"contract_id":subsets['contract']['contract_id'],"tile_count":len(subsets['tiles']),
               "tiles":[x['task'] for x in subsets['tiles']],"compatibility":summarize_subset_compatibility(subsets)}
        return (subsets,_json_text(tasks),_json_text(subsets["execution_groups"]))


class IGE_TileNoiseMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "tile_subsets": ("IGE_SUBSETS",),
            "encoded_tiles": ("LATENT",),
            "refine_noise_weight": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "guarded_refine_noise_weight": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 1.0, "step": 0.05}),
            "generate_noise_weight": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
        }}
    RETURN_TYPES=("MASK", "STRING")
    RETURN_NAMES=("TILE_LATENT_NOISE_MASK", "NOISE_MASK_REPORT_JSON")
    FUNCTION="build"
    CATEGORY="IGE/Global Logic"

    def build(self, tile_subsets, encoded_tiles, refine_noise_weight=1.0,
              guarded_refine_noise_weight=0.25, generate_noise_weight=1.0):
        if not isinstance(encoded_tiles, dict) or "samples" not in encoded_tiles:
            raise TypeError("encoded_tiles must be the VAEEncode LATENT dictionary with a 'samples' tensor")
        latent_shape = tuple(int(x) for x in encoded_tiles["samples"].shape)
        masks, report = build_tile_noise_masks(
            tile_subsets, latent_shape, refine_noise_weight,
            guarded_refine_noise_weight, generate_noise_weight
        )
        return (_to_tensor(masks), _json_text(report))


class IGE_LogicMapPreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"global_contract":("IGE_CONTRACT",)}}
    RETURN_TYPES=("IMAGE",)
    RETURN_NAMES=("LOGIC_MAP_PREVIEW",)
    FUNCTION="preview"
    CATEGORY="IGE/Global Logic"

    def preview(self,global_contract):
        am=global_contract['action_map']
        gm=global_contract['geometry_guard']
        # Visualization palette only; numeric action codes stay in IGE_ACTION_MAP.
        palette=np.array([[25,25,25],[55,160,110],[230,150,45],[210,55,65]],dtype=np.float32)/255.0
        out=palette[am]
        out[gm>0]=np.array([0.25,0.55,0.95],dtype=np.float32)
        return (_to_tensor(out[None]),)


class IGE_ApplyLogicGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "original_tiles": ("IMAGE",),
            "refined_tiles": ("IMAGE",),
            "tile_subsets": ("IGE_SUBSETS",)
        }}
    RETURN_TYPES=("IMAGE","STRING")
    RETURN_NAMES=("LOGIC_GATED_TILES","GATE_REPORT_JSON")
    FUNCTION="apply"
    CATEGORY="IGE/Global Logic"

    def apply(self,original_tiles,refined_tiles,tile_subsets):
        gated,report=apply_logic_gate(_to_np(original_tiles),_to_np(refined_tiles),tile_subsets)
        return (_to_tensor(gated,refined_tiles),_json_text(report))


class IGE_GlobalReconciler:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "source_image": ("IMAGE",),
            "gated_tiles": ("IMAGE",),
            "tile_subsets": ("IGE_SUBSETS",)
        }}
    RETURN_TYPES=("IMAGE","IGE_SUBSETS","STRING")
    RETURN_NAMES=("GLOBAL_COMPOSITE","UPDATED_SUBSETS","RECONCILE_REPORT_JSON")
    FUNCTION="reconcile"
    CATEGORY="IGE/Global Logic"

    def reconcile(self,source_image,gated_tiles,tile_subsets):
        source=_to_np(source_image)
        candidate=_to_np(gated_tiles)
        merged,report=reconcile_tiles(source,candidate,tile_subsets)
        updated=dict(tile_subsets); updated['reconcile_report']=report
        return (_to_tensor(merged[None],source_image),updated,_json_text(report))


class IGE_GlobalAcceptanceAudit:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "source_image": ("IMAGE",),
            "candidate_image": ("IMAGE",),
            "tile_subsets": ("IGE_SUBSETS",),
            "observations_json": ("STRING", {"default":"{}","multiline":True})
        }}
    RETURN_TYPES=("STRING",)
    RETURN_NAMES=("GLOBAL_AUDIT_JSON",)
    FUNCTION="audit"
    CATEGORY="IGE/Global Logic"

    def audit(self,source_image,candidate_image,tile_subsets,observations_json="{}"):
        obs=json.loads(observations_json or "{}")
        result=audit_candidate(_to_np(source_image),_to_np(candidate_image),tile_subsets,obs)
        return (_json_text(result),)


class IGE_IterationFeedback:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "global_contract": ("IGE_CONTRACT",),
            "audit_json": ("STRING", {"multiline":True}),
            "operator_feedback_json": ("STRING", {"default":"{}","multiline":True})
        }}
    RETURN_TYPES=("STRING",)
    RETURN_NAMES=("NEXT_ITERATION_STATE_JSON",)
    FUNCTION="feedback"
    CATEGORY="IGE/Global Logic"

    def feedback(self,global_contract,audit_json,operator_feedback_json="{}"):
        audit=json.loads(audit_json)
        feedback=json.loads(operator_feedback_json or "{}")
        state=make_iteration_feedback(global_contract['contract'],audit,feedback)
        return (_json_text(state),)



class IGE_ExecutionAuthorizationGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "global_contract": ("IGE_CONTRACT",),
            "latent": ("LATENT",),
            "authorization_json": ("STRING", {"default": "{}", "multiline": True}),
            "branch_id": ("STRING", {"default": "sampler"}),
        }}

    RETURN_TYPES = ("LATENT", "STRING")
    RETURN_NAMES = ("AUTHORIZED_LATENT", "EXECUTION_GATE_REPORT_JSON")
    FUNCTION = "gate"
    CATEGORY = "IGE/Global Logic"

    def gate(self, global_contract, latent, authorization_json="{}", branch_id="sampler"):
        if not isinstance(latent, dict) or "samples" not in latent:
            raise TypeError("latent must be a ComfyUI LATENT dictionary with samples")
        if not isinstance(latent["samples"], torch.Tensor):
            raise TypeError("latent.samples must be a torch.Tensor")
        report = validate_execution_authorization(global_contract, authorization_json, branch_id)
        report["latent_shape"] = [int(x) for x in latent["samples"].shape]
        report["latent_batch"] = int(latent["samples"].shape[0])
        return (latent, _json_text(report))


NODE_CLASS_MAPPINGS={
    "IGE_GlobalLogicCompiler": IGE_GlobalLogicCompiler,
    "IGE_TTPSubsetProjector": IGE_TTPSubsetProjector,
    "IGE_TileNoiseMask": IGE_TileNoiseMask,
    "IGE_LogicMapPreview": IGE_LogicMapPreview,
    "IGE_ApplyLogicGate": IGE_ApplyLogicGate,
    "IGE_GlobalReconciler": IGE_GlobalReconciler,
    "IGE_GlobalAcceptanceAudit": IGE_GlobalAcceptanceAudit,
    "IGE_IterationFeedback": IGE_IterationFeedback,
    "IGE_ExecutionAuthorizationGate": IGE_ExecutionAuthorizationGate,
}

NODE_DISPLAY_NAME_MAPPINGS={
    "IGE_GlobalLogicCompiler":"IGE · Global Logic Compiler",
    "IGE_TTPSubsetProjector":"IGE · TTP Global-to-Subset Projector",
    "IGE_TileNoiseMask":"IGE · Tile Latent Noise Mask",
    "IGE_LogicMapPreview":"IGE · Logic Map Preview",
    "IGE_ApplyLogicGate":"IGE · Tile Logic Gate",
    "IGE_GlobalReconciler":"IGE · Global Consensus Reconciler",
    "IGE_GlobalAcceptanceAudit":"IGE · Global Acceptance Audit",
    "IGE_IterationFeedback":"IGE · Iteration Feedback Compiler",
    "IGE_ExecutionAuthorizationGate":"IGE · Fail-Closed Execution Authorization Gate",
}
