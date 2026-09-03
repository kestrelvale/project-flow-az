import unittest
import shutil
from pathlib import Path
from wikiskill.storage.workspace import WorkspaceManager
from wikiskill.storage.patch import apply_patches, PatchOperationError

class TestWorkspaceStorage(unittest.TestCase):
    def setUp(self):
        self.test_root = Path("./.test_wikiskill_workspace")
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.ws = WorkspaceManager(str(self.test_root))
        self.ws.init_workspace()

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_three_layer_initialization(self):
        self.assertTrue((self.test_root / "raw" / "traces").is_dir())
        self.assertTrue((self.test_root / "wiki" / "patterns").is_dir())
        self.assertTrue((self.test_root / "skills").is_dir())
        self.assertTrue(self.ws.index_file.exists())
        self.assertTrue(self.ws.log_file.exists())
        self.assertTrue(self.ws.skill_impact_file.exists())

    def test_patch_engine(self):
        base = "line 1\nline 2\nline 3"
        edits = [
            {"op": "append", "content": "line 4"},
            {"op": "replace", "target": "line 2", "content": "line 2 modified"},
            {"op": "insert_after", "target": "line 1", "content": "\nline 1.5"}
        ]
        res = apply_patches(base, edits)
        self.assertIn("line 1.5", res)
        self.assertIn("line 2 modified", res)
        self.assertIn("line 4", res)

    def test_skills_rollback_isolated(self):
        # 初始创建技能
        self.ws.create_skill("skill_a", "# Skill A v1", "# Purpose A")
        self.ws.create_pattern("pat1.md", "# Pattern 1")
        self.ws.snapshot_skills()

        # 修改技能与 wiki
        self.ws.create_skill("skill_b", "# Skill B", "# Purpose B")
        self.ws.create_pattern("pat2.md", "# Pattern 2")
        self.ws.append_log("Iteration 1 log")

        # 触发回滚
        self.ws.rollback_skills()

        # 检验：skill_b 应该消失，skill_a 存在；但 wiki 中的 pat2.md 和 log 必须保留！
        self.assertIn("skill_a", self.ws.list_skills())
        self.assertNotIn("skill_b", self.ws.list_skills())
        self.assertIn("pat1.md", self.ws.list_patterns())
        self.assertIn("pat2.md", self.ws.list_patterns())
        self.assertIn("Iteration 1 log", self.ws.get_log())

if __name__ == "__main__":
    unittest.main()
