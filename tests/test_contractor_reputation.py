import unittest

from workdoe.contractor_reputation import contractor_reputation


class ContractorReputationTests(unittest.TestCase):
    def test_reputation_uses_only_verified_completion_milestones(self):
        reputation = contractor_reputation(3, 2, 1)

        self.assertEqual(reputation["completion_points"], 300)
        self.assertEqual(reputation["level_label"], "Steady provider")
        self.assertEqual(
            [badge["label"] for badge in reputation["achieved_milestones"]],
            ["First finish", "Steady provider"],
        )
        self.assertEqual(reputation["next_milestone"]["label"], "Local regular")
        self.assertEqual(reputation["next_milestone"]["remaining"], 7)
        self.assertEqual(reputation["progress_value"], 3)
        self.assertEqual(reputation["progress_max"], 10)
        self.assertEqual(
            [milestone["state"] for milestone in reputation["milestones"]],
            ["earned", "current", "next", "locked"],
        )
        self.assertEqual(reputation["milestones"][1]["points"], 300)
        self.assertEqual(
            reputation["credential_signals"][0]["label"],
            "License source checked",
        )
        self.assertEqual(reputation["ranking_effect"], "none")

    def test_reputation_normalizes_untrusted_counts_and_never_infers_a_license(self):
        reputation = contractor_reputation("invalid", 1, 4)

        self.assertEqual(reputation["completion_points"], 0)
        self.assertEqual(reputation["level_label"], "New to Workdoe")
        self.assertEqual(reputation["source_checked_licenses"], 1)
        self.assertEqual(reputation["next_milestone"]["remaining"], 1)
        self.assertEqual(reputation["progress_value"], 0)
        self.assertEqual(reputation["progress_max"], 1)
        self.assertEqual(reputation["milestones"][0]["state"], "next")

    def test_first_completion_shows_absolute_progress_to_the_next_milestone(self):
        reputation = contractor_reputation(1)

        self.assertEqual(reputation["level_label"], "First finish")
        self.assertEqual(reputation["progress_value"], 1)
        self.assertEqual(reputation["progress_max"], 3)
        self.assertEqual(
            [milestone["state"] for milestone in reputation["milestones"]],
            ["current", "next", "locked", "locked"],
        )


if __name__ == "__main__":
    unittest.main()
