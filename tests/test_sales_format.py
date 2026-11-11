"""Ensure public sale copy contains only recorded deal facts."""
import unittest
from datetime import datetime

from app.db.models import Deal
from app.deals.sales import format_sales_post


class SalesFormatTests(unittest.TestCase):
    def test_sale_text_does_not_invent_channel_or_approval_method(self):
        deal = Deal(
            date=datetime(2026, 11, 9),
            agent_id=1,
            client="Synthetic Client",
            carrier="Test Carrier",
            product="Term",
            annual_premium=1200.0,
            term_months=12,
            status="Pending",
            policy_number="FORMAT-TEST-001",
            data_type="test",
        )
        text = format_sales_post(deal)
        self.assertIn("Synthetic Client", text)
        self.assertIn("Test Carrier", text)
        self.assertIn("Pending", text)
        self.assertNotIn("#inbound", text)
        self.assertNotIn("#meta", text)
        self.assertNotIn("approved instantly", text)


if __name__ == "__main__":
    unittest.main()
