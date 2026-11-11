"""Tests for automatic fresh-install data bootstrap."""
import unittest
from unittest.mock import patch

from app.bootstrap import bootstrap_application_data


class ApplicationBootstrapTests(unittest.TestCase):
    def test_bootstrap_delegates_to_idempotent_profile_initializer(self):
        with patch("app.bootstrap.create_pilot_profiles", return_value=5) as create:
            self.assertEqual(bootstrap_application_data(), 5)
            create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
