from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageOps

DETAIL_MASKS = ('metal', 'stone', 'text', 'fire')
PROTECTED_MASKS = ('face', 'skin', 'eye_white')

def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_mask(path, base_size, target_size):
    with Image.open(path) as opened:
        im = ImageOps.exif_transpose(opened).convert('L')
    if im.size == base_size:
        im = im.resize(target_size, Image.Resampling.NEAREST)
    elif im.size != target_size:
        raise ValueError(f'mask size mismatch: {path}')
    return np.asarray(im, dtype=np.float32) / 255.0

def hf_energy(array, mask):
    im = Image.fromarray(np.clip(array, 0, 255).astype('uint8'), 'RGB')
    blur = np.asarray(im.filter(ImageFilter.GaussianBlur(radius=1.0)), dtype=np.float32)
    residual = np.mean(np.abs(array.astype(np.float32) - blur), axis=2)
    selected = mask > 0.5
    return float(residual[selected].mean()) if np.any(selected) else 0.0

def run_detail6(base_path, upscaled_path, masks_manifest_path, output_dir, *, gain=0.15, minimum_bytes=6_000_000):
    base_path, upscaled_path = Path(base_path), Path(upscaled_path)
    masks_path, out = Path(masks_manifest_path), Path(output_dir)
    for item in (base_path, upscaled_path, masks_path):
        if not item.is_file():
            raise FileNotFoundError(item)
    if not 0 <= gain <= 0.5 or minimum_bytes < 1:
        raise ValueError('invalid gain or byte threshold')
    meta_path = upscaled_path.with_suffix('.upscale.json')
    if not meta_path.is_file():
        raise ValueError('verified Siax sidecar is required')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    if meta.get('model_id') != '4x_NMKD-Siax_200k' or meta.get('scale') != 4:
        raise ValueError('DETAIL6 requires a verified 4x Siax master')
    if meta.get('output_sha256') != file_sha(upscaled_path) or meta.get('input_sha256') != file_sha(base_path):
        raise ValueError('Siax input/output hash does not match the sidecar')
    if meta.get('license_review') != 'user_confirmed':
        raise PermissionError('model license review is not confirmed')
    with Image.open(base_path) as opened:
        base = ImageOps.exif_transpose(opened).convert('RGB')
    with Image.open(upscaled_path) as opened:
        high = ImageOps.exif_transpose(opened).convert('RGB')
    target_size = (base.width * 4, base.height * 4)
    if high.size != target_size:
        raise ValueError(f'expected exact 4x dimensions {target_size}, got {high.size}')
    manifest = json.loads(masks_path.read_text(encoding='utf-8'))
    entries = manifest.get('masks') if manifest.get('mask_version') == '1.0' else None
    if not isinstance(entries, dict) or set(PROTECTED_MASKS) - set(entries):
        raise ValueError('mask manifest must include face, skin and eye_white masks')
    detail_names = [name for name in DETAIL_MASKS if name in entries]
    if not detail_names:
        raise ValueError('at least one of metal, stone, text or fire masks is required')
    masks = {}
    for name, rel in entries.items():
        if name not in set(DETAIL_MASKS) | set(PROTECTED_MASKS):
            raise ValueError(f'unsupported mask class: {name}')
        path = (masks_path.parent / str(rel)).resolve()
        if masks_path.parent.resolve() not in path.parents or not path.is_file():
            raise ValueError(f'invalid or missing mask path: {rel}')
        masks[name] = read_mask(path, base.size, high.size)
    allowed = np.maximum.reduce([masks[n] for n in detail_names])
    protected = np.maximum.reduce([masks[n] for n in PROTECTED_MASKS])
    feather = np.asarray(Image.fromarray((allowed * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255.0
    alpha = np.clip(feather, 0, 1) * (1 - (protected > 0).astype(np.float32))
    if not np.any(alpha > 0.01):
        raise ValueError('no writable pixels remain after protected masks')
    source = np.asarray(high, dtype=np.float32)
    low = np.asarray(high.filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32)
    # PREVENT BLUE INJECTION: metal uses Y-only HF residual; other detail masks keep RGB residual.
    from .material_chroma_guard import detail6_y_only_residual
    metal_w = masks.get('metal', np.zeros(alpha.shape, dtype=np.float32))
    metal_w = np.clip(metal_w, 0, 1) * (1 - (protected > 0).astype(np.float32))
    metal_w = np.asarray(
        Image.fromarray((metal_w * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(1.0)),
        dtype=np.float32,
    ) / 255.0
    other_w = np.clip(alpha - metal_w, 0, 1)
    # if metal not in detail set, metal_w~0 and other_w~alpha (legacy RGB residual)
    if 'metal' not in detail_names:
        other_w = alpha
        metal_w = np.zeros_like(alpha)
    output = detail6_y_only_residual(source, low, metal_w, other_w, gain=gain).astype('uint8')
    out.mkdir(parents=True, exist_ok=True)
    png = out / 'DETAIL6_WORKING.png'
    Image.fromarray(output, 'RGB').save(png, format='PNG')
    roundtrip = np.asarray(Image.open(png).convert('RGB'))
    source_u8 = np.asarray(high)
    changed_outside = int(np.count_nonzero(np.any(roundtrip != source_u8, axis=2) & (alpha <= 0)))
    changed_protected = int(np.count_nonzero(np.any(roundtrip != source_u8, axis=2) & (protected > 0)))
    zones = {}
    for name in detail_names:
        before, after = hf_energy(source, masks[name]), hf_energy(roundtrip.astype(np.float32), masks[name])
        zones[name] = {'hf_before': round(before, 6), 'hf_after': round(after, 6), 'hf_delta': round(after-before, 6)}
    jpgs, sizes = {}, {}
    for q in (98, 100):
        p = out / f'DETAIL6_FULL_q{q}.jpg'
        Image.fromarray(roundtrip, 'RGB').save(p, 'JPEG', quality=q, subsampling=0, optimize=False)
        jpgs[f'q{q}'] = str(p.resolve())
        sizes[f'q{q}'] = p.stat().st_size
    size_ok = any(n >= minimum_bytes for n in sizes.values())
    detail_delta_observed = any(row['hf_delta'] > 0 for row in zones.values())
    protected_ok = changed_outside == 0 and changed_protected == 0
    exact_4x = high.size == target_size
    execution_complete = exact_4x and protected_ok and size_ok
    report = {'detail6_version':'1.0','stage_scope':'DETAIL6_PARTIAL_EXECUTION_PATH','base_sha256':file_sha(base_path),'upscaled_sha256':file_sha(upscaled_path),'dimensions':{'width':high.width,'height':high.height},'gain':gain,'methods':['D1_verified_4x_siax_master','D2_region_masked_high_frequency_residual','D2b_metal_y_only_chroma_guard_PBI','D4_zone_limited_detail_gain','D6_jpeg_4_4_4'],'zone_proof':zones,'jpeg_outputs':jpgs,'jpeg_bytes':sizes,'pixel_audit':{'changed_outside_effective_detail_mask':changed_outside,'changed_inside_protected_masks':changed_protected},'gates':{'exact_4x':exact_4x,'protected_pixels_preserved_on_png':protected_ok,'minimum_delivery_bytes':size_ok},'diagnostic_signals':{'hf_delta_observed':detail_delta_observed,'note':'HF energy is diagnostic only; it is not a clarity or perceptual-quality acceptance metric.'},'execution_complete':execution_complete,'visual_quality_review':'REQUIRED_NOT_RUN','final_acceptance':False,'status':'TECHNICAL_CANDIDATE_REVIEW_REQUIRED' if execution_complete else 'DETAIL6_BLOCKED_OR_FAILED','limitations':['This implements only the Siax-master, material-mask residual and 4:4:4 delivery slice of legacy DETAIL6; full GRID_CLEAN/BEAT donor selection and clarity proof are not yet imported.','HF energy change is diagnostic only and does not prove clarity or perceptual improvement.','JPEG encodes are lossy; exact pixel audit applies to the PNG only.','No padding or file inflation is used to reach a byte threshold.','Identity, topology, geometry and visual quality remain separate gates.']}
    report_path = out / 'DETAIL6_REPORT.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    report['report_path'] = str(report_path.resolve())
    return report
