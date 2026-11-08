from __future__ import annotations
from .core import sha256_json


def build_global_prompt(policy: dict, geometry: dict) -> str:
    lines=[]
    user=policy.get('global_instruction','').strip()
    if user: lines.append(user)
    else:
        lines.append('Refine the existing full image as one globally coherent scene, not as independent pictures.')
    lines += [
      'Every tile is only a spatial subset of the same full-frame image. Preserve the shared scene layout, object identity, scale, pose, and spatial relationships across tile boundaries.',
      'Follow the inherited global logic and geometry constraints. Do not invent new semantic objects unless an explicitly operator-confirmed GENERATE region allows it.',
      'Do not reinterpret crop edges as scene boundaries. Treat overlap as shared context for reconciliation, not as permission to create duplicate content.'
    ]
    for rule in policy.get('rules',[]):
        if rule.get("instruction_scope", "global") != "global":
            continue
        c=rule.get('constraints',{})
        clauses=[]
        if c.get('preserve_silhouette'): clauses.append('preserve silhouette')
        if c.get('preserve_landmarks'): clauses.append('preserve landmark positions')
        if c.get('no_pose_change'): clauses.append('do not change pose')
        if c.get('no_duplication'): clauses.append('do not duplicate the object')
        if clauses:
            oid=rule.get('object_id') or rule.get('id','object')
            lines.append(f"Global object constraint for {oid}: " + '; '.join(clauses) + '.')
    if geometry.get('geometry_status')!='operator_confirmed':
        lines.append('The supplied geometry is provisional guidance, not an operator-approved hard lock; do not claim geometry acceptance from this prompt.')
    return ' '.join(lines)


def build_local_prompt(contract: dict, tile_task: dict, policy: dict) -> str:
    pieces=[]
    rules_by_id={r.get('id'):r for r in list(policy.get('rules',[]))+list(policy.get('operator_regions',[]))}
    for rid in tile_task.get('rule_ids_inherited',[]):
        r=rules_by_id.get(rid,{})
        if r.get("instruction_scope", "tile_local" if r.get("scope") != "global" else "global") != "tile_local":
            continue
        instruction=(r.get('instruction') or '').strip()
        if instruction:
            pieces.append(instruction)
        else:
            c=r.get('constraints',{})
            if c.get('preserve_silhouette') or c.get('preserve_landmarks'):
                pieces.append('Within this tile subset, refine only surface detail while preserving the inherited global silhouette and landmark positions.')
            if r.get('action')=='PRESERVE': pieces.append('Keep this region pixel-identical to the source.')
            elif r.get('action')=='REJECT': pieces.append('Do not accept generated changes in this region; retain source content.')
            elif r.get('action')=='GENERATE': pieces.append(r.get('generation_intent','Generate only the explicitly approved content in this region.'))
    return ' '.join(dict.fromkeys(pieces))


def build_execution_groups(subsets: dict, policy: dict) -> dict:
    grouped={}
    global_prompt=subsets["contract"].get("global_conditioning_prompt") or build_global_prompt(policy, {})
    for entry in subsets['tiles']:
        local=entry['task'].get('local_prompt','')
        sig=sha256_json({'global':global_prompt,'local':local})[:16]
        grouped.setdefault(sig,{'profile_id':sig,'global_prompt':global_prompt,'local_prompt':local,'tile_ids':[]})['tile_ids'].append(entry['task']['tile_id'])
    groups=list(grouped.values())
    return {
      'schema_version':'ige-subset-execution-groups/0.1',
      'groups':groups,
      'group_count':len(groups),
      'single_shared_sampler_batch_compatible':len(groups)==1,
      'routing_rule':'A stock SamplerCustomAdvanced conditioning object is shared by the full latent batch. If groups differ, execute groups separately or provide a validated per-sample conditioning adapter; never pretend local prompts were applied by one shared CLIP conditioning.',
      'tile_count':sum(len(g['tile_ids']) for g in groups)
    }
