from .features import build_sift_match_graph
from .multiview import (
    MultiViewRegistrationError,
    SimilarityFit,
    SimilarityTransform,
    fit_weighted_similarity,
    register_multiview as register_multiview_similarity,
    register_multiview_v2,
    warp_image_to_canvas,
)
from .geometry_models import (
    HomographyFit,
    HomographyTransform,
    LocalMeshPairFit,
    SUPPORTED_GEOMETRY_MODELS,
    fit_weighted_homography,
    fit_local_mesh_pair,
    evaluate_holdout_residuals,
    split_edge_anchors_holdout,
)

# Public registration entry: multi-model v2 (default geometry_model=similarity).
register_multiview = register_multiview_v2

__all__ = [
    "MultiViewRegistrationError",
    "SimilarityFit",
    "SimilarityTransform",
    "HomographyFit",
    "HomographyTransform",
    "LocalMeshPairFit",
    "SUPPORTED_GEOMETRY_MODELS",
    "build_sift_match_graph",
    "fit_weighted_similarity",
    "fit_weighted_homography",
    "fit_local_mesh_pair",
    "register_multiview",
    "register_multiview_similarity",
    "register_multiview_v2",
    "warp_image_to_canvas",
    "evaluate_holdout_residuals",
    "split_edge_anchors_holdout",
]
