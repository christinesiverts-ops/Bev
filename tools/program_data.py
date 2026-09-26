"""Seed data for the Chain Audit Tool.

Sources
-------
NA  = "Non-Alc Chain Document" dated September 8, 2026 (current source of truth)
HW  = "HW Soda Chain Activity - Pacific Region as of 8-25-25" hot sheet (2025 data,
      used for structure and for accounts missing from the Non-Alc document)

Every program row carries its source and a data status so the field can tell
current 2026 direction apart from 2025 carry-forward that still needs confirming.
"""
from datetime import date

NA = "Non-Alc Chain 9/8/26"
HW = "HW Hot Sheet 8/25/25"
BOTH = "Non-Alc 9/8/26 + HW 8/25/25"

CURRENT = "Current (2026)"
CONFIRM = "Confirm for 2026"

HENRYS_4 = "Root Beer, Black Cherry Cream, Orange Cream, Vanilla Cream"
HENRYS_4_BCC_SELECT = "Root Beer, Orange Cream, Vanilla Cream; Black Cherry Cream select stores"
BACKSTOCK = "1 case of each flavor backstock"
GAPS = "Priority to close gaps and hit 90%+ re-service rates."
DISPLAY_SELL = "Sell in displays at store level to support promotional pricing."

# Each program: one row per brand x account.
# fields: brand, chain, account, market, outlets, total, skus, case_rec,
#         shelf, case_cost, srp_text, base, timing, priority, owner, source, status
PROGRAMS = [
    # ---------------- ZOA (Non-Alc 9/8/26) ----------------
    dict(brand="ZOA", chain="Albertsons/Safeway", account="Mountain West North", market="ID / MT / WY",
         skus="ZOA core SKUs", shelf="Promo display where authorized", srp_text="Promo 2 for $4",
         timing="Aug-Dec 2026", priority="Promote ZOA at 2 for $4.", source=NA, status=CURRENT),
    dict(brand="ZOA", chain="Albertsons/Safeway", account="Mountain West South", market="CO / WY",
         skus="ZOA core SKUs", shelf="Promo display where authorized", srp_text="Promo 2 for $4",
         timing="Aug-Dec 2026", priority="Promote ZOA at 2 for $4.", source=NA, status=CURRENT),
    dict(brand="ZOA", chain="Albertsons/Safeway", account="Southwest Division (SWD)", market="AZ / LV / NM",
         skus="ZOA core SKUs", shelf="Promo display where authorized", srp_text="Promo 2 for $4",
         timing="Aug-Dec 2026", priority="Promote ZOA at 2 for $4.", source=NA, status=CURRENT),
    dict(brand="ZOA", chain="Smart & Final", account="Smart & Final", market="Chain-wide",
         skus="12-pack; Frosted Grape and Tropical Punch singles",
         shelf="Store-level display (authorization required); shelf tags",
         srp_text="12pk $17.99 (to 9/22); singles 2 for $3 (9/23-11/3)", timing="8/26-11/3/2026",
         priority="Secure shelf tags and store-level display authorization.", source=NA, status=CURRENT),
    dict(brand="ZOA", chain="Yoke's Fresh Market", account="Yoke's Fresh Market", market="W. WA",
         skus="ZOA core SKUs", shelf="Per store planogram - confirm", case_cost="$15.30 case cost",
         srp_text="Retail TBD", timing="8/2-10/3/2026", priority="$15.30 case cost. Retail TBD.",
         source=NA, status=CURRENT),

    # ---------------- HENRY'S SODA (Non-Alc 9/8/26, merged with HW where the account overlaps) ----------------
    dict(brand="Henry's", chain="Albertsons/Safeway", account="Mountain West North", market="PNW / ID / UT / WY",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         case_cost="$23 case (transition)", srp_text="SRP $7.99 (2025 ABSCO)", base=7.99,
         timing="Effective 9/7/2026",
         priority="Reflect approved PTRs in distributor price books. Sell in displays. Transition to $23 case pricing.",
         source=BOTH, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="Mountain West South", market="CO / WY",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         case_cost="New pricing structure", srp_text="SRP $7.99 (2025 ABSCO)", base=7.99,
         timing="Effective 9/7/2026",
         priority="Confirm distributor price book accuracy. Sell in displays. Execute the new pricing structure.",
         source=BOTH, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="Southwest Division (SWD) #17", market="AZ / LV / NM",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         srp_text="EDLP $7.99", base=7.99, timing="Ongoing",
         priority="Reflect approved PTRs, actively sell displays and maintain $7.99 EDLP.",
         source=BOTH, status=CURRENT),
    dict(brand="Henry's", chain="BevMo!", account="BevMo!", market="Non-alcohol section",
         outlets="MU-AK ID OR WA: 5; MU-AZ NM LAS VEGAS: 5; MU-CA HI NORTH NV: 99", total=109,
         skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Non-alcohol section",
         srp_text="SRP $8.99; promo TBD", base=8.99, timing="Ongoing",
         priority="Confirm all four Henry's SKUs are on shelf. Support reorders and in-stock conditions. "
                  "Promo pricing TBD (Bob and Lexi setting up price promotions, per 2025 hot sheet).",
         source=BOTH, status=CURRENT),
    dict(brand="Henry's", chain="Raley's", account="Raley's", market="NorCal (+ AZ per 2025 hot sheet)",
         outlets="MU-CA HI NORTH NV: 115; MU-AZ NM LAS VEGAS: 44", total=159,
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         case_cost="$23 frontline; $3.45 O/I; $19.55 net; $1.00/CE scan",
         srp_text="SRP $6.49 (2025)", base=6.49, timing="2H 2026 - four promo windows (dates not listed)",
         priority="$23 frontline. $3.45 O/I, $19.55 net and $1.00/CE scan in four promotional windows. " + GAPS,
         source=BOTH, status=CONFIRM),
    dict(brand="Henry's", chain="Yoke's Fresh Market", account="Yoke's Fresh Market", market="W. WA",
         outlets="MU-AK ID OR WA: 17", total=17, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         case_cost="$19.55 case cost (6/1-9/8/2026)", srp_text="SRP $6.49 (2025); retail TBD", base=6.49,
         timing="6/1-9/8/2026", priority="$19.55 case cost. Retail TBD. " + GAPS + " " + DISPLAY_SELL,
         source=BOTH, status=CONFIRM),
    dict(brand="Henry's", chain="WinCo Foods", account="WinCo Foods", market="PNW / NorCal / Utah",
         outlets="MU-AK ID OR WA: 59; MU-AZ NM LAS VEGAS: 10; MU-CA HI NORTH NV: 40", total=109,
         skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Shelf set + promo displays",
         case_cost="$23 frontline; $19.55 Tier 2; $18.40 Tier 3", srp_text="SRP $6.49 (2025)", base=6.49,
         timing="Jun-Dec 2026 (see Promo Calendar)",
         priority="$23 frontline effective 6/1. $19.55 Tier 2 and $18.40 Tier 3 promotional/display pricing. " + GAPS,
         source=BOTH, status=CONFIRM),

    # ---------------- HENRY'S: accounts only on the HW hot sheet (missing from Non-Alc) ----------------
    dict(brand="Henry's", chain="Save Mart / Lucky", account="Save Mart / Lucky", market="NorCal / N. NV",
         outlets="MU-CA HI NORTH NV: 188", total=188, skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK,
         shelf="Shelf set + displays", srp_text="SRP $6.49", base=6.49, timing="2025: 6/1-9/6, 10/5-1/3",
         priority=GAPS + " " + DISPLAY_SELL, source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="SFWY Portland Div. #19", market="OR / SW WA",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelves merchandised; backstock",
         srp_text="SRP $7.99", base=7.99, timing="2025: 6/1-9/6, 10/5-1/3",
         priority="Ensure shelves are merchandised. Sufficient inventory in backstock.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="Haggen Div. #24", market="W. WA",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelves merchandised; backstock",
         srp_text="SRP $7.99", base=7.99, timing="2025: 6/1-9/6, 10/5-1/3",
         priority="Ensure shelves are merchandised. Sufficient inventory in backstock.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="NorCal Div. #25 (incl. HI)", market="NorCal / HI",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelves merchandised; backstock",
         srp_text="SRP $7.99 (HI $8.99)", base=7.99, timing="2025: 6/1-9/6, 10/5-1/3",
         priority="Ensure shelves are merchandised. Sufficient inventory in backstock. Hawaii SRP $8.99 / TPR $7.99.",
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="Seattle Div. #27", market="WA / AK",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelves merchandised; backstock",
         srp_text="SRP $7.99", base=7.99, timing="2025: 6/1-9/6, 10/5-1/3",
         priority="Ensure shelves are merchandised. Sufficient inventory in backstock.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="SoCal Div. #29", market="SoCal",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelves merchandised; backstock",
         srp_text="SRP $7.99", base=7.99, timing="2025: 6/1-9/6, 10/5-1/3",
         priority="Ensure shelves are merchandised. Sufficient inventory in backstock.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Albertsons/Safeway", account="Intermountain Div. #30", market="ID / MT / UT / NV",
         skus=HENRYS_4_BCC_SELECT, case_rec=BACKSTOCK, shelf="Shelves merchandised; backstock",
         srp_text="SRP $7.99", base=7.99, timing="2025: 6/1-9/6, 10/5-1/3",
         priority="Ensure shelves are merchandised. Sufficient inventory in backstock. "
                  "Confirm whether this division is now covered by Mountain West North.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Bi-Mart", account="Bi-Mart", market="OR / WA / ID",
         outlets="MU-AK ID OR WA: 52", total=52, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Per store planogram - confirm",
         srp_text="SRP $6.49", base=6.49, timing="2025: 9/28-1/3",
         priority="Summer and fall price promotions accepted.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Bashas'", account="Bashas'", market="AZ",
         outlets="MU-AZ NM LAS VEGAS: 43", total=43, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         srp_text="SRP $6.49", base=6.49, timing="2025: 5/18-9/6, 9/29-1/3",
         priority=GAPS + " " + DISPLAY_SELL, source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="C&K Market", account="C&K / Ray's Food Place / Shop Smart", market="OR / N. CA",
         outlets="MU-AK ID OR WA: 26; MU-CA HI NORTH NV: 13", total=39, skus=HENRYS_4, case_rec=BACKSTOCK,
         shelf="Shelf set + displays", srp_text="SRP $6.49", base=6.49,
         timing="2025: 10/8-11/4, 11/5-12/2, 12/3-12/30", priority=GAPS + " " + DISPLAY_SELL, source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Kroger", account="Fred Meyer (Div. 701)", market="PNW",
         outlets="Fred Meyer: 95", total=95, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Per store planogram - confirm",
         srp_text="SRP $7.99", base=7.99, timing="2025: 10/15-1/3",
         priority="Kroger Mega Buy 5 Save $5 ($1 off each when buying 5 participating items), 2025 timing P5W4-P6W2.",
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Kroger", account="Fry's (Div. 660)", market="AZ",
         outlets="Fry's: 126", total=126, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Per store planogram - confirm",
         srp_text="SRP $7.99", base=7.99, timing="2025: 10/15-1/3",
         priority="Kroger Mega Buy 5 Save $5, 2025 timing P5W4-P6W2.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Kroger", account="QFC (Div. 705)", market="W. WA / OR",
         outlets="QFC: 58", total=58, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Per store planogram - confirm",
         srp_text="SRP $7.99", base=7.99, timing="2025: 10/15-1/3",
         priority="Kroger Mega Buy 5 Save $5, 2025 timing P5W4-P6W2.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Kroger", account="Ralphs SoCal (Div. 703)", market="SoCal",
         outlets="Ralphs: 153", total=153, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Per store planogram - confirm",
         srp_text="SRP $7.99", base=7.99, timing="2025: 10/15-1/3",
         priority="Kroger Mega Buy 5 Save $5, 2025 timing P5W4-P6W2.", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Kroger", account="Smith's", market="UT / NV",
         outlets="Smith's: 67", total=67, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Per store planogram - confirm",
         srp_text="SRP $7.99", base=7.99, timing="2025: 10/15-1/3",
         priority="Kroger Mega Buy 5 Save $5, 2025 timing P5W4-P6W2. King Soopers also listed as a division (no outlet count).",
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Nugget Markets", account="Nugget Markets", market="NorCal",
         outlets="MU-CA HI NORTH NV: 15", total=15, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         srp_text="SRP $6.49", base=6.49, timing="2025: 9/29-1/3", priority=GAPS + " " + DISPLAY_SELL,
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Stater Bros.", account="Stater Bros.", market="SoCal",
         outlets="MU-CA HI NORTH NV: 163", total=163,
         skus=HENRYS_4 + " (54 stores carry 3 - no Orange Cream)", case_rec=BACKSTOCK,
         shelf="Shelf set + displays for promo and key holidays", srp_text="SRP $6.99", base=6.99,
         timing="2025: 9/29-1/3", priority=GAPS + " " + DISPLAY_SELL + " Close Orange Cream gap in 54 stores.",
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Plaid Pantry", account="Plaid Pantry", market="OR / WA",
         outlets="MU-AK ID OR WA: 74", total=74, skus=HENRYS_4 + " (singles)", case_rec=BACKSTOCK,
         shelf="Cold vault / single-serve set - confirm", srp_text="SRP $1.50 single", base=1.50,
         timing="2025: 10/5-11/1, 11/2-11/29, 11/30-1/3", priority=GAPS, source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Metropolitan Market", account="Metropolitan Market", market="Seattle / Tacoma",
         outlets="MU-AK ID OR WA: 10", total=10, skus="Root Beer, Orange Cream, Vanilla Cream (no Black Cherry Cream)",
         case_rec=BACKSTOCK, shelf="Per store planogram - confirm", srp_text="SRP $6.49", base=6.49,
         timing="2025: 9/28-1/3", priority="Account lead: Chris Armstrong.", owner="Chris Armstrong",
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Northwest Grocers (NWG)", account="Northwest Grocers (NWG)", market="PNW",
         outlets="MU-AK ID OR WA: (count blank)", skus=HENRYS_4, case_rec=BACKSTOCK,
         shelf="Per store planogram - confirm", srp_text="SRP $7.99", base=7.99, timing="2025: 9/29-1/3",
         priority="Account lead: Chris Armstrong. Outlet count missing.", owner="Chris Armstrong",
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Town & Country Markets", account="Town & Country Markets", market="Puget Sound",
         outlets="MU-AK ID OR WA: 6", total=6, skus=HENRYS_4, case_rec=BACKSTOCK,
         shelf="Per store planogram - confirm", srp_text="SRP $6.49", base=6.49, timing="2025: 9/28-1/3",
         priority="Account lead: Chris Armstrong.", owner="Chris Armstrong", source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Harvest Foods", account="Harvest Foods", market="ID / WA / OR",
         outlets="MU-AK ID OR WA: 22", total=22, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         srp_text="SRP $6.49", base=6.49, timing="2025: 11/29-1/3",
         priority="Henry's continued in the July and August savings guides (2025). " + DISPLAY_SELL,
         source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Ridley's Family Markets", account="Ridley's Family Markets", market="ID / UT / WY / NV",
         outlets="MU-AK ID OR WA: 13; MU-CA HI NORTH NV: 4", total=17, skus=HENRYS_4, case_rec=BACKSTOCK,
         shelf="Shelf set + displays", srp_text="SRP $6.49", base=6.49, timing="2025: 11/30-1/3",
         priority=GAPS + " " + DISPLAY_SELL, source=HW, status=CONFIRM),
    dict(brand="Henry's", chain="Rosauers", account="Rosauers", market="E. WA / N. ID / MT",
         outlets="MU-AK ID OR WA: 19", total=19, skus=HENRYS_4, case_rec=BACKSTOCK, shelf="Shelf set + displays",
         srp_text="SRP $6.49", base=6.49, timing="2025: 5/19-9/6, 8/30-9/12 (deep), 9/29-1/3",
         priority=GAPS + " " + DISPLAY_SELL, source=HW, status=CONFIRM),

    # ---------------- FEVER-TREE (Non-Alc 9/8/26) ----------------
    dict(brand="Fever-Tree", chain="Albertsons/Safeway", account="Safeway NorCal", market="NorCal",
         skus="Fever-Tree authorized set", shelf="Shelf presence + display opportunities",
         srp_text="Not listed", timing="KEHE-to-DSD transition",
         priority="Support KEHE-to-DSD transition. Protect inventory, shelf presence and merchandising. Pursue display opportunities.",
         source=NA, status=CURRENT),
    dict(brand="Fever-Tree", chain="BevMo!", account="BevMo!", market="Authorized stores",
         skus="~23 SKUs per authorized store", shelf="Fully merchandised mixer set",
         srp_text="Not listed", timing="Ongoing",
         priority="Keep Fever-Tree fully merchandised and maintain approximately 23 SKUs per store where authorized.",
         source=NA, status=CURRENT),
    dict(brand="Fever-Tree", chain="C&K Market", account="C&K / Ray's", market="Oregon",
         skus="Fever-Tree DSD set", shelf="Per store planogram - confirm", srp_text="Not listed", timing="Ongoing",
         priority="Support new DSD distribution and drive incremental distribution opportunities.",
         source=NA, status=CURRENT),
    dict(brand="Fever-Tree", chain="Harmons", account="Harmons", market="Utah",
         skus="4pk, 8pk, 500mL", case_rec="Est. 50 cases per store for display",
         shelf="Ad feature + 4-week endcap; display 3 months (Aug / Nov / Dec)",
         srp_text="TPR: 4pk $4.99, 8pk $5.99, 500mL 2 for $5", timing="Aug / Nov / Dec 2026",
         priority="Display three months. Estimate 50 cases per store. Ad feature + 4-week endcap.",
         source=NA, status=CURRENT),
    dict(brand="Fever-Tree", chain="Kroger", account="Kroger (proposed plan)", market="Kroger divisions",
         skus="Fever-Tree Kroger set", shelf="Merchandising / display per plan",
         srp_text="Promotional scans + digital offers", timing="P10-P13",
         priority="Promotional scans, merchandising/display, digital offers and paid media. "
                  "Detailed proposed plan remains in the source PowerPoint.",
         source=NA, status=CONFIRM),

    # ---------------- NAKED LIFE (Non-Alc 9/8/26) ----------------
    dict(brand="Naked Life", chain="Whole Foods Market", account="WFM September Feature",
         market="DSD: WA, OR, CA, TX | Broadliner: FL; MA/NJ/MD dry stores only",
         skus="Margarita 4pk 12oz cans; Mojito 4pk 12oz cans",
         case_rec="Initial 1-case shelf placement; reorders allowed during feature",
         shelf="Shelf feature; Gouda case stack: CA 1 dry store (Laguna Beach), MA/NJ/MD half of dry stores",
         case_cost="Cost to WFM: $33.03 promo / $38.25 everyday", srp_text="Everyday SRP $10.99; promo $9.49",
         base=10.99, timing="Orders week of 8/24; feature 9/2-10/6/2026 (5 weeks)",
         priority="Execution success = initial order quantity delivered. Confirm promo costing is entered in WFM VIP. "
                  "Support: influencer + media campaign, 50 WFM sampling demos. Items may remain in flex stores after program.",
         source=NA, status=CURRENT),
]


