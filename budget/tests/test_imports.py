from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from budget import imports
from budget.models import (
    Account, AccountShare, Budget, BudgetAlert, Category, ImportBatch, Membership, Rule, Transaction, TransactionAnnotation, Workspace,
)

MAPPING = {"header": True, "date_col": 0, "description_col": 1, "amount_col": 2, "credit_col": None, "sign": "negative",
           "incoming": "income", "category_col": None}
CSV = "Date,Description,Amount\n05/01/2026,COFFEE SHOP,-4.50\n05/02/2026,PAYROLL,1000.00\n"


def parse(text, **mapping):
    return imports.parse(imports.rows(text), {**MAPPING, **mapping})


class ParseTests(TestCase):
    def test_amounts_dates_and_zero_rows(self):
        text = "Date,Description,Amount\n2026-05-01 00:00:00,A,\"$1,234.56\"\n2026-05-02,B,(12.00)\n2026-05-03,C,0.00\n\n2026-05-04,D,-4.50\n"
        parsed, errors, skipped = parse(text, sign="positive")
        self.assertEqual(errors, [])
        self.assertEqual(skipped, 1)
        self.assertEqual([(p["source_row"], p["posted_on"], p["amount_cents"], p["classification"]) for p in parsed], [
            (2, date(2026, 5, 1), 123456, "expense"), (3, date(2026, 5, 2), 1200, "income"), (6, date(2026, 5, 4), 450, "income")])

    def test_bad_rows_are_named(self):
        text = "Date,Description,Amount\n05/01/2026,A,1.005\n05/02/2026,B,NaN\n13/45/2026,C,1.00\n05/03/2026,D,abc\n"
        _, errors, _ = parse(text)
        self.assertEqual(len(errors), 4)
        for row, error in zip((2, 3, 4, 5), errors):
            self.assertTrue(error.startswith(f"Row {row}:"), error)

    def test_two_columns_no_header_and_incoming_type(self):
        text = "05/01/2026,CARD PAYMENT,,500.00\n05/02/2026,GROCER,-25.10,\n05/03/2026,BOTH,1.00,2.00\n"
        parsed, errors, _ = parse(text, header=False, credit_col=3, incoming="transfer")
        self.assertEqual([(p["description"], p["amount_cents"], p["classification"]) for p in parsed[:2]],
                         [("CARD PAYMENT", 50000, "transfer"), ("GROCER", 2510, "expense")])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Row 3:"))

    def test_guess_picks_columns_and_majority_sign(self):
        header = ["Transaction Date", "Posted Date", "Card No.", "Description", "Category", "Debit", "Credit"]
        guessed = imports.guess(header, [["05/01/2026", "05/02/2026", "1", "A", "Dining", "4.50", ""]])
        self.assertEqual((guessed["date_col"], guessed["description_col"], guessed["amount_col"], guessed["credit_col"], guessed["category_col"]),
                         (0, 3, 5, 6, 4))
        self.assertEqual(imports.guess(["Date", "Description", "Amount"], [["x", "y", "4.50"], ["x", "y", "5"], ["x", "y", "-100"]])["sign"], "positive")


class ImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "eve")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Checking")
        AccountShare.objects.create(account=cls.card, workspace=cls.group)

    def setUp(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        self.base = f"/workspaces/{self.group.pk}/accounts/{self.card.pk}/import/"

    def upload(self, text=CSV, name="may.csv"):
        return self.client.post(self.base, {"file": SimpleUploadedFile(name, text.encode(), content_type="text/csv")})

    def commit(self, text=CSV, keep=(), action="import", **mapping):
        response = self.upload(text)
        self.assertEqual(response.status_code, 302, response.content[:500])
        values = {**MAPPING, **mapping}
        data = {k: ("" if v is None else v) for k, v in values.items() if k != "header"}
        if values["header"]:
            data["header"] = "on"
        return self.client.post(response["Location"], {**data, "keep": list(keep), "action": action})

    def test_import_creates_read_only_rows_once(self):
        self.assertEqual(self.commit().status_code, 302)
        rows = list(Transaction.objects.filter(account=self.card).order_by("posted_on"))
        self.assertEqual([(r.description, r.amount_cents, r.classification, r.source_row) for r in rows],
                         [("COFFEE SHOP", 450, "expense", 2), ("PAYROLL", 100000, "income", 3)])
        batch = ImportBatch.objects.get()
        self.assertEqual((batch.status, batch.row_count, batch.content), ("done", 2, ""))
        self.assertContains(self.upload(), "already imported", status_code=400)
        self.assertEqual(Transaction.objects.count(), 2)
        # The original entry is the bank's: amount/date/description can't change, the type can.
        url = f"/workspaces/{self.group.pk}/accounts/{self.card.pk}/transactions/{rows[0].pk}/"
        self.client.post(url, {"posted_on": "2020-01-01", "amount": "999.00", "description": "X", "classification": "transfer"})
        rows[0].refresh_from_db()
        self.assertEqual((rows[0].amount_cents, rows[0].posted_on, rows[0].description, rows[0].classification), (450, date(2026, 5, 1), "COFFEE SHOP", "transfer"))

    def test_one_bad_row_saves_nothing(self):
        response = self.commit(CSV + "05/03/2026,BAD,1.005\n")
        self.assertContains(response, "Row 4:", status_code=400)
        self.assertFalse(Transaction.objects.exists())
        self.assertFalse(ImportBatch.objects.filter(status="done").exists())

    def test_committing_one_preview_twice_imports_once(self):
        response = self.upload()
        data = {k: ("" if v is None else v) for k, v in MAPPING.items() if k != "header"}
        for _ in range(2):
            self.client.post(response["Location"], {**data, "header": "on", "action": "import"})
        self.assertEqual(Transaction.objects.count(), 2)

    def test_identical_purchases_survive_and_overlap_is_reviewed(self):
        twice = "Date,Description,Amount\n05/01/2026,COFFEE,-4.50\n05/01/2026,COFFEE,-4.50\n"
        self.commit(twice)
        self.assertEqual(Transaction.objects.count(), 2)
        overlapping = twice + "05/01/2026,COFFEE,-4.50\n05/02/2026,BAGEL,-3.00\n"
        response = self.upload(overlapping)
        preview = self.client.get(response["Location"])
        self.assertContains(preview, "2 look already imported")
        self.commit(overlapping)  # the new file's first two coffees match the two already there
        self.assertEqual(Transaction.objects.filter(description="COFFEE").count(), 3)
        self.assertEqual(Transaction.objects.filter(description="BAGEL").count(), 1)

    def test_ticking_an_overlap_imports_it(self):
        Transaction.objects.create(account=self.card, posted_on=date(2026, 5, 1), amount_cents=450, description="coffee shop")
        self.commit(keep=[2])
        self.assertEqual(Transaction.objects.filter(amount_cents=450).count(), 2)

    @mock.patch("django.utils.timezone.localdate", return_value=date(2026, 5, 20))  # alerts cover the current period only
    def test_category_column_rules_and_budgets(self, _):
        dining = Category.objects.get(workspace=self.group, name="Dining")
        Rule.objects.create(workspace=self.personal, pattern="coffee", category=Category.objects.get(workspace=self.personal, name="Dining"))
        Budget.objects.create(workspace=self.group, category=dining, limit_cents=100)
        text = "Date,Description,Amount,Category\n05/01/2026,COFFEE SHOP,-4.50,dining\n05/02/2026,ODD,-1.00,Food & Drink\n"
        self.commit(text, category_col=3)
        coffee, odd = Transaction.objects.order_by("posted_on")
        group_note = TransactionAnnotation.objects.get(transaction=coffee, workspace=self.group)
        self.assertEqual((group_note.category, group_note.category_source), (dining, "manual"))
        self.assertEqual(TransactionAnnotation.objects.get(transaction=coffee, workspace=self.personal).category_source, "rule")
        self.assertFalse(TransactionAnnotation.objects.filter(transaction=odd, workspace=self.group).exists())
        self.assertTrue(BudgetAlert.objects.filter(recipient=self.bob, silent=False).exists())

    def test_only_the_owner_can_import(self):
        self.upload()
        batch = ImportBatch.objects.get()
        for user in (self.bob, self.eve):
            self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
            for url in (self.base, f"{self.base}{batch.pk}/"):
                self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(f"{self.base}{batch.pk}/undo/").status_code, 404)
        self.assertEqual(self.client.get(f"{self.base}{batch.pk}/undo/").status_code, 405)

    def test_undo_removes_the_rows(self):
        self.commit()
        revision = Workspace.objects.get(pk=self.group.pk).data_revision
        batch = ImportBatch.objects.get()
        self.assertEqual(self.client.post(f"{self.base}{batch.pk}/undo/").status_code, 302)
        self.assertFalse(Transaction.objects.exists())
        self.assertFalse(ImportBatch.objects.exists())
        self.assertGreater(Workspace.objects.get(pk=self.group.pk).data_revision, revision)
        self.assertEqual(self.upload().status_code, 302)  # the same file may be imported again after an undo

    def test_upload_limits(self):
        self.assertContains(self.upload("Date,Description,Amount\n"), "no rows", status_code=400)
        self.assertContains(self.upload("x" * (1024 * 1024 + 1)), "1 MB", status_code=400)
        self.assertContains(self.upload("Date,Description,Amount\n" + "05/01/2026,A,1\n" * 5001), "5,000", status_code=400)
