# test_trial_balance_for_party.py
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today
from erpnext.accounts.report.trial_balance_for_party.trial_balance_for_party import (
    execute,
    toggle_debit_credit,
    is_party_name_visible,
)

class TestTrialBalanceForParty(FrappeTestCase):
    def setUp(self):
        # Create test company
        self.company = create_company(company_name="TB - TPC")
        self.create_accounts()
        self.create_parties()
        self.create_gl_entries()

    def tearDown(self):
        frappe.db.rollback()

    def create_accounts(self):
        company = self.company

        # Create parent groups if they don't exist
        parent_groups = [
            {"account_name": "Accounts Receivable - TB - TPC - Parent", "account_type": "Receivable", "is_group": 1},
            {"account_name": "Sales - TB - TPC - Parent", "account_type": "Income Account", "is_group": 1},
        ]

        for grp in parent_groups:
            if not frappe.db.exists("Account", {"account_name": grp["account_name"], "company": company}):
                frappe.get_doc({
                    "doctype": "Account",
                    "account_name": grp["account_name"],
                    "company": company,
                    "is_group": grp["is_group"],
                    "account_type": grp["account_type"],
                    "root_type": "Asset",
                    "parent_account": None,
                }).insert(ignore_if_duplicate=True)

        # Create child accounts
        child_accounts = [
            {
                "account_name": "Accounts Receivable - TB - TPC",
                "company": company,
                "is_group": 0,
                "account_type": "Receivable",
                "parent_account": "Accounts Receivable - TB - TPC - Parent",
            },
            {
                "account_name": "Sales - TB - TPC",
                "company": company,
                "is_group": 0,
                "account_type": "Income Account",
                "parent_account": "Sales - TB - TPC - Parent",
            },
        ]

        for acc in child_accounts:
            if not frappe.db.exists("Account", {"account_name": acc["account_name"], "company": company}):
                frappe.get_doc({
                    "doctype": "Account",
                    **acc
                }).insert(ignore_if_duplicate=True)

    def create_parties(self):
        """Create Customer, Supplier, Employee, Shareholder"""
        parties = [
            ("Customer", "CUST-001", "Customer One"),
            ("Supplier", "SUP-001", "Supplier One"),
            ("Employee", "EMP-001", "Employee One"),
            ("Shareholder", "SH-001", "Shareholder One")
        ]
        for doctype, name, title in parties:
            if not frappe.db.exists(doctype, name):
                frappe.get_doc({
                    "doctype": doctype,
                    "name": name if doctype != "Shareholder" else None,
                    "customer_name": title if doctype=="Customer" else None,
                    "supplier_name": title if doctype=="Supplier" else None,
                    "employee_name": title if doctype=="Employee" else None,
                    "title": title if doctype=="Shareholder" else None
                }).insert()

    def create_gl_entries(self):
        """Create sample GL entries for testing"""
        entries = [
            {"party": "CUST-001", "party_type": "Customer", "account": "Test Receivable", "debit": 1000, "credit": 200, "posting_date": "2025-01-01", "is_opening": "Yes"},
            {"party": "CUST-001", "party_type": "Customer", "account": "Test Receivable", "debit": 500, "credit": 300, "posting_date": "2025-06-01", "is_opening": "No"},
            {"party": "SUP-001", "party_type": "Supplier", "account": "Test Payable", "debit": 0, "credit": 500, "posting_date": "2025-03-01", "is_opening": "Yes"},
            {"party": "EMP-001", "party_type": "Employee", "account": "Test Receivable", "debit": 300, "credit": 0, "posting_date": "2025-02-01", "is_opening": "Yes"},
            {"party": "EMP-001", "party_type": "Employee", "account": "Test Receivable", "debit": 200, "credit": 100, "posting_date": "2025-05-01", "is_opening": "No"},
            {"party": "SH-001", "party_type": "Shareholder", "account": "Test Receivable", "debit": 0, "credit": 500, "posting_date": "2025-04-01", "is_opening": "Yes"},
        ]
        for gl in entries:
            frappe.get_doc({
                "doctype": "GL Entry",
                "company": self.company,
                "account": gl["account"],
                "debit": gl["debit"],
                "credit": gl["credit"],
                "party": gl["party"],
                "party_type": gl["party_type"],
                "posting_date": gl["posting_date"],
                "is_opening": gl["is_opening"],
                "is_cancelled": 0
            }).insert()

    def test_execute_returns_columns_and_data(self):
        filters = frappe._dict({
            "company": self.company,
            "party_type": "Customer",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "show_zero_values": 1
        })
        columns, data = execute(filters)
        self.assertTrue(any(col["fieldname"] == "party_name" for col in columns))
        self.assertTrue(len(data) > 0)

    def test_toggle_debit_credit_logic(self):
        debit, credit = toggle_debit_credit(1000, 200)
        self.assertEqual(debit, 800)
        self.assertEqual(credit, 0)

        debit, credit = toggle_debit_credit(200, 500)
        self.assertEqual(debit, 0)
        self.assertEqual(credit, 300)

    def test_is_party_name_visible_logic(self):
        # Customer Naming Series
        frappe.db.set_single_value("Selling Settings", "cust_master_name", "Naming Series")
        self.assertTrue(is_party_name_visible(frappe._dict({"party_type": "Customer"})))

        # Supplier Naming Series
        frappe.db.set_single_value("Buying Settings", "supp_master_name", "Naming Series")
        self.assertTrue(is_party_name_visible(frappe._dict({"party_type": "Supplier"})))

        # Employee & Shareholder always visible
        self.assertTrue(is_party_name_visible(frappe._dict({"party_type": "Employee"})))
        self.assertTrue(is_party_name_visible(frappe._dict({"party_type": "Shareholder"})))

    def test_get_data_with_filters(self):
        from erpnext.accounts.report.trial_balance_for_party.trial_balance_for_party import get_data
        filters = frappe._dict({
            "company": self.company,
            "party_type": "Customer",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "show_zero_values": 1
        })
        data = get_data(filters, show_party_name=True)
        self.assertTrue(any(row.get("party_name") == "Customer One" for row in data))

    def test_total_row_added(self):
        from erpnext.accounts.report.trial_balance_for_party.trial_balance_for_party import get_data
        filters = frappe._dict({
            "company": self.company,
            "party_type": "Customer",
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
            "show_zero_values": 1
        })
        data = get_data(filters, show_party_name=True)
        total_row = data[-1]
        self.assertIn("Totals", total_row.get("party", ""))

    def test_supplier_and_employee_report(self):
        from erpnext.accounts.report.trial_balance_for_party.trial_balance_for_party import get_data
        for party_type in ["Supplier", "Employee", "Shareholder"]:
            filters = frappe._dict({
                "company": self.company,
                "party_type": party_type,
                "from_date": "2025-01-01",
                "to_date": "2025-12-31",
                "show_zero_values": 1
            })
            data = get_data(filters, show_party_name=True)
            self.assertTrue(len(data) > 0)

def create_company(**args):
    args = frappe._dict(args)
    company_name = args.company_name or "Trial Balance Company"
    if not frappe.db.exists("Company", company_name):
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": company_name,
            "country": args.country or "India",
            "default_currency": args.currency or "INR",
        }).insert(ignore_if_duplicate=True)
        return company.name
    else:
        return frappe.db.get_value("Company", company_name, "name")