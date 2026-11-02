import unittest
from ige.contracts import AssetRef, AssetRole, Invariants, TaskContract, TaskType


class ContractTests(unittest.TestCase):
    def test_retexture_requires_material_reference(self):
        task = TaskContract(
            task_id="x", task_type=TaskType.RETEXTURE, objective="change cloth",
            assets=(AssetRef("base", AssetRole.BASE, "base.png"),),
            invariants=Invariants(protected_regions=("face",), allowed_regions=("garment",)),
            target_regions=("garment",)
        )
        with self.assertRaises(ValueError):
            task.validate()

    def test_target_cannot_overlap_protected_region(self):
        task = TaskContract(
            task_id="x", task_type=TaskType.EDIT, objective="edit",
            assets=(AssetRef("base", AssetRole.BASE, "base.png"),),
            invariants=Invariants(protected_regions=("face",), allowed_regions=("garment",)),
            target_regions=("face",)
        )
        with self.assertRaises(ValueError):
            task.validate()
