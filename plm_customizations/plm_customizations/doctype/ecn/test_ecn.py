# Copyright (c) 2024, PLM Customizations and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestECN(FrappeTestCase):
    def test_ecn_creation(self):
        """Test that ECN can be created with required fields and auto-generates name."""
        ecn = frappe.get_doc({
            "doctype": "ECN",
            "title": "Test ECN",
            "change_reason": "Test change reason"
        })
        ecn.insert()
        
        # Name should be in format ECN followed by 6 digits
        self.assertTrue(ecn.name.startswith("ECN"))
        self.assertEqual(len(ecn.name), 9)  # ECN + 6 digits
        self.assertEqual(ecn.author, frappe.session.user)
        self.assertIsNotNone(ecn.creation_date)
        
        # Clean up
        ecn.delete()
    
    def test_ecn_auto_increment(self):
        """Test that ECN numbers auto-increment."""
        ecn1 = frappe.get_doc({
            "doctype": "ECN",
            "title": "Test ECN 1",
            "change_reason": "Test change reason 1"
        })
        ecn1.insert()
        
        ecn2 = frappe.get_doc({
            "doctype": "ECN",
            "title": "Test ECN 2",
            "change_reason": "Test change reason 2"
        })
        ecn2.insert()
        
        # ECN2 number should be greater than ECN1
        num1 = int(ecn1.name[3:])
        num2 = int(ecn2.name[3:])
        self.assertGreater(num2, num1)
        
        # Clean up
        ecn2.delete()
        ecn1.delete()
