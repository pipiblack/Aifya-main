"""One-shot script: add missing billing + insurance i18n keys identified
by the post-audit smoke test. Run from apps/web."""
import json
from collections import OrderedDict
from pathlib import Path

EN = {
    "billing": {
        "customerInvoicingTitle": "Customer Invoicing",
        "customerInvoicingHelp": "Patient and payer invoices, payments, and statements.",
        "supplierInvoicingTitle": "Supplier Invoicing",
        "supplierInvoicingHelp": "Vendor bills, expense invoices, withholding tax tracking.",
        "viewInvoices": "View Invoices",
        "insuranceClaims": "Insurance Claims",
        "manageSuppliers": "Manage Suppliers",
        "newSupplier": "New Supplier",
        "newSupplierInvoice": "New Supplier Invoice",
        "new": "New",
        "suppliers": "Suppliers",
        "supplierInvoices": "Supplier Invoices",
        "supplier": "Supplier",
        "selectSupplier": "Select supplier",
        "searchSuppliers": "Search suppliers by name, KRA PIN or phone",
        "invoiceDate": "Invoice Date",
        "dueDate": "Due Date",
        "vatAmount": "VAT",
        "whtAmount": "WHT",
        "account": "Account",
        "addLine": "Add Line",
        "approved": "Approved",
        "received": "Received",
    },
    "insurance": {
        "claimFlowActions": "ClaimFlow Actions",
    },
}

SW = {
    "billing": {
        "customerInvoicingTitle": "Bili za Wateja",
        "customerInvoicingHelp": "Bili za wagonjwa, malipo na taarifa.",
        "supplierInvoicingTitle": "Bili za Wasambazaji",
        "supplierInvoicingHelp": "Bili za wauzaji, gharama, na ufuatiliaji wa kodi.",
        "viewInvoices": "Angalia Bili",
        "insuranceClaims": "Madai ya Bima",
        "manageSuppliers": "Simamia Wasambazaji",
        "newSupplier": "Msambazaji Mpya",
        "newSupplierInvoice": "Bili Mpya ya Msambazaji",
        "new": "Mpya",
        "suppliers": "Wasambazaji",
        "supplierInvoices": "Bili za Wasambazaji",
        "supplier": "Msambazaji",
        "selectSupplier": "Chagua msambazaji",
        "searchSuppliers": "Tafuta wasambazaji kwa jina, KRA PIN au simu",
        "invoiceDate": "Tarehe ya Bili",
        "dueDate": "Tarehe ya Kulipa",
        "vatAmount": "VAT",
        "whtAmount": "WHT",
        "account": "Akaunti",
        "addLine": "Ongeza Mstari",
        "approved": "Imeidhinishwa",
        "received": "Imepokelewa",
    },
    "insurance": {
        "claimFlowActions": "Vitendo vya ClaimFlow",
    },
}


def merge(target: dict, source: dict) -> None:
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            merge(target[k], v)
        else:
            if k not in target:
                target[k] = v


here = Path(__file__).resolve().parent.parent
for rel, patch in [("src/messages/en.json", EN), ("src/messages/sw.json", SW)]:
    path = here / rel
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    merge(data, patch)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Updated {rel}")
