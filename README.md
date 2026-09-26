# Bev: Chain Audit Tool

A field tool for verifying that chain stores show the planned **price, shelf placement and display** for each brand (ZOA, Henry's Soda, Fever-Tree, Naked Life), with visit notes that reps can recall on the next visit.

| File | What it is |
|---|---|
| `Chain_Audit_Tool.xlsx` | The workbook: Dashboard, Chain Program (hot sheet), Promo Calendar, Visit Log, Store History, Data Review, Lists. Open the README tab first. |
| `docs/RECOMMENDATIONS.md` | Platform research, design changes and roll-out plan (Excel plan + Microsoft Lists visit log, then Power Apps) |
| `docs/visit_log_list_schema.csv` | Column spec for creating the Visit Log as a Microsoft List |
| `tools/program_data.py` | Seed data merged from the Non-Alc Chain Document (9/8/2026) and the HW Soda hot sheet (8/25/2025) |
| `tools/build_workbook.py` | Regenerates the workbook: `pip install openpyxl && python tools/build_workbook.py` |

Programs marked **Confirm for 2026** still use 2025 hot-sheet pricing. See the Data Review tab.
