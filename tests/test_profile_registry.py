import unittest

from backend.profile_registry import PROFILES, get_profile


class ProfileRegistryTests(unittest.TestCase):
    def test_all_profiles_are_fully_configured(self):
        self.assertEqual(
            set(PROFILES),
            {"ved", "rsp", "rop", "opr"},
        )

        for profile_id in PROFILES:
            with self.subTest(profile_id=profile_id):
                profile = get_profile(profile_id)

                self.assertTrue(profile.rules_path.is_file())
                self.assertTrue(callable(profile.extract_structure))
                self.assertTrue(callable(profile.build_payload))
                self.assertTrue(callable(profile.run_control))
                self.assertTrue(callable(profile.build_diagnostics))
                self.assertTrue(profile.controlled_rules)
                self.assertGreater(profile.max_tokens, 0)

                if profile.request_mode == "single":
                    self.assertTrue(profile.system_prompt)
                else:
                    self.assertTrue(callable(profile.build_system_prompt))
                    self.assertTrue(callable(profile.build_rule_input))

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Неизвестный профиль: unknown",
        ):
            get_profile("unknown")


if __name__ == "__main__":
    unittest.main()
