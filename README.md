# Bev: Chain Audit

A tool for verifying that chain stores show the planned **price, shelf placement and display** for each brand (ZOA, Henry's Soda, Fever-Tree, Naked Life). Reps log store visits with notes and photos, discrepancies become follow-ups, and those follow-ups come back up on the next visit.

## Web app (Docker)

A self-hosted, phone-friendly web app. **See [docs/DEPLOY.md](docs/DEPLOY.md) to install it.**

- **Plan:** 42 brand × account programs and 81 dated promo windows, seeded from the Non-Alc Chain Document (9/8/2026) and the HW Soda hot sheet (8/25/2025). The expected shelf price is calculated for any day.
- **Store visits:**
  - GPS check-in, flagged when it's far from the store
  - per-program checks: observed price vs. plan (Match / Over / Under), shelf tag, planogram, in-stock and display
  - notes and photos
  - the expected price is frozen into each audit record
- **Follow-ups:** raised automatically from discrepancies, each with an owner, due date and a status history. They're shown on the store page and on the next visit.
- **Wins:** new displays, cold placements (cooler and cold vault doors), new SKUs, secondary placements and ads, each with photos, cases and facings. Display and placement wins are re-checked on later visits ("Still up / Gone").
- **Tasks:** managers assign work to reps.
- **Dashboard:** visits, price match rate, open and overdue follow-ups by rep and brand, and stores not visited recently.
- **Roles:** Manager (edits plan, manages users), Rep (views plan, edits only their own visits), Viewer (read-only).
- **Data:** full Excel export, plan import from `Chain_Audit_Tool.xlsx`, store list import, and nightly backups.

**Design:** the "Cellar & Ivory" look.
- Light theme for reps in stores; dark theme for managers. Anyone can switch from their menu.
- Company name, logo, colors, and brand, product and retailer logos are set under **Branding**. Colors are contrast-checked automatically.
- Styling uses Tailwind CSS. The compiled `app/static/app.css` is committed, so Docker builds don't need Node.
- After changing templates, rebuild the CSS with `npm install && npm run build:css`.

To run it locally for development:

```bash
pip install -r requirements-dev.txt
DATA_DIR=./data SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") COOKIE_SECURE=false \
  ADMIN_USERNAME=manager ADMIN_PASSWORD='Change-Me-2026' uvicorn app.asgi:app --reload
python -m pytest -q
```

## Other files

| File | What it is |
|---|---|
| `Chain_Audit_Tool.xlsx` | The Excel version of the tool; the app can import it |
| `docs/RECOMMENDATIONS.md` | Platform research and design rationale |
| `docs/visit_log_list_schema.csv` | Microsoft Lists column spec (the alternative M365 route) |
| `tools/program_data.py` | Seed data used by both the workbook and the app |
| `tools/build_workbook.py` | Regenerates the workbook |
| `tools/extract_logos.py` | Re-extracts brand, product and retailer logos from the two source documents |

Programs marked **Confirm for 2026** still use 2025 hot-sheet pricing. See **Data review** in the app.
