# Independent SEC reconciliation — all verified-real companies, four fiscal years each

Generated 2026-10-14 13:22 UTC by `python scripts/independent_sec_reconciliation.py`.
XBRL values were retrieved **live** from SEC `companyconcept` (a different endpoint from the app's stored `companyfacts` snapshot) and selected with this script's own rules; the original 10-K HTML was parsed independently; derived metrics were recomputed with Decimal arithmetic. Compared with the app's API on a temporary database.

**Result: PASS — no discrepancies**

## Reported values

| Company | FY | Metric | App ($M) | Independent XBRL ($M) | Source filing (filed) | Printed in 10-K | Display | Result |
|---|---|---|---|---|---|---|---|---|
| Yellow | FY2019 | capex | 143.200 | 143.200 | 0000950170-22-000779 (2022-02-04) | 143.2 | $143.2M | OK |
| Yellow | FY2020 | capex | 140.600 | 140.600 | 0000950170-23-002332 (2023-02-09) | 140.6 | $140.6M | OK |
| Yellow | FY2021 | capex | 497.600 | 497.600 | 0000950170-23-002332 (2023-02-09) | 497.6 | $497.6M | OK |
| Yellow | FY2022 | capex | 191.800 | 191.800 | 0000950170-23-002332 (2023-02-09) | 191.8 | $191.8M | OK |
| Yellow | FY2019 | cash | 109.200 | 109.200 | 0001564590-21-005530 (2021-02-11) | 109.2 | $109.2M | OK |
| Yellow | FY2020 | cash | 439.300 | 439.300 | 0000950170-22-000779 (2022-02-04) | 439.3 | $439.3M | OK |
| Yellow | FY2021 | cash | 310.700 | 310.700 | 0000950170-23-002332 (2023-02-09) | 310.7 | $310.7M | OK |
| Yellow | FY2022 | cash | 235.100 | 235.100 | 0000950170-23-002332 (2023-02-09) | 235.1 | $235.1M | OK |
| Yellow | FY2019 | current_assets | 618.200 | 618.200 | 0001564590-21-005530 (2021-02-11) | 618.2 | $618.2M | OK |
| Yellow | FY2020 | current_assets | 1,029.800 | 1,029.800 | 0000950170-22-000779 (2022-02-04) | 1,029.8 | $1,029.8M | OK |
| Yellow | FY2021 | current_assets | 1,043.500 | 1,043.500 | 0000950170-23-002332 (2023-02-09) | 1,043.5 | $1,043.5M | OK |
| Yellow | FY2022 | current_assets | 914.100 | 914.100 | 0000950170-23-002332 (2023-02-09) | 914.1 | $914.1M | OK |
| Yellow | FY2019 | current_liabilities | 652.000 | 652.000 | 0001564590-21-005530 (2021-02-11) | 652.0 | $652.0M | OK |
| Yellow | FY2020 | current_liabilities | 700.700 | 700.700 | 0000950170-22-000779 (2022-02-04) | 700.7 | $700.7M | OK |
| Yellow | FY2021 | current_liabilities | 824.100 | 824.100 | 0000950170-23-002332 (2023-02-09) | 824.1 | $824.1M | OK |
| Yellow | FY2022 | current_liabilities | 717.000 | 717.000 | 0000950170-23-002332 (2023-02-09) | 717.0 | $717.0M | OK |
| Yellow | FY2019 | depreciation_amortization | 152.400 | 152.400 | 0000950170-22-000779 (2022-02-04) | 152.4 | $152.4M | OK |
| Yellow | FY2020 | depreciation_amortization | 134.900 | 134.900 | 0000950170-23-002332 (2023-02-09) | 134.9 | $134.9M | OK |
| Yellow | FY2021 | depreciation_amortization | 143.600 | 143.600 | 0000950170-23-002332 (2023-02-09) | 143.6 | $143.6M | OK |
| Yellow | FY2022 | depreciation_amortization | 143.400 | 143.400 | 0000950170-23-002332 (2023-02-09) | 143.4 | $143.4M | OK |
| Yellow | FY2019 | interest_expense | 111.200 | 111.200 | 0000950170-22-000779 (2022-02-04) | 111.2 | $111.2M | OK |
| Yellow | FY2020 | interest_expense | 135.900 | 135.900 | 0000950170-23-002332 (2023-02-09) | 135.9 | $135.9M | OK |
| Yellow | FY2021 | interest_expense | 150.700 | 150.700 | 0000950170-23-002332 (2023-02-09) | 150.7 | $150.7M | OK |
| Yellow | FY2022 | interest_expense | 162.900 | 162.900 | 0000950170-23-002332 (2023-02-09) | 162.9 | $162.9M | OK |
| Yellow | FY2019 | net_income | -104.000 | -104.000 | 0000950170-22-000779 (2022-02-04) | 104.0 | -$104.0M | OK |
| Yellow | FY2020 | net_income | -53.500 | -53.500 | 0000950170-23-002332 (2023-02-09) | 53.5 | -$53.5M | OK |
| Yellow | FY2021 | net_income | -109.100 | -109.100 | 0000950170-23-002332 (2023-02-09) | 109.1 | -$109.1M | OK |
| Yellow | FY2022 | net_income | 21.800 | 21.800 | 0000950170-23-002332 (2023-02-09) | 21.8 | $21.8M | OK |
| Yellow | FY2019 | operating_cash_flow | 21.500 | 21.500 | 0000950170-22-000779 (2022-02-04) | 21.5 | $21.5M | OK |
| Yellow | FY2020 | operating_cash_flow | 122.500 | 122.500 | 0000950170-23-002332 (2023-02-09) | 122.5 | $122.5M | OK |
| Yellow | FY2021 | operating_cash_flow | 10.200 | 10.200 | 0000950170-23-002332 (2023-02-09) | 10.2 | $10.2M | OK |
| Yellow | FY2022 | operating_cash_flow | 121.300 | 121.300 | 0000950170-23-002332 (2023-02-09) | 121.3 | $121.3M | OK |
| Yellow | FY2019 | operating_income | 16.200 | 16.200 | 0000950170-22-000779 (2022-02-04) | 16.2 | $16.2M | OK |
| Yellow | FY2020 | operating_income | 56.500 | 56.500 | 0000950170-23-002332 (2023-02-09) | 56.5 | $56.5M | OK |
| Yellow | FY2021 | operating_income | 103.600 | 103.600 | 0000950170-23-002332 (2023-02-09) | 103.6 | $103.6M | OK |
| Yellow | FY2022 | operating_income | 197.800 | 197.800 | 0000950170-23-002332 (2023-02-09) | 197.8 | $197.8M | OK |
| Yellow | FY2019 | receivables | 464.400 | 464.400 | 0001564590-21-005530 (2021-02-11) | 464.4 | $464.4M | OK |
| Yellow | FY2020 | receivables | 505.000 | 505.000 | 0000950170-22-000779 (2022-02-04) | 505.0 | $505.0M | OK |
| Yellow | FY2021 | receivables | 663.700 | 663.700 | 0000950170-23-002332 (2023-02-09) | 663.7 | $663.7M | OK |
| Yellow | FY2022 | receivables | 599.700 | 599.700 | 0000950170-23-002332 (2023-02-09) | 599.7 | $599.7M | OK |
| Yellow | FY2019 | revenue | 4,871.200 | 4,871.200 | 0000950170-22-000779 (2022-02-04) | 4,871.2 | $4,871.2M | OK |
| Yellow | FY2020 | revenue | 4,513.700 | 4,513.700 | 0000950170-23-002332 (2023-02-09) | 4,513.7 | $4,513.7M | OK |
| Yellow | FY2021 | revenue | 5,121.800 | 5,121.800 | 0000950170-23-002332 (2023-02-09) | 5,121.8 | $5,121.8M | OK |
| Yellow | FY2022 | revenue | 5,244.700 | 5,244.700 | 0000950170-23-002332 (2023-02-09) | 5,244.7 | $5,244.7M | OK |
| Yellow | FY2019 | total_debt | 862.200 | 862.200 | 0001564590-21-005530 (2021-02-11) | 862.2 | $862.2M | OK |
| Yellow | FY2020 | total_debt | 1,225.400 | 1,225.400 | 0000950170-22-000779 (2022-02-04) | 1,225.4 | $1,225.4M | OK |
| Yellow | FY2021 | total_debt | 1,554.500 | 1,554.500 | 0000950170-23-002332 (2023-02-09) | 1,554.5 | $1,554.5M | OK |
| Yellow | FY2022 | total_debt | 1,538.000 | 1,538.000 | 0000950170-23-002332 (2023-02-09) | 1,538.0 | $1,538.0M | OK |
| Old Dominion | FY2019 | capex | 479.325 | 479.325 | 0001564590-22-006303 (2022-02-23) | 479,325 | $479.3M | OK |
| Old Dominion | FY2020 | capex | 225.081 | 225.081 | 0000950170-23-003783 (2023-02-22) | 225,081 | $225.1M | OK |
| Old Dominion | FY2021 | capex | 550.077 | 550.077 | 0000950170-23-003783 (2023-02-22) | 550,077 | $550.1M | OK |
| Old Dominion | FY2022 | capex | 775.148 | 775.148 | 0000950170-23-003783 (2023-02-22) | 775,148 | $775.1M | OK |
| Old Dominion | FY2019 | cash | 403.571 | 403.571 | 0001564590-20-006626 (2020-02-26) | 403,571 | $403.6M | OK |
| Old Dominion | FY2020 | cash | 401.430 | 401.430 | 0001564590-22-006303 (2022-02-23) | 401,430 | $401.4M | OK |
| Old Dominion | FY2021 | cash | 462.564 | 462.564 | 0000950170-23-003783 (2023-02-22) | 462,564 | $462.6M | OK |
| Old Dominion | FY2022 | cash | 186.312 | 186.312 | 0000950170-23-003783 (2023-02-22) | 186,312 | $186.3M | OK |
| Old Dominion | FY2019 | current_assets | 866.834 | 866.834 | 0001564590-20-006626 (2020-02-26) | 866,834 | $866.8M | OK |
| Old Dominion | FY2020 | current_assets | 1,243.339 | 1,243.339 | 0001564590-22-006303 (2022-02-23) | 1,243,339 | $1,243.3M | OK |
| Old Dominion | FY2021 | current_assets | 1,383.787 | 1,383.787 | 0000950170-23-003783 (2023-02-22) | 1,383,787 | $1,383.8M | OK |
| Old Dominion | FY2022 | current_assets | 933.740 | 933.740 | 0000950170-23-003783 (2023-02-22) | 933,740 | $933.7M | OK |
| Old Dominion | FY2019 | current_liabilities | 366.085 | 366.085 | 0001564590-20-006626 (2020-02-26) | 366,085 | $366.1M | OK |
| Old Dominion | FY2020 | current_liabilities | 373.130 | 373.130 | 0001564590-22-006303 (2022-02-23) | 373,130 | $373.1M | OK |
| Old Dominion | FY2021 | current_liabilities | 464.234 | 464.234 | 0000950170-23-003783 (2023-02-22) | 464,234 | $464.2M | OK |
| Old Dominion | FY2022 | current_liabilities | 529.793 | 529.793 | 0000950170-23-003783 (2023-02-22) | 529,793 | $529.8M | OK |
| Old Dominion | FY2019 | depreciation_amortization | 253.681 | 253.681 | 0001564590-22-006303 (2022-02-23) | 253,681 | $253.7M | OK |
| Old Dominion | FY2020 | depreciation_amortization | 261.259 | 261.259 | 0000950170-23-003783 (2023-02-22) | 261,259 | $261.3M | OK |
| Old Dominion | FY2021 | depreciation_amortization | 259.883 | 259.883 | 0000950170-23-003783 (2023-02-22) | 259,883 | $259.9M | OK |
| Old Dominion | FY2022 | depreciation_amortization | 276.050 | 276.050 | 0000950170-23-003783 (2023-02-22) | 276,050 | $276.1M | OK |
| Old Dominion | FY2019 | interest_expense | 0.377 | 0.377 | 0001564590-22-006303 (2022-02-23) | 377 | $0.4M | OK |
| Old Dominion | FY2020 | interest_expense | 2.782 | 2.782 | 0000950170-23-003783 (2023-02-22) | 2,782 | $2.8M | OK |
| Old Dominion | FY2021 | interest_expense | 1.727 | 1.727 | 0000950170-23-003783 (2023-02-22) | 1,727 | $1.7M | OK |
| Old Dominion | FY2022 | interest_expense | 1.563 | 1.563 | 0000950170-23-003783 (2023-02-22) | 1,563 | $1.6M | OK |
| Old Dominion | FY2019 | net_income | 615.518 | 615.518 | 0001564590-22-006303 (2022-02-23) | 615,518 | $615.5M | OK |
| Old Dominion | FY2020 | net_income | 672.682 | 672.682 | 0000950170-23-003783 (2023-02-22) | 672,682 | $672.7M | OK |
| Old Dominion | FY2021 | net_income | 1,034.375 | 1,034.375 | 0000950170-23-003783 (2023-02-22) | 1,034,375 | $1,034.4M | OK |
| Old Dominion | FY2022 | net_income | 1,377.159 | 1,377.159 | 0000950170-23-003783 (2023-02-22) | 1,377,159 | $1,377.2M | OK |
| Old Dominion | FY2019 | operating_cash_flow | 983.888 | 983.888 | 0001564590-22-006303 (2022-02-23) | 983,888 | $983.9M | OK |
| Old Dominion | FY2020 | operating_cash_flow | 933.024 | 933.024 | 0000950170-23-003783 (2023-02-22) | 933,024 | $933.0M | OK |
| Old Dominion | FY2021 | operating_cash_flow | 1,212.606 | 1,212.606 | 0000950170-23-003783 (2023-02-22) | 1,212,606 | $1,212.6M | OK |
| Old Dominion | FY2022 | operating_cash_flow | 1,691.582 | 1,691.582 | 0000950170-23-003783 (2023-02-22) | 1,691,582 | $1,691.6M | OK |
| Old Dominion | FY2019 | operating_income | 818.706 | 818.706 | 0001564590-22-006303 (2022-02-23) | 818,706 | $818.7M | OK |
| Old Dominion | FY2020 | operating_income | 906.882 | 906.882 | 0000950170-23-003783 (2023-02-22) | 906,882 | $906.9M | OK |
| Old Dominion | FY2021 | operating_income | 1,391.602 | 1,391.602 | 0000950170-23-003783 (2023-02-22) | 1,391,602 | $1,391.6M | OK |
| Old Dominion | FY2022 | operating_income | 1,840.632 | 1,840.632 | 0000950170-23-003783 (2023-02-22) | 1,840,632 | $1,840.6M | OK |
| Old Dominion | FY2019 | receivables | 397.579 | 397.579 | 0001564590-20-006626 (2020-02-26) | 397,579 | $397.6M | OK |
| Old Dominion | FY2020 | receivables | 444.653 | 444.653 | 0001564590-22-006303 (2022-02-23) | 444,653 | $444.7M | OK |
| Old Dominion | FY2021 | receivables | 567.474 | 567.474 | 0000950170-23-003783 (2023-02-22) | 567,474 | $567.5M | OK |
| Old Dominion | FY2022 | receivables | 578.648 | 578.648 | 0000950170-23-003783 (2023-02-22) | 578,648 | $578.6M | OK |
| Old Dominion | FY2019 | revenue | 4,109.111 | 4,109.111 | 0001564590-22-006303 (2022-02-23) | 4,109,111 | $4,109.1M | OK |
| Old Dominion | FY2020 | revenue | 4,015.129 | 4,015.129 | 0000950170-23-003783 (2023-02-22) | 4,015,129 | $4,015.1M | OK |
| Old Dominion | FY2021 | revenue | 5,256.328 | 5,256.328 | 0000950170-23-003783 (2023-02-22) | 5,256,328 | $5,256.3M | OK |
| Old Dominion | FY2022 | revenue | 6,260.077 | 6,260.077 | 0000950170-23-003783 (2023-02-22) | 6,260,077 | $6,260.1M | OK |
| Old Dominion | FY2019 | total_debt | 45.000 | 45.000 | 0001564590-21-008056 (2021-02-24) | 45,000 | $45.0M | OK |
| Old Dominion | FY2020 | total_debt | 99.931 | 99.931 | 0001564590-22-006303 (2022-02-23) | 99,931 | $99.9M | OK |
| Old Dominion | FY2021 | total_debt | 99.947 | 99.947 | 0000950170-23-003783 (2023-02-22) | 99,947 | $99.9M | OK |
| Old Dominion | FY2022 | total_debt | 99.963 | 99.963 | 0000950170-23-003783 (2023-02-22) | 99,963 | $100.0M | OK |
| Party City | FY2018 | capex | 85.661 | 85.661 | 0001564590-21-012608 (2021-03-12) | 85,661 | $85.7M | OK |
| Party City | FY2019 | capex | 61.733 | 61.733 | 0000950170-22-002280 (2022-02-28) | 61,733 | $61.7M | OK |
| Party City | FY2020 | capex | 51.128 | 51.128 | 0000950170-22-002280 (2022-02-28) | 51,128 | $51.1M | OK |
| Party City | FY2021 | capex | 79.222 | 79.222 | 0000950170-22-002280 (2022-02-28) | 79,222 | $79.2M | OK |
| Party City | FY2018 | cash | 58.909 | 58.909 | 0001193125-20-071738 (2020-03-12) | 58,909 | $58.9M | OK |
| Party City | FY2019 | cash | 34.917 | 34.917 | 0001564590-21-012608 (2021-03-12) | 34,917 | $34.9M | OK |
| Party City | FY2020 | cash | 119.532 | 119.532 | 0000950170-22-002280 (2022-02-28) | 119,532 | $119.5M | OK |
| Party City | FY2021 | cash | 47.914 | 47.914 | 0000950170-22-002280 (2022-02-28) | 47,914 | $47.9M | OK |
| Party City | FY2018 | current_assets | 1,023.835 | 1,023.835 | 0001193125-20-071738 (2020-03-12) | 1,023,835 | $1,023.8M | OK |
| Party City | FY2019 | current_assets | 894.130 | 894.130 | 0001564590-21-012608 (2021-03-12) | 894,130 | $894.1M | OK |
| Party City | FY2020 | current_assets | 809.260 | 809.260 | 0000950170-22-002280 (2022-02-28) | 809,260 | $809.3M | OK |
| Party City | FY2021 | current_assets | 698.483 | 698.483 | 0000950170-22-002280 (2022-02-28) | 698,483 | $698.5M | OK |
| Party City | FY2018 | current_liabilities | 711.437 | 711.437 | 0001193125-20-071738 (2020-03-12) | 711,437 | $711.4M | OK |
| Party City | FY2019 | current_liabilities | 694.927 | 694.927 | 0001564590-21-012608 (2021-03-12) | 694,927 | $694.9M | OK |
| Party City | FY2020 | current_liabilities | 713.877 | 713.877 | 0000950170-22-002280 (2022-02-28) | 713,877 | $713.9M | OK |
| Party City | FY2021 | current_liabilities | 570.059 | 570.059 | 0000950170-22-002280 (2022-02-28) | 570,059 | $570.1M | OK |
| Party City | FY2018 | depreciation_amortization | 78.575 | 78.575 | 0001564590-21-012608 (2021-03-12) | 78,575 | $78.6M | OK |
| Party City | FY2019 | depreciation_amortization | 81.116 | 81.116 | 0000950170-22-002280 (2022-02-28) | 81,116 | $81.1M | OK |
| Party City | FY2020 | depreciation_amortization | 76.506 | 76.506 | 0000950170-22-002280 (2022-02-28) | 76,506 | $76.5M | OK |
| Party City | FY2021 | depreciation_amortization | 65.610 | 65.610 | 0000950170-22-002280 (2022-02-28) | 65,610 | $65.6M | OK |
| Party City | FY2018 | interest_expense | 105.706 | 105.706 | 0001564590-21-012608 (2021-03-12) | 105,706 | $105.7M | OK |
| Party City | FY2019 | interest_expense | 114.899 | 114.899 | 0000950170-22-002280 (2022-02-28) | 114,899 | $114.9M | OK |
| Party City | FY2020 | interest_expense | 77.043 | 77.043 | 0000950170-22-002280 (2022-02-28) | 77,043 | $77.0M | OK |
| Party City | FY2021 | interest_expense | 87.226 | 87.226 | 0000950170-22-002280 (2022-02-28) | 87,226 | $87.2M | OK |
| Party City | FY2018 | net_income | 123.259 | 123.259 | 0001564590-21-012608 (2021-03-12) | 123,259 | $123.3M | OK |
| Party City | FY2019 | net_income | -532.495 | -532.495 | 0000950170-22-002280 (2022-02-28) | 532,495 | -$532.5M | OK |
| Party City | FY2020 | net_income | -528.238 | -528.238 | 0000950170-22-002280 (2022-02-28) | 528,238 | -$528.2M | OK |
| Party City | FY2021 | net_income | -6.528 | -6.528 | 0000950170-22-002280 (2022-02-28) | 6,528 | -$6.5M | OK |
| Party City | FY2018 | operating_cash_flow | 101.856 | 101.856 | 0001564590-21-012608 (2021-03-12) | 101,856 | $101.9M | OK |
| Party City | FY2019 | operating_cash_flow | 43.693 | 43.693 | 0000950170-22-002280 (2022-02-28) | 43,693 | $43.7M | OK |
| Party City | FY2020 | operating_cash_flow | 77.200 | 77.200 | 0000950170-22-002280 (2022-02-28) | 77,200 | $77.2M | OK |
| Party City | FY2021 | operating_cash_flow | 51.935 | 51.935 | 0000950170-22-002280 (2022-02-28) | 51,935 | $51.9M | OK |
| Party City | FY2018 | operating_income | 278.285 | 278.285 | 0001564590-21-012608 (2021-03-12) | 278,285 | $278.3M | OK |
| Party City | FY2019 | operating_income | -417.393 | -417.393 | 0000950170-22-002280 (2022-02-28) | 417,393 | -$417.4M | OK |
| Party City | FY2020 | operating_income | -877.501 | -877.501 | 0000950170-22-002280 (2022-02-28) | 877,501 | -$877.5M | OK |
| Party City | FY2021 | operating_income | 84.632 | 84.632 | 0000950170-22-002280 (2022-02-28) | 84,632 | $84.6M | OK |
| Party City | FY2018 | receivables | 146.983 | 146.983 | 0001193125-20-071738 (2020-03-12) | 146,983 | $147.0M | OK |
| Party City | FY2019 | receivables | 149.109 | 149.109 | 0001564590-21-012608 (2021-03-12) | 149,109 | $149.1M | OK |
| Party City | FY2020 | receivables | 90.879 | 90.879 | 0000950170-22-002280 (2022-02-28) | 90,879 | $90.9M | OK |
| Party City | FY2021 | receivables | 93.301 | 93.301 | 0000950170-22-002280 (2022-02-28) | 93,301 | $93.3M | OK |
| Party City | FY2018 | revenue | 2,427.515 | 2,427.515 | 0001564590-21-012608 (2021-03-12) | 2,427,515 | $2,427.5M | OK |
| Party City | FY2019 | revenue | 2,348.789 | 2,348.789 | 0000950170-22-002280 (2022-02-28) | 2,348,789 | $2,348.8M | OK |
| Party City | FY2020 | revenue | 1,850.690 | 1,850.690 | 0000950170-22-002280 (2022-02-28) | 1,850,690 | $1,850.7M | OK |
| Party City | FY2021 | revenue | 2,171.060 | 2,171.060 | 0000950170-22-002280 (2022-02-28) | 2,171,060 | $2,171.1M | OK |
| Party City | FY2018 | total_debt | 1,635.279 | 1,635.279 | 0001193125-20-071738 (2020-03-12) | 1,635,279 | $1,635.3M | OK |
| Party City | FY2019 | total_debt | 1,575.511 | 1,575.511 | 0001564590-21-012608 (2021-03-12) | 1,575,511 | $1,575.5M | OK |
| Party City | FY2020 | total_debt | 1,343.384 | 1,343.384 | 0000950170-22-002280 (2022-02-28) | 1,343,384 | $1,343.4M | OK |
| Party City | FY2021 | total_debt | 1,352.562 | 1,352.562 | 0000950170-22-002280 (2022-02-28) | 1,352,562 | $1,352.6M | OK |
| Diebold Nixdorf | FY2019 | capex | n/a (missing) | — | — | — | — | missing in app; shown as n/a |
| Diebold Nixdorf | FY2020 | capex | n/a (missing) | — | — | — | — | missing in app; shown as n/a |
| Diebold Nixdorf | FY2021 | capex | n/a (missing) | — | — | — | — | missing in app; shown as n/a |
| Diebold Nixdorf | FY2022 | capex | n/a (missing) | — | — | — | — | missing in app; shown as n/a |
| Diebold Nixdorf | FY2019 | cash | 280.900 | 280.900 | 0000028823-23-000078 (2023-03-16) | 280.9 | $280.9M | OK |
| Diebold Nixdorf | FY2020 | cash | 324.500 | 324.500 | 0000028823-23-000078 (2023-03-16) | 324.5 | $324.5M | OK |
| Diebold Nixdorf | FY2021 | cash | 388.900 | 388.900 | 0000028823-23-000078 (2023-03-16) | 388.9 | $388.9M | OK |
| Diebold Nixdorf | FY2022 | cash | 319.100 | 319.100 | 0000028823-23-000078 (2023-03-16) | 319.1 | $319.1M | OK |
| Diebold Nixdorf | FY2019 | current_assets | 1,892.000 | 1,892.000 | 0000028823-21-000059 (2021-03-01) | 1,892.0 | $1,892.0M | OK |
| Diebold Nixdorf | FY2020 | current_assets | 1,857.300 | 1,857.300 | 0000028823-22-000058 (2022-03-11) | 1,857.3 | $1,857.3M | OK |
| Diebold Nixdorf | FY2021 | current_assets | 1,887.300 | 1,887.300 | 0000028823-23-000078 (2023-03-16) | 1,887.3 | $1,887.3M | OK |
| Diebold Nixdorf | FY2022 | current_assets | 1,770.900 | 1,770.900 | 0000028823-23-000078 (2023-03-16) | 1,770.9 | $1,770.9M | OK |
| Diebold Nixdorf | FY2019 | current_liabilities | 1,599.600 | 1,599.600 | 0000028823-21-000059 (2021-03-01) | 1,599.6 | $1,599.6M | OK |
| Diebold Nixdorf | FY2020 | current_liabilities | 1,649.500 | 1,649.500 | 0000028823-22-000058 (2022-03-11) | 1,649.5 | $1,649.5M | OK |
| Diebold Nixdorf | FY2021 | current_liabilities | 1,749.400 | 1,749.400 | 0000028823-23-000078 (2023-03-16) | 1,749.4 | $1,749.4M | OK |
| Diebold Nixdorf | FY2022 | current_liabilities | 1,604.900 | 1,604.900 | 0000028823-23-000078 (2023-03-16) | 1,604.9 | $1,604.9M | OK |
| Diebold Nixdorf | FY2019 | depreciation_amortization | 226.100 | 226.100 | 0000028823-20-000056 (2020-02-26) | 226.1 | $226.1M | OK |
| Diebold Nixdorf | FY2020 | depreciation_amortization | 73.700 | 73.700 | 0000028823-23-000078 (2023-03-16) | 73.7 | $73.7M | OK |
| Diebold Nixdorf | FY2021 | depreciation_amortization | 46.400 | 46.400 | 0000028823-23-000078 (2023-03-16) | 46.4 | $46.4M | OK |
| Diebold Nixdorf | FY2022 | depreciation_amortization | 29.800 | 29.800 | 0000028823-23-000078 (2023-03-16) | 29.8 | $29.8M | OK |
| Diebold Nixdorf | FY2019 | interest_expense | 202.900 | 202.900 | 0000028823-22-000058 (2022-03-11) | 202.9 | $202.9M | OK |
| Diebold Nixdorf | FY2020 | interest_expense | 266.800 | 266.800 | 0000028823-23-000078 (2023-03-16) | 266.8 | $266.8M | OK |
| Diebold Nixdorf | FY2021 | interest_expense | 195.300 | 195.300 | 0000028823-23-000078 (2023-03-16) | 195.3 | $195.3M | OK |
| Diebold Nixdorf | FY2022 | interest_expense | 199.200 | 199.200 | 0000028823-23-000078 (2023-03-16) | 199.2 | $199.2M | OK |
| Diebold Nixdorf | FY2019 | net_income | -341.300 | -341.300 | 0000028823-22-000058 (2022-03-11) | 341.3 | -$341.3M | OK |
| Diebold Nixdorf | FY2020 | net_income | -269.100 | -269.100 | 0000028823-23-000078 (2023-03-16) | 269.1 | -$269.1M | OK |
| Diebold Nixdorf | FY2021 | net_income | -78.800 | -78.800 | 0000028823-23-000078 (2023-03-16) | 78.8 | -$78.8M | OK |
| Diebold Nixdorf | FY2022 | net_income | -581.400 | -581.400 | 0000028823-23-000078 (2023-03-16) | 581.4 | -$581.4M | OK |
| Diebold Nixdorf | FY2019 | operating_cash_flow | 135.800 | 135.800 | 0000028823-22-000058 (2022-03-11) | 135.8 | $135.8M | OK |
| Diebold Nixdorf | FY2020 | operating_cash_flow | 18.000 | 18.000 | 0000028823-23-000078 (2023-03-16) | 18.0 | $18.0M | OK |
| Diebold Nixdorf | FY2021 | operating_cash_flow | 123.300 | 123.300 | 0000028823-23-000078 (2023-03-16) | 123.3 | $123.3M | OK |
| Diebold Nixdorf | FY2022 | operating_cash_flow | -387.900 | -387.900 | 0000028823-23-000078 (2023-03-16) | 387.9 | -$387.9M | OK |
| Diebold Nixdorf | FY2019 | operating_income | -26.600 | -26.600 | 0000028823-22-000058 (2022-03-11) | 26.6 | -$26.6M | OK |
| Diebold Nixdorf | FY2020 | operating_income | 24.000 | 24.000 | 0000028823-23-000078 (2023-03-16) | 24.0 | $24.0M | OK |
| Diebold Nixdorf | FY2021 | operating_income | 137.100 | 137.100 | 0000028823-23-000078 (2023-03-16) | 137.1 | $137.1M | OK |
| Diebold Nixdorf | FY2022 | operating_income | -211.700 | -211.700 | 0000028823-23-000078 (2023-03-16) | 211.7 | -$211.7M | OK |
| Diebold Nixdorf | FY2019 | receivables | 619.300 | 619.300 | 0000028823-22-000058 (2022-03-11) | 619.3 | $619.3M | OK |
| Diebold Nixdorf | FY2020 | receivables | 646.900 | 646.900 | 0000028823-23-000078 (2023-03-16) | 646.9 | $646.9M | OK |
| Diebold Nixdorf | FY2021 | receivables | 595.200 | 595.200 | 0000028823-23-000078 (2023-03-16) | 595.2 | $595.2M | OK |
| Diebold Nixdorf | FY2022 | receivables | 612.200 | 612.200 | 0000028823-23-000078 (2023-03-16) | 612.2 | $612.2M | OK |
| Diebold Nixdorf | FY2019 | revenue | 4,408.700 | 4,408.700 | 0000028823-22-000058 (2022-03-11) | 4,408.7 | $4,408.7M | OK |
| Diebold Nixdorf | FY2020 | revenue | 3,902.300 | 3,902.300 | 0000028823-23-000078 (2023-03-16) | 3,902.3 | $3,902.3M | OK |
| Diebold Nixdorf | FY2021 | revenue | 3,905.200 | 3,905.200 | 0000028823-23-000078 (2023-03-16) | 3,905.2 | $3,905.2M | OK |
| Diebold Nixdorf | FY2022 | revenue | 3,460.700 | 3,460.700 | 0000028823-23-000078 (2023-03-16) | 3,460.7 | $3,460.7M | OK |
| Diebold Nixdorf | FY2019 | total_debt | 2,141.200 | 2,141.200 | 0000028823-21-000059 (2021-03-01) | components 2,108.7 + 32.5 | $2,141.2M | OK |
| Diebold Nixdorf | FY2020 | total_debt | 2,346.400 | 2,346.400 | 0000028823-22-000058 (2022-03-11) | components 2,335.7 + 10.7 | $2,346.4M | OK |
| Diebold Nixdorf | FY2021 | total_debt | 2,292.700 | 2,292.700 | 0000028823-23-000078 (2023-03-16) | components 2,245.6 + 47.1 | $2,292.7M | OK |
| Diebold Nixdorf | FY2022 | total_debt | 2,609.800 | 2,609.800 | 0000028823-23-000078 (2023-03-16) | components 2,585.8 + 24.0 | $2,609.8M | OK |
| Saia | FY2019 | capex | 287.655 | 287.655 | 0001564590-22-006259 (2022-02-23) | 287,655 | $287.7M | OK |
| Saia | FY2020 | capex | 231.142 | 231.142 | 0000950170-23-004094 (2023-02-23) | 231,142 | $231.1M | OK |
| Saia | FY2021 | capex | 285.746 | 285.746 | 0000950170-23-004094 (2023-02-23) | 285,746 | $285.7M | OK |
| Saia | FY2022 | capex | 367.429 | 367.429 | 0000950170-23-004094 (2023-02-23) | 367,429 | $367.4M | OK |
| Saia | FY2019 | cash | 0.248 | 0.248 | 0001564590-21-008077 (2021-02-24) | 248 | $0.2M | OK |
| Saia | FY2020 | cash | 25.308 | 25.308 | 0001564590-22-006259 (2022-02-23) | 25,308 | $25.3M | OK |
| Saia | FY2021 | cash | 106.588 | 106.588 | 0000950170-23-004094 (2023-02-23) | 106,588 | $106.6M | OK |
| Saia | FY2022 | cash | 187.390 | 187.390 | 0000950170-23-004094 (2023-02-23) | 187,390 | $187.4M | OK |
| Saia | FY2019 | current_assets | 232.379 | 232.379 | 0001564590-21-008077 (2021-02-24) | 232,379 | $232.4M | OK |
| Saia | FY2020 | current_assets | 271.696 | 271.696 | 0001564590-22-006259 (2022-02-23) | 271,696 | $271.7M | OK |
| Saia | FY2021 | current_assets | 416.255 | 416.255 | 0000950170-23-004094 (2023-02-23) | 416,255 | $416.3M | OK |
| Saia | FY2022 | current_assets | 530.886 | 530.886 | 0000950170-23-004094 (2023-02-23) | 530,886 | $530.9M | OK |
| Saia | FY2019 | current_liabilities | 241.246 | 241.246 | 0001564590-21-008077 (2021-02-24) | 241,246 | $241.2M | OK |
| Saia | FY2020 | current_liabilities | 275.754 | 275.754 | 0001564590-22-006259 (2022-02-23) | 275,754 | $275.8M | OK |
| Saia | FY2021 | current_liabilities | 321.348 | 321.348 | 0000950170-23-004094 (2023-02-23) | 321,348 | $321.3M | OK |
| Saia | FY2022 | current_liabilities | 274.085 | 274.085 | 0000950170-23-004094 (2023-02-23) | 274,085 | $274.1M | OK |
| Saia | FY2019 | depreciation_amortization | 119.135 | 119.135 | 0001564590-22-006259 (2022-02-23) | 119,135 | $119.1M | OK |
| Saia | FY2020 | depreciation_amortization | 134.655 | 134.655 | 0000950170-23-004094 (2023-02-23) | 134,655 | $134.7M | OK |
| Saia | FY2021 | depreciation_amortization | 141.700 | 141.700 | 0000950170-23-004094 (2023-02-23) | 141,700 | $141.7M | OK |
| Saia | FY2022 | depreciation_amortization | 157.203 | 157.203 | 0000950170-23-004094 (2023-02-23) | 157,203 | $157.2M | OK |
| Saia | FY2019 | interest_expense | 6.688 | 6.688 | 0001564590-22-006259 (2022-02-23) | 6,688 | $6.7M | OK |
| Saia | FY2020 | interest_expense | 5.177 | 5.177 | 0000950170-23-004094 (2023-02-23) | 5,177 | $5.2M | OK |
| Saia | FY2021 | interest_expense | 3.212 | 3.212 | 0000950170-23-004094 (2023-02-23) | 3,212 | $3.2M | OK |
| Saia | FY2022 | interest_expense | 2.611 | 2.611 | 0000950170-23-004094 (2023-02-23) | 2,611 | $2.6M | OK |
| Saia | FY2019 | net_income | 113.719 | 113.719 | 0001564590-22-006259 (2022-02-23) | 113,719 | $113.7M | OK |
| Saia | FY2020 | net_income | 138.340 | 138.340 | 0000950170-23-004094 (2023-02-23) | 138,340 | $138.3M | OK |
| Saia | FY2021 | net_income | 253.235 | 253.235 | 0000950170-23-004094 (2023-02-23) | 253,235 | $253.2M | OK |
| Saia | FY2022 | net_income | 357.422 | 357.422 | 0000950170-23-004094 (2023-02-23) | 357,422 | $357.4M | OK |
| Saia | FY2019 | operating_cash_flow | 272.876 | 272.876 | 0001564590-22-006259 (2022-02-23) | 272,876 | $272.9M | OK |
| Saia | FY2020 | operating_cash_flow | 309.145 | 309.145 | 0000950170-23-004094 (2023-02-23) | 309,145 | $309.1M | OK |
| Saia | FY2021 | operating_cash_flow | 382.592 | 382.592 | 0000950170-23-004094 (2023-02-23) | 382,592 | $382.6M | OK |
| Saia | FY2022 | operating_cash_flow | 473.026 | 473.026 | 0000950170-23-004094 (2023-02-23) | 473,026 | $473.0M | OK |
| Saia | FY2019 | operating_income | 152.586 | 152.586 | 0001564590-22-006259 (2022-02-23) | 152,586 | $152.6M | OK |
| Saia | FY2020 | operating_income | 180.321 | 180.321 | 0000950170-23-004094 (2023-02-23) | 180,321 | $180.3M | OK |
| Saia | FY2021 | operating_income | 335.141 | 335.141 | 0000950170-23-004094 (2023-02-23) | 335,141 | $335.1M | OK |
| Saia | FY2022 | operating_income | 470.488 | 470.488 | 0000950170-23-004094 (2023-02-23) | 470,488 | $470.5M | OK |
| Saia | FY2019 | receivables | 196.119 | 196.119 | 0001564590-21-008077 (2021-02-24) | 196,119 | $196.1M | OK |
| Saia | FY2020 | receivables | 216.899 | 216.899 | 0001564590-22-006259 (2022-02-23) | 216,899 | $216.9M | OK |
| Saia | FY2021 | receivables | 276.755 | 276.755 | 0000950170-23-004094 (2023-02-23) | 276,755 | $276.8M | OK |
| Saia | FY2022 | receivables | 290.306 | 290.306 | 0000950170-23-004094 (2023-02-23) | 290,306 | $290.3M | OK |
| Saia | FY2019 | revenue | 1,786.735 | 1,786.735 | 0001564590-22-006259 (2022-02-23) | 1,786,735 | $1,786.7M | OK |
| Saia | FY2020 | revenue | 1,822.366 | 1,822.366 | 0000950170-23-004094 (2023-02-23) | 1,822,366 | $1,822.4M | OK |
| Saia | FY2021 | revenue | 2,288.704 | 2,288.704 | 0000950170-23-004094 (2023-02-23) | 2,288,704 | $2,288.7M | OK |
| Saia | FY2022 | revenue | 2,792.057 | 2,792.057 | 0000950170-23-004094 (2023-02-23) | 2,792,057 | $2,792.1M | OK |
| Saia | FY2019 | total_debt | 136.430 | 136.430 | 0001564590-21-008077 (2021-02-24) | 136,430 | $136.4M | OK |
| Saia | FY2020 | total_debt | 70.976 | 70.976 | 0001564590-22-006259 (2022-02-23) | 70,976 | $71.0M | OK |
| Saia | FY2021 | total_debt | 50.404 | 50.404 | 0000950170-23-004094 (2023-02-23) | 50,404 | $50.4M | OK |
| Saia | FY2022 | total_debt | 31.008 | 31.008 | 0000950170-23-004094 (2023-02-23) | 31,008 | $31.0M | OK |

## Derived values (recomputed independently)

| Company | FY | Metric | App display | Independent value | Result |
|---|---|---|---|---|---|
| Yellow | FY2019 | ebitda | $168.6M | 168.6000 | OK |
| Yellow | FY2019 | ebitda_margin_pct | 3.5% | 3.4612 | OK |
| Yellow | FY2019 | net_debt | $753.0M | 753.0000 | OK |
| Yellow | FY2019 | net_leverage_x | 4.47x | 4.4662 | OK |
| Yellow | FY2019 | gross_leverage_x | 5.11x | 5.1139 | OK |
| Yellow | FY2019 | interest_coverage_x | 1.52x | 1.5162 | OK |
| Yellow | FY2019 | free_cash_flow | -$121.7M | -121.7000 | OK |
| Yellow | FY2019 | net_margin_pct | -2.1% | -2.1350 | OK |
| Yellow | FY2019 | current_ratio_x | 0.95x | 0.9482 | OK |
| Yellow | FY2019 | dso_days | 34.8 days | 34.7976 | OK |
| Yellow | FY2020 | ebitda | $191.4M | 191.4000 | OK |
| Yellow | FY2020 | ebitda_margin_pct | 4.2% | 4.2404 | OK |
| Yellow | FY2020 | net_debt | $786.1M | 786.1000 | OK |
| Yellow | FY2020 | net_leverage_x | 4.11x | 4.1071 | OK |
| Yellow | FY2020 | gross_leverage_x | 6.40x | 6.4023 | OK |
| Yellow | FY2020 | interest_coverage_x | 1.41x | 1.4084 | OK |
| Yellow | FY2020 | free_cash_flow | -$18.1M | -18.1000 | OK |
| Yellow | FY2020 | net_margin_pct | -1.2% | -1.1853 | OK |
| Yellow | FY2020 | current_ratio_x | 1.47x | 1.4697 | OK |
| Yellow | FY2020 | dso_days | 40.8 days | 40.8368 | OK |
| Yellow | FY2020 | revenue_growth_pct | -7.3% | -7.3391 | OK |
| Yellow | FY2020 | cash_change_pct | 302.3% | 302.2894 | OK |
| Yellow | FY2021 | ebitda | $247.2M | 247.2000 | OK |
| Yellow | FY2021 | ebitda_margin_pct | 4.8% | 4.8264 | OK |
| Yellow | FY2021 | net_debt | $1,243.8M | 1,243.8000 | OK |
| Yellow | FY2021 | net_leverage_x | 5.03x | 5.0316 | OK |
| Yellow | FY2021 | gross_leverage_x | 6.29x | 6.2884 | OK |
| Yellow | FY2021 | interest_coverage_x | 1.64x | 1.6403 | OK |
| Yellow | FY2021 | free_cash_flow | -$487.4M | -487.4000 | OK |
| Yellow | FY2021 | net_margin_pct | -2.1% | -2.1301 | OK |
| Yellow | FY2021 | current_ratio_x | 1.27x | 1.2662 | OK |
| Yellow | FY2021 | dso_days | 47.3 days | 47.2979 | OK |
| Yellow | FY2021 | revenue_growth_pct | 13.5% | 13.4723 | OK |
| Yellow | FY2021 | cash_change_pct | -29.3% | -29.2738 | OK |
| Yellow | FY2022 | ebitda | $341.2M | 341.2000 | OK |
| Yellow | FY2022 | ebitda_margin_pct | 6.5% | 6.5056 | OK |
| Yellow | FY2022 | net_debt | $1,302.9M | 1,302.9000 | OK |
| Yellow | FY2022 | net_leverage_x | 3.82x | 3.8186 | OK |
| Yellow | FY2022 | gross_leverage_x | 4.51x | 4.5076 | OK |
| Yellow | FY2022 | interest_coverage_x | 2.09x | 2.0945 | OK |
| Yellow | FY2022 | free_cash_flow | -$70.5M | -70.5000 | OK |
| Yellow | FY2022 | net_margin_pct | 0.4% | 0.4157 | OK |
| Yellow | FY2022 | current_ratio_x | 1.27x | 1.2749 | OK |
| Yellow | FY2022 | dso_days | 41.7 days | 41.7356 | OK |
| Yellow | FY2022 | cash_conversion_x | 5.56x | 5.5642 | OK |
| Yellow | FY2022 | revenue_growth_pct | 2.4% | 2.3995 | OK |
| Yellow | FY2022 | cash_change_pct | -24.3% | -24.3322 | OK |
| Old Dominion | FY2019 | ebitda | $1,072.4M | 1,072.3870 | OK |
| Old Dominion | FY2019 | ebitda_margin_pct | 26.1% | 26.0978 | OK |
| Old Dominion | FY2019 | net_debt | -$358.6M | -358.5710 | OK |
| Old Dominion | FY2019 | net_leverage_x | -0.33x | -0.3344 | OK |
| Old Dominion | FY2019 | gross_leverage_x | 0.04x | 0.0420 | OK |
| Old Dominion | FY2019 | interest_coverage_x | 2,845x | 2,844.5279 | OK |
| Old Dominion | FY2019 | free_cash_flow | $504.6M | 504.5630 | OK |
| Old Dominion | FY2019 | net_margin_pct | 15.0% | 14.9793 | OK |
| Old Dominion | FY2019 | current_ratio_x | 2.37x | 2.3678 | OK |
| Old Dominion | FY2019 | dso_days | 35.3 days | 35.3157 | OK |
| Old Dominion | FY2019 | cash_conversion_x | 1.60x | 1.5985 | OK |
| Old Dominion | FY2020 | ebitda | $1,168.1M | 1,168.1410 | OK |
| Old Dominion | FY2020 | ebitda_margin_pct | 29.1% | 29.0935 | OK |
| Old Dominion | FY2020 | net_debt | -$301.5M | -301.4990 | OK |
| Old Dominion | FY2020 | net_leverage_x | -0.26x | -0.2581 | OK |
| Old Dominion | FY2020 | gross_leverage_x | 0.09x | 0.0855 | OK |
| Old Dominion | FY2020 | interest_coverage_x | 420x | 419.8925 | OK |
| Old Dominion | FY2020 | free_cash_flow | $707.9M | 707.9430 | OK |
| Old Dominion | FY2020 | net_margin_pct | 16.8% | 16.7537 | OK |
| Old Dominion | FY2020 | current_ratio_x | 3.33x | 3.3322 | OK |
| Old Dominion | FY2020 | dso_days | 40.4 days | 40.4217 | OK |
| Old Dominion | FY2020 | cash_conversion_x | 1.39x | 1.3870 | OK |
| Old Dominion | FY2020 | revenue_growth_pct | -2.3% | -2.2872 | OK |
| Old Dominion | FY2020 | cash_change_pct | -0.5% | -0.5305 | OK |
| Old Dominion | FY2021 | ebitda | $1,651.5M | 1,651.4850 | OK |
| Old Dominion | FY2021 | ebitda_margin_pct | 31.4% | 31.4190 | OK |
| Old Dominion | FY2021 | net_debt | -$362.6M | -362.6170 | OK |
| Old Dominion | FY2021 | net_leverage_x | -0.22x | -0.2196 | OK |
| Old Dominion | FY2021 | gross_leverage_x | 0.06x | 0.0605 | OK |
| Old Dominion | FY2021 | interest_coverage_x | 956x | 956.2739 | OK |
| Old Dominion | FY2021 | free_cash_flow | $662.5M | 662.5290 | OK |
| Old Dominion | FY2021 | net_margin_pct | 19.7% | 19.6787 | OK |
| Old Dominion | FY2021 | current_ratio_x | 2.98x | 2.9808 | OK |
| Old Dominion | FY2021 | dso_days | 39.4 days | 39.4055 | OK |
| Old Dominion | FY2021 | cash_conversion_x | 1.17x | 1.1723 | OK |
| Old Dominion | FY2021 | revenue_growth_pct | 30.9% | 30.9131 | OK |
| Old Dominion | FY2021 | cash_change_pct | 15.2% | 15.2291 | OK |
| Old Dominion | FY2022 | ebitda | $2,116.7M | 2,116.6820 | OK |
| Old Dominion | FY2022 | ebitda_margin_pct | 33.8% | 33.8124 | OK |
| Old Dominion | FY2022 | net_debt | -$86.3M | -86.3490 | OK |
| Old Dominion | FY2022 | net_leverage_x | -0.04x | -0.0408 | OK |
| Old Dominion | FY2022 | gross_leverage_x | 0.05x | 0.0472 | OK |
| Old Dominion | FY2022 | interest_coverage_x | 1,354x | 1,354.2431 | OK |
| Old Dominion | FY2022 | free_cash_flow | $916.4M | 916.4340 | OK |
| Old Dominion | FY2022 | net_margin_pct | 22.0% | 21.9991 | OK |
| Old Dominion | FY2022 | current_ratio_x | 1.76x | 1.7625 | OK |
| Old Dominion | FY2022 | dso_days | 33.7 days | 33.7386 | OK |
| Old Dominion | FY2022 | cash_conversion_x | 1.23x | 1.2283 | OK |
| Old Dominion | FY2022 | revenue_growth_pct | 19.1% | 19.0960 | OK |
| Old Dominion | FY2022 | cash_change_pct | -59.7% | -59.7219 | OK |
| Party City | FY2018 | ebitda | $356.9M | 356.8600 | OK |
| Party City | FY2018 | ebitda_margin_pct | 14.7% | 14.7006 | OK |
| Party City | FY2018 | net_debt | $1,576.4M | 1,576.3700 | OK |
| Party City | FY2018 | net_leverage_x | 4.42x | 4.4173 | OK |
| Party City | FY2018 | gross_leverage_x | 4.58x | 4.5824 | OK |
| Party City | FY2018 | interest_coverage_x | 3.38x | 3.3760 | OK |
| Party City | FY2018 | free_cash_flow | $16.2M | 16.1950 | OK |
| Party City | FY2018 | net_margin_pct | 5.1% | 5.0776 | OK |
| Party City | FY2018 | current_ratio_x | 1.44x | 1.4391 | OK |
| Party City | FY2018 | dso_days | 22.1 days | 22.1003 | OK |
| Party City | FY2018 | cash_conversion_x | 0.83x | 0.8264 | OK |
| Party City | FY2019 | ebitda | -$336.3M | -336.2770 | OK |
| Party City | FY2019 | ebitda_margin_pct | -14.3% | -14.3170 | OK |
| Party City | FY2019 | net_debt | $1,540.6M | 1,540.5940 | OK |
| Party City | FY2019 | interest_coverage_x | -2.93x | -2.9267 | OK |
| Party City | FY2019 | free_cash_flow | -$18.0M | -18.0400 | OK |
| Party City | FY2019 | net_margin_pct | -22.7% | -22.6710 | OK |
| Party City | FY2019 | current_ratio_x | 1.29x | 1.2867 | OK |
| Party City | FY2019 | dso_days | 23.2 days | 23.1714 | OK |
| Party City | FY2019 | revenue_growth_pct | -3.2% | -3.2431 | OK |
| Party City | FY2019 | cash_change_pct | -40.7% | -40.7272 | OK |
| Party City | FY2020 | ebitda | -$801.0M | -800.9950 | OK |
| Party City | FY2020 | ebitda_margin_pct | -43.3% | -43.2809 | OK |
| Party City | FY2020 | net_debt | $1,223.9M | 1,223.8520 | OK |
| Party City | FY2020 | interest_coverage_x | -10.4x | -10.3967 | OK |
| Party City | FY2020 | free_cash_flow | $26.1M | 26.0720 | OK |
| Party City | FY2020 | net_margin_pct | -28.5% | -28.5428 | OK |
| Party City | FY2020 | current_ratio_x | 1.13x | 1.1336 | OK |
| Party City | FY2020 | dso_days | 17.9 days | 17.9235 | OK |
| Party City | FY2020 | revenue_growth_pct | -21.2% | -21.2066 | OK |
| Party City | FY2020 | cash_change_pct | 242.3% | 242.3318 | OK |
| Party City | FY2021 | ebitda | $150.2M | 150.2420 | OK |
| Party City | FY2021 | ebitda_margin_pct | 6.9% | 6.9202 | OK |
| Party City | FY2021 | net_debt | $1,304.6M | 1,304.6480 | OK |
| Party City | FY2021 | net_leverage_x | 8.68x | 8.6836 | OK |
| Party City | FY2021 | gross_leverage_x | 9.00x | 9.0026 | OK |
| Party City | FY2021 | interest_coverage_x | 1.72x | 1.7224 | OK |
| Party City | FY2021 | free_cash_flow | -$27.3M | -27.2870 | OK |
| Party City | FY2021 | net_margin_pct | -0.3% | -0.3007 | OK |
| Party City | FY2021 | current_ratio_x | 1.23x | 1.2253 | OK |
| Party City | FY2021 | dso_days | 15.7 days | 15.6858 | OK |
| Party City | FY2021 | revenue_growth_pct | 17.3% | 17.3108 | OK |
| Party City | FY2021 | cash_change_pct | -59.9% | -59.9153 | OK |
| Diebold Nixdorf | FY2019 | ebitda | $199.5M | 199.5000 | OK |
| Diebold Nixdorf | FY2019 | ebitda_margin_pct | 4.5% | 4.5251 | OK |
| Diebold Nixdorf | FY2019 | net_debt | $1,860.3M | 1,860.3000 | OK |
| Diebold Nixdorf | FY2019 | net_leverage_x | 9.32x | 9.3248 | OK |
| Diebold Nixdorf | FY2019 | gross_leverage_x | 10.7x | 10.7328 | OK |
| Diebold Nixdorf | FY2019 | interest_coverage_x | 0.98x | 0.9832 | OK |
| Diebold Nixdorf | FY2019 | net_margin_pct | -7.7% | -7.7415 | OK |
| Diebold Nixdorf | FY2019 | current_ratio_x | 1.18x | 1.1828 | OK |
| Diebold Nixdorf | FY2019 | dso_days | 51.3 days | 51.2724 | OK |
| Diebold Nixdorf | FY2020 | ebitda | $97.7M | 97.7000 | OK |
| Diebold Nixdorf | FY2020 | ebitda_margin_pct | 2.5% | 2.5037 | OK |
| Diebold Nixdorf | FY2020 | net_debt | $2,021.9M | 2,021.9000 | OK |
| Diebold Nixdorf | FY2020 | net_leverage_x | 20.7x | 20.6950 | OK |
| Diebold Nixdorf | FY2020 | gross_leverage_x | 24.0x | 24.0164 | OK |
| Diebold Nixdorf | FY2020 | interest_coverage_x | 0.37x | 0.3662 | OK |
| Diebold Nixdorf | FY2020 | net_margin_pct | -6.9% | -6.8959 | OK |
| Diebold Nixdorf | FY2020 | current_ratio_x | 1.13x | 1.1260 | OK |
| Diebold Nixdorf | FY2020 | dso_days | 60.5 days | 60.5075 | OK |
| Diebold Nixdorf | FY2020 | revenue_growth_pct | -11.5% | -11.4864 | OK |
| Diebold Nixdorf | FY2020 | cash_change_pct | 15.5% | 15.5215 | OK |
| Diebold Nixdorf | FY2021 | ebitda | $183.5M | 183.5000 | OK |
| Diebold Nixdorf | FY2021 | ebitda_margin_pct | 4.7% | 4.6989 | OK |
| Diebold Nixdorf | FY2021 | net_debt | $1,903.8M | 1,903.8000 | OK |
| Diebold Nixdorf | FY2021 | net_leverage_x | 10.4x | 10.3749 | OK |
| Diebold Nixdorf | FY2021 | gross_leverage_x | 12.5x | 12.4943 | OK |
| Diebold Nixdorf | FY2021 | interest_coverage_x | 0.94x | 0.9396 | OK |
| Diebold Nixdorf | FY2021 | net_margin_pct | -2.0% | -2.0178 | OK |
| Diebold Nixdorf | FY2021 | current_ratio_x | 1.08x | 1.0788 | OK |
| Diebold Nixdorf | FY2021 | dso_days | 55.6 days | 55.6304 | OK |
| Diebold Nixdorf | FY2021 | revenue_growth_pct | 0.1% | 0.0743 | OK |
| Diebold Nixdorf | FY2021 | cash_change_pct | 19.8% | 19.8459 | OK |
| Diebold Nixdorf | FY2022 | ebitda | -$181.9M | -181.9000 | OK |
| Diebold Nixdorf | FY2022 | ebitda_margin_pct | -5.3% | -5.2562 | OK |
| Diebold Nixdorf | FY2022 | net_debt | $2,290.7M | 2,290.7000 | OK |
| Diebold Nixdorf | FY2022 | interest_coverage_x | -0.91x | -0.9132 | OK |
| Diebold Nixdorf | FY2022 | net_margin_pct | -16.8% | -16.8001 | OK |
| Diebold Nixdorf | FY2022 | current_ratio_x | 1.10x | 1.1034 | OK |
| Diebold Nixdorf | FY2022 | dso_days | 64.6 days | 64.5687 | OK |
| Diebold Nixdorf | FY2022 | revenue_growth_pct | -11.4% | -11.3823 | OK |
| Diebold Nixdorf | FY2022 | cash_change_pct | -17.9% | -17.9481 | OK |
| Saia | FY2019 | ebitda | $271.7M | 271.7210 | OK |
| Saia | FY2019 | ebitda_margin_pct | 15.2% | 15.2077 | OK |
| Saia | FY2019 | net_debt | $136.2M | 136.1820 | OK |
| Saia | FY2019 | net_leverage_x | 0.50x | 0.5012 | OK |
| Saia | FY2019 | gross_leverage_x | 0.50x | 0.5021 | OK |
| Saia | FY2019 | interest_coverage_x | 40.6x | 40.6281 | OK |
| Saia | FY2019 | free_cash_flow | -$14.8M | -14.7790 | OK |
| Saia | FY2019 | net_margin_pct | 6.4% | 6.3646 | OK |
| Saia | FY2019 | current_ratio_x | 0.96x | 0.9632 | OK |
| Saia | FY2019 | dso_days | 40.1 days | 40.0638 | OK |
| Saia | FY2019 | cash_conversion_x | 2.40x | 2.3996 | OK |
| Saia | FY2020 | ebitda | $315.0M | 314.9760 | OK |
| Saia | FY2020 | ebitda_margin_pct | 17.3% | 17.2839 | OK |
| Saia | FY2020 | net_debt | $45.7M | 45.6680 | OK |
| Saia | FY2020 | net_leverage_x | 0.14x | 0.1450 | OK |
| Saia | FY2020 | gross_leverage_x | 0.23x | 0.2253 | OK |
| Saia | FY2020 | interest_coverage_x | 60.8x | 60.8414 | OK |
| Saia | FY2020 | free_cash_flow | $78.0M | 78.0030 | OK |
| Saia | FY2020 | net_margin_pct | 7.6% | 7.5912 | OK |
| Saia | FY2020 | current_ratio_x | 0.99x | 0.9853 | OK |
| Saia | FY2020 | dso_days | 43.4 days | 43.4425 | OK |
| Saia | FY2020 | cash_conversion_x | 2.23x | 2.2347 | OK |
| Saia | FY2020 | revenue_growth_pct | 2.0% | 1.9942 | OK |
| Saia | FY2020 | cash_change_pct | 10,104.8% | 10,104.8387 | OK |
| Saia | FY2021 | ebitda | $476.8M | 476.8410 | OK |
| Saia | FY2021 | ebitda_margin_pct | 20.8% | 20.8345 | OK |
| Saia | FY2021 | net_debt | -$56.2M | -56.1840 | OK |
| Saia | FY2021 | net_leverage_x | -0.12x | -0.1178 | OK |
| Saia | FY2021 | gross_leverage_x | 0.11x | 0.1057 | OK |
| Saia | FY2021 | interest_coverage_x | 148x | 148.4561 | OK |
| Saia | FY2021 | free_cash_flow | $96.8M | 96.8460 | OK |
| Saia | FY2021 | net_margin_pct | 11.1% | 11.0646 | OK |
| Saia | FY2021 | current_ratio_x | 1.30x | 1.2953 | OK |
| Saia | FY2021 | dso_days | 44.1 days | 44.1366 | OK |
| Saia | FY2021 | cash_conversion_x | 1.51x | 1.5108 | OK |
| Saia | FY2021 | revenue_growth_pct | 25.6% | 25.5897 | OK |
| Saia | FY2021 | cash_change_pct | 321.2% | 321.1633 | OK |
| Saia | FY2022 | ebitda | $627.7M | 627.6910 | OK |
| Saia | FY2022 | ebitda_margin_pct | 22.5% | 22.4813 | OK |
| Saia | FY2022 | net_debt | -$156.4M | -156.3820 | OK |
| Saia | FY2022 | net_leverage_x | -0.25x | -0.2491 | OK |
| Saia | FY2022 | gross_leverage_x | 0.05x | 0.0494 | OK |
| Saia | FY2022 | interest_coverage_x | 240x | 240.4025 | OK |
| Saia | FY2022 | free_cash_flow | $105.6M | 105.5970 | OK |
| Saia | FY2022 | net_margin_pct | 12.8% | 12.8014 | OK |
| Saia | FY2022 | current_ratio_x | 1.94x | 1.9369 | OK |
| Saia | FY2022 | dso_days | 38.0 days | 37.9511 | OK |
| Saia | FY2022 | cash_conversion_x | 1.32x | 1.3234 | OK |
| Saia | FY2022 | revenue_growth_pct | 22.0% | 21.9929 | OK |
| Saia | FY2022 | cash_change_pct | 75.8% | 75.8078 | OK |

## Discrepancies

- None.

## Live requests made

```
2026-10-14 13:21:34 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json
2026-10-14 13:21:35 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/CashAndCashEquivalentsAtCarryingValue.json
2026-10-14 13:21:36 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/AssetsCurrent.json
2026-10-14 13:21:37 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/LiabilitiesCurrent.json
2026-10-14 13:21:38 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/DepreciationDepletionAndAmortization.json
2026-10-14 13:21:38 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/InterestExpense.json
2026-10-14 13:21:39 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/NetIncomeLoss.json
2026-10-14 13:21:40 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/NetCashProvidedByUsedInOperatingActivities.json
2026-10-14 13:21:41 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/OperatingIncomeLoss.json
2026-10-14 13:21:42 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/AccountsReceivableNetCurrent.json
2026-10-14 13:21:43 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/RevenueFromContractWithCustomerIncludingAssessedTax.json
2026-10-14 13:21:43 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000716006/us-gaap/LongTermDebt.json
2026-10-14 13:21:45 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/PaymentsToAcquireProductiveAssets.json
2026-10-14 13:21:45 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/CashAndCashEquivalentsAtCarryingValue.json
2026-10-14 13:21:46 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/AssetsCurrent.json
2026-10-14 13:21:47 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/LiabilitiesCurrent.json
2026-10-14 13:21:48 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/DepreciationAndAmortization.json
2026-10-14 13:21:49 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/InterestAndDebtExpense.json
2026-10-14 13:21:50 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/NetIncomeLoss.json
2026-10-14 13:21:50 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/NetCashProvidedByUsedInOperatingActivities.json
2026-10-14 13:21:51 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/OperatingIncomeLoss.json
2026-10-14 13:21:52 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/AccountsReceivableNetCurrent.json
2026-10-14 13:21:53 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/RevenueFromContractWithCustomerIncludingAssessedTax.json
2026-10-14 13:21:54 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/LongTermDebtAndCapitalLeaseObligations.json
2026-10-14 13:21:55 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000878927/us-gaap/LongTermDebtAndCapitalLeaseObligationsCurrent.json
2026-10-14 13:21:55 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json
2026-10-14 13:21:56 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/CashAndCashEquivalentsAtCarryingValue.json
2026-10-14 13:21:57 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/AssetsCurrent.json
2026-10-14 13:21:58 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/LiabilitiesCurrent.json
2026-10-14 13:21:59 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/DepreciationDepletionAndAmortization.json
2026-10-14 13:22:00 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/InterestExpense.json
2026-10-14 13:22:01 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/NetIncomeLoss.json
2026-10-14 13:22:01 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/NetCashProvidedByUsedInOperatingActivities.json
2026-10-14 13:22:02 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/OperatingIncomeLoss.json
2026-10-14 13:22:03 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/AccountsReceivableNetCurrent.json
2026-10-14 13:22:04 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/Revenues.json
2026-10-14 13:22:05 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/LongTermDebtAndCapitalLeaseObligations.json
2026-10-14 13:22:05 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/LongTermDebtAndCapitalLeaseObligationsCurrent.json
2026-10-14 13:22:06 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001592058/us-gaap/LongTermDebt.json
2026-10-14 13:22:07 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents.json
2026-10-14 13:22:08 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/AssetsCurrent.json
2026-10-14 13:22:09 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/LiabilitiesCurrent.json
2026-10-14 13:22:10 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/DepreciationDepletionAndAmortization.json
2026-10-14 13:22:11 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/Depreciation.json
2026-10-14 13:22:12 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/InterestExpense.json
2026-10-14 13:22:12 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/NetIncomeLoss.json
2026-10-14 13:22:13 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/NetCashProvidedByUsedInOperatingActivities.json
2026-10-14 13:22:14 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/OperatingIncomeLoss.json
2026-10-14 13:22:15 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/ReceivablesNetCurrent.json
2026-10-14 13:22:16 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/Revenues.json
2026-10-14 13:22:17 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/LongTermDebtAndCapitalLeaseObligations.json
2026-10-14 13:22:18 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0000028823/us-gaap/NotesPayableCurrent.json
2026-10-14 13:22:19 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/PaymentsToAcquirePropertyPlantAndEquipment.json
2026-10-14 13:22:20 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/CashAndCashEquivalentsAtCarryingValue.json
2026-10-14 13:22:21 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/AssetsCurrent.json
2026-10-14 13:22:22 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/LiabilitiesCurrent.json
2026-10-14 13:22:23 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/DepreciationDepletionAndAmortization.json
2026-10-14 13:22:24 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/InterestExpense.json
2026-10-14 13:22:25 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/NetIncomeLoss.json
2026-10-14 13:22:25 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/NetCashProvidedByUsedInOperatingActivities.json
2026-10-14 13:22:26 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/OperatingIncomeLoss.json
2026-10-14 13:22:27 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/AccountsReceivableNetCurrent.json
2026-10-14 13:22:28 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json
2026-10-14 13:22:28 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/LongTermDebtAndCapitalLeaseObligations.json
2026-10-14 13:22:29 UTC  200  https://data.sec.gov/api/xbrl/companyconcept/CIK0001177702/us-gaap/LongTermDebtAndCapitalLeaseObligationsCurrent.json
```