def d(y, m, dd):
    return date(y, m, dd)


def pid(brand, account):
    return f"{brand} | {account}"


# Promo calendar rows: (program id, sku, type, offer, unit_retail, case_cost, start, end, display_req, source)
def _promos():
    rows = []
    add = rows.append

    # ZOA 2026
    for acct in ("Mountain West North", "Mountain West South", "Southwest Division (SWD)"):
        add((pid("ZOA", acct), "All", "TPR", "2 for $4", 2.00, None, d(2026, 8, 1), d(2026, 12, 31), "Y", NA))
    add((pid("ZOA", "Smart & Final"), "12pk", "TPR", "12-pack $17.99", 17.99, None, d(2026, 8, 26), d(2026, 9, 22), "Y", NA))
    add((pid("ZOA", "Smart & Final"), "Singles (Frosted Grape/Tropical Punch)", "TPR", "Singles 2 for $3", 1.50, None,
         d(2026, 9, 23), d(2026, 11, 3), "Y", NA))
    add((pid("ZOA", "Yoke's Fresh Market"), "All", "Case Cost", "$15.30 case cost; retail TBD", None, 15.30,
         d(2026, 8, 2), d(2026, 10, 3), "N", NA))

    # Henry's 2026 case-cost programs
    add((pid("Henry's", "Yoke's Fresh Market"), "All", "Case Cost", "$19.55 case cost; retail TBD", None, 19.55,
         d(2026, 6, 1), d(2026, 9, 8), "N", NA))
    winco = pid("Henry's", "WinCo Foods")
    frontline = [((6, 1), (6, 9)), ((6, 10), (6, 23)), ((7, 22), (8, 4)), ((8, 19), (9, 1)), ((9, 16), (9, 29)),
                 ((9, 30), (10, 13)), ((11, 27), (12, 8))]
    tier2 = [((6, 24), (7, 7)), ((7, 8), (7, 21)), ((8, 5), (8, 18)), ((9, 2), (9, 15)), ((10, 14), (10, 27)),
             ((10, 28), (11, 10)), ((12, 28), (1, 12))]
    tier3 = [((11, 11), (11, 26)), ((12, 9), (12, 27))]

    def span(a, b):
        start = d(2026, *a)
        end = d(2027 if b[0] < a[0] else 2026, *b)
        return start, end

    for a, b in frontline:
        s, e = span(a, b)
        add((winco, "All", "Frontline TPR", "Frontline TPR ($23 frontline)", None, 23.00, s, e, "N", NA))
    for a, b in tier2:
        s, e = span(a, b)
        add((winco, "All", "TPR + Display", "Tier 2 $19.55 TPR + display", None, 19.55, s, e, "Y", NA))
    for a, b in tier3:
        s, e = span(a, b)
        add((winco, "All", "TPR + Display", "Tier 3 $18.40 TPR + display", None, 18.40, s, e, "Y", NA))

    # Fever-Tree Harmons 2026 (months per Non-Alc doc)
    harmons = pid("Fever-Tree", "Harmons")
    for (s, e) in ((d(2026, 8, 1), d(2026, 8, 31)), (d(2026, 11, 1), d(2026, 11, 30)), (d(2026, 12, 1), d(2026, 12, 31))):
        add((harmons, "4pk", "TPR + Display", "4pk $4.99", 4.99, None, s, e, "Y", NA))
        add((harmons, "8pk", "TPR + Display", "8pk $5.99", 5.99, None, s, e, "Y", NA))
        add((harmons, "500mL", "TPR + Display", "500mL 2 for $5", 2.50, None, s, e, "Y", NA))

    # Naked Life WFM 2026
    add((pid("Naked Life", "WFM September Feature"), "All", "Feature TPR", "Promo SRP $9.49 (cost $33.03)", 9.49, 33.03,
         d(2026, 9, 2), d(2026, 10, 6), "Y", NA))

    # ---- 2025 reference windows from the HW hot sheet (all expired; kept as history / pattern) ----
    def hw(acct, windows, price=5.99, typ="TPR", label=None):
        for (s, e, *rest) in windows:
            p = rest[0] if rest else price
            t = rest[1] if len(rest) > 1 else typ
            add((pid("Henry's", acct), "All", t, label or f"{t} ${p:.2f}", p, None, s, e, "N", HW))

    std = [(d(2025, 6, 1), d(2025, 9, 6)), (d(2025, 10, 5), d(2026, 1, 3))]
    hw("Save Mart / Lucky", std)
    for div in ("SFWY Portland Div. #19", "Haggen Div. #24", "NorCal Div. #25 (incl. HI)", "Seattle Div. #27",
                "SoCal Div. #29", "Intermountain Div. #30", "Southwest Division (SWD) #17"):
        hw(div, std)
    hw("Raley's", [(d(2025, 5, 19), d(2025, 9, 6)), (d(2025, 9, 29), d(2026, 1, 3))])
    hw("Bi-Mart", [(d(2025, 9, 28), d(2026, 1, 3))], price=4.99)
    hw("Bashas'", [(d(2025, 5, 18), d(2025, 9, 6)), (d(2025, 9, 29), d(2026, 1, 3))])
    hw("C&K / Ray's Food Place / Shop Smart",
       [(d(2025, 10, 8), d(2025, 11, 4)), (d(2025, 11, 5), d(2025, 12, 2)), (d(2025, 12, 3), d(2025, 12, 30))])
    for k in ("Fred Meyer (Div. 701)", "Fry's (Div. 660)", "QFC (Div. 705)", "Ralphs SoCal (Div. 703)", "Smith's"):
        hw(k, [(d(2025, 10, 15), d(2026, 1, 3))], price=6.49)
    hw("Nugget Markets", [(d(2025, 9, 29), d(2026, 1, 3))])
    hw("Stater Bros.", [(d(2025, 9, 29), d(2026, 1, 3))])
    hw("Plaid Pantry", [(d(2025, 10, 5), d(2025, 11, 1)), (d(2025, 11, 2), d(2025, 11, 29)),
                        (d(2025, 11, 30), d(2026, 1, 3))], price=1.50, label="2 for $3.00")
    hw("WinCo Foods", [(d(2025, 5, 26), d(2025, 9, 2)), (d(2025, 9, 29), d(2026, 1, 3))], price=5.88)
    hw("Metropolitan Market", [(d(2025, 9, 28), d(2026, 1, 3))])
    hw("Northwest Grocers (NWG)", [(d(2025, 9, 29), d(2026, 1, 3))])
    hw("Town & Country Markets", [(d(2025, 9, 28), d(2026, 1, 3))], price=6.49)
    hw("Harvest Foods", [(d(2025, 11, 29), d(2026, 1, 3))])
    hw("Ridley's Family Markets", [(d(2025, 11, 30), d(2026, 1, 3))], price=5.49)
    hw("Rosauers", [(d(2025, 5, 19), d(2025, 9, 6)), (d(2025, 8, 30), d(2025, 9, 12), 5.29, "Deep TPR"),
                    (d(2025, 9, 29), d(2026, 1, 3))])
    hw("Yoke's Fresh Market", [(d(2025, 5, 19), d(2025, 9, 6)), (d(2025, 8, 4), d(2025, 8, 12), 5.29, "Deep TPR"),
                               (d(2025, 9, 29), d(2026, 1, 3)), (d(2025, 10, 29), d(2025, 11, 11), 4.99, "Sweet Deal")])
    return rows


