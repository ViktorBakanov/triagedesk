import unittest

from triage.rules import RulesTriager


class RulesTriagerTests(unittest.TestCase):
    def setUp(self):
        self.triager = RulesTriager({"vip.example": {"account_id": "A-1", "tier": "platinum"}})

    def test_keyword_and_tier_produce_suggestion(self):
        suggestion = self.triager.suggest({
            "subject": "Where is my package?",
            "body": "It is late and still has not arrived.",
            "from_email": "agent@vip.example",
        })
        self.assertEqual(suggestion.category, "delivery_delay")
        self.assertEqual(suggestion.team, "ops-east")
        self.assertEqual(suggestion.urgency, "high")
        self.assertEqual(suggestion.confidence, 0.85)

    def test_urgent_language_overrides_tier_urgency(self):
        suggestion = self.triager.suggest({
            "subject": "Damaged delivery",
            "body": "The box is broken. This is urgent.",
            "from_email": "agent@unknown.example",
        })
        self.assertEqual(suggestion.urgency, "high")
        self.assertEqual(suggestion.confidence, 0.55)

    def test_no_keyword_escalates_without_guessing(self):
        suggestion = self.triager.suggest({"subject": "Portal access", "body": "Please reset my preferences."})
        self.assertEqual(suggestion.confidence, 0.0)
        self.assertIsNone(suggestion.category)


if __name__ == "__main__":
    unittest.main()
