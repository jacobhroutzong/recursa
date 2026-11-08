import unittest
from recursa.research_manifest import compare_arms, validate_research_run

class ResearchProtocolTests(unittest.TestCase):
    def make_run(self, arm):
        return {"arm": arm, "evidence": "planned", "task_suite_sha256": "a"*64,
                "model_id": "example/open-model", "model_revision": "b"*40,
                "tokenizer_revision": "c"*40, "evaluation_version": "v1", "seed": 42,
                "decoding_config": {"temperature": 0, "max_output_tokens": 500},
                "resource_limits": {"max_calls": 8, "max_cost_usd": 0, "max_wall_seconds": 60}}
    def test_three_arms(self):
        self.assertFalse(compare_arms([self.make_run(a) for a in
            ("direct","external_context_only","recursive_subcalls")])["measured"])
    def test_revision_mismatch(self):
        r=[self.make_run(a) for a in ("direct","external_context_only","recursive_subcalls")]
        r[1]["model_revision"]="f"*40
        with self.assertRaisesRegex(ValueError, "mismatched"): compare_arms(r)
    def test_duplicate_arm(self):
        with self.assertRaises(ValueError): compare_arms([self.make_run("direct") for _ in range(3)])
    def test_unpinned_revision(self):
        r=self.make_run("direct");r["model_revision"]="latest"
        with self.assertRaises(ValueError): validate_research_run(r)
    def test_infinite_budget(self):
        r=self.make_run("direct");r["resource_limits"]["max_cost_usd"]=float("inf")
        with self.assertRaises(ValueError): validate_research_run(r)
    def test_false_measured_flag(self):
        r=self.make_run("direct");r["evidence"]="measured"
        with self.assertRaises(ValueError): validate_research_run(r)

if __name__=="__main__": unittest.main()