PROMOS = _promos()

# Data questions found while merging the two documents.
# (account, brand, issue, action needed)
DATA_REVIEW = [
    ("All HW-only accounts", "Henry's",
     "The HW Soda hot sheet is dated 8/25/25. Its promo windows (e.g. 6/1-9/6, 10/5-1/3) are 2025 windows and have all "
     "expired. 22 Henry's programs carry 2025 SRPs forward and are marked 'Confirm for 2026'.",
     "Get 2026 SRP and promo windows for every program marked 'Confirm for 2026', then update Promo Calendar."),
    ("WinCo Foods", "Henry's",
     "Non-Alc 2026 gives case-cost tiers ($23 / $19.55 / $18.40) by window but no shelf retail. The 2025 hot sheet had "
     "SRP $6.49 / TPR $5.88.",
     "Confirm the 2026 shelf retail for each tier so reps can audit shelf price, not just case cost."),
    ("Albertsons/Safeway SWD", "Henry's",
     "Non-Alc says 'maintain $7.99 EDLP'; 2025 hot sheet ran TPR $5.99 against $7.99 SRP.",
     "Confirm whether SWD is EDLP-only for 2H 2026 (no TPRs)."),
    ("Albertsons/Safeway Mountain West North", "ZOA / Henry's",
     "Market listed as ID / MT / WY for ZOA but PNW / ID / UT / WY for Henry's.",
     "Confirm the division footprint and whether Intermountain #30 and Portland #19 now roll into Mountain West."),
    ("Albertsons/Safeway divisions", "Henry's",
     "Portland #19, Haggen #24, NorCal #25, Seattle #27 and SoCal #29 carried Henry's in 2025 but are not in the "
     "Non-Alc Henry's section.", "Confirm Henry's is still authorized and get 2026 pricing."),
    ("Plaid Pantry", "Henry's", "2025 SRP $1.50 single and promo '2 for $3.00' are the same unit price - no discount.",
     "Confirm the correct 2026 SRP or promo."),
    ("Town & Country Markets", "Henry's", "2025 TPR $6.49 equals SRP $6.49 - no discount.",
     "Confirm the correct 2026 SRP or promo."),
    ("Raley's", "Henry's", "2H 2026 plan lists four promotional windows but no dates or shelf retail.",
     "Add the four window dates and retail to Promo Calendar."),
    ("Yoke's Fresh Market", "ZOA / Henry's",
     "Retail TBD for both brands. Henry's $19.55 case cost window ended 9/8/26; ZOA ends 10/3/26.",
     "Get shelf retail so price audits can be scored."),
    ("Kroger", "Fever-Tree", "P10-P13 plan details are 'in the source PowerPoint', which was not provided.",
     "Share the Kroger Fever-Tree deck so windows and scan prices can be loaded."),
    ("Kroger banners", "Henry's",
     "Mega Buy 5 Save $5 timing on the hot sheet (6/18-7/8) is 2025. King Soopers is listed but has no outlet count.",
     "Confirm 2026 Kroger Henry's plan by banner."),
    ("BevMo!", "Henry's", "Promo pricing TBD on 2025 hot sheet (Bob and Lexi setting up).", "Confirm status."),
    ("Northwest Grocers (NWG)", "Henry's", "Outlet count is blank on the hot sheet.", "Add store count and store list."),
    ("Stater Bros.", "Henry's",
     "163 outlets are listed under MU-CA HI NORTH NV, but Stater Bros. is a SoCal chain. 54 stores do not carry Orange Cream.",
     "Confirm market unit; build a distribution-gap target list for Orange Cream."),
    ("Whole Foods Market", "Naked Life",
     "The WFM feature covers WA, OR, CA, TX (DSD) and FL + MA/NJ/MD dry stores (broadliner) - wider than the Pacific region.",
     "Confirm which WFM stores are on your team's routes."),
    ("Harmons", "Fever-Tree", "Display months are listed as Aug / Nov / Dec without exact dates; calendar uses full months.",
     "Confirm exact ad and endcap weeks."),
    ("Both source documents", "All",
     "Chain names in both documents are logos only (images), so they cannot be searched, filtered or counted.",
     "Keep chain names as text in the tool; logos are optional decoration."),
]

DISCREPANCY_TYPES = [
    "None",
    "Price - over plan",
    "Price - under plan",
    "Missing / wrong shelf tag",
    "Expired promo tag still up",
    "Out of stock / missing SKU",
    "Wrong shelf location (planogram)",
    "Display not built",
    "Display built - wrong product/price",
    "Unauthorized SKU on shelf",
    "Backstock missing",
    "Other",
]

SKU_LIST = [
    "All", "12pk", "Singles (Frosted Grape/Tropical Punch)", "4pk", "8pk", "500mL",
    "Root Beer", "Black Cherry Cream", "Orange Cream", "Vanilla Cream", "Margarita 4pk", "Mojito 4pk",
]

STATUSES = ["No Issue", "Open", "In Progress", "Resolved"]
YN = ["Y", "N"]
DISPLAY_YN = ["Yes", "No", "N/A"]
BRANDS = ["ZOA", "Henry's", "Fever-Tree", "Naked Life"]
ROSTER = ["Chris Armstrong"]  # add the rest of the team on the Lists tab
