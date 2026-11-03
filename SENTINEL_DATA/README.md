# SENTINEL: data quality, feature engineering and reason codes

Assignment steps 1 to 5 on the SENTINEL fraud data (Project Work 4 and 5): load the tables, check data quality,
build six fraud features without future leakage, assign reason codes R01 to R08, and compare everything with
the provided `features` table.

**Result in one line:** on all 1,100,000 transactions my six features and all eight reason codes match the
provided features table on **100% of rows**. Step 5b shows which common mistakes would break that and by how much.

## Files

| File | What it is |
|---|---|
| `sentinel_features.ipynb` | The notebook: all steps, every line commented, with the outputs of a full run |
| `sentinel_features.py` | The same code as a plain script |
| `outputs/` | Result CSV files from the full run (data quality, match rates, my features) |
| `screenshots/` | Screenshots of the main outputs (shown below) |
| `requirements.txt`, `.env.example` | Python packages and settings |

## Setup

1. Install Python 3.10 or newer.
2. Open a terminal (PowerShell) in this folder and install the packages:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`. The defaults already point to your tables folder:
   ```
   SOURCE=files
   DATA_PATH=C:\Users\sudha\Downloads\Sentinel project data\sentinel_data\tables
   SAMPLE_CUSTOMERS=0
   ```
   `DATA_PATH` can also point to `Sentinel project data.zip`; the code reads straight out of the zip.

### Optional: load from your own Supabase (Project Work 5)
If you loaded the data with `sql/create_table` and `python ingest.py all`, set in `.env`:
```
SOURCE=supabase
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=<your anon key>
SAMPLE_CUSTOMERS=2000
```
The script reads with the Supabase REST API, 1,000 rows per request (Supabase never returns more than 1,000
rows per call, so every read is paged). With `SAMPLE_CUSTOMERS=2000` it picks 2,000 customers and reads **all**
of their transactions, outcomes, labels and features. `SAMPLE_CUSTOMERS=0` reads every row (slow over REST:
about 4,400 requests). If your tables are not in the `public` schema, set `SUPABASE_SCHEMA` too.

Note: if your Supabase load only holds part of the transactions (the class demo loaded 100,000), the history
features will not match for customers whose earlier transactions are missing. Step 5b shows the effect.

## How to run

- **Notebook:** `jupyter notebook sentinel_features.ipynb`, then *Run All*.
- **Script:** `python sentinel_features.py`

A full run on 1.1 million rows takes about 3 to 5 minutes and needs about 4 GB of RAM.
For a quick test set `SAMPLE_CUSTOMERS=2000` (under a minute). Results are written to `outputs/`.

---

## Step 1: Load the data

All seven tables are read into pandas from the `part-*.csv.gz` files.

| Table | Rows | Columns |
|---|---:|---:|
| customers | 25,000 | 6 |
| merchants | 2,000 | 5 |
| devices | 100,120 | 3 |
| transactions | 1,100,000 | 18 |
| payment_outcomes | 1,100,000 | 5 |
| labels | 1,100,000 | 7 |
| features (provided, for step 5) | 1,100,000 | 22 |

![Tables loaded](screenshots/step1_load.png)

Only `.csv.gz` files are read. Your tables folder also holds extracted copies
(`customers/all/part-00003.csv/`, `merchants/all/part-00001.csv/`, `devices/all/part-00021.csv/` and a `.zip`).
Reading those as well would load 5,000 customers, all 2,000 merchants and the last devices part twice.

## Step 2: Data quality report

![Data quality summary](screenshots/step2_quality.png)

| Check | Result |
|---|---|
| Duplicate primary keys | 0 in every table |
| Exact duplicate rows | 0 in every table |
| Wrong types | 0 (every timestamp, number, boolean and JSON value parses as the schema says) |
| Broken links | 0 transactions with an unknown customer, merchant or device; every transaction has a label and an outcome |
| `amount_paise` vs `transaction_amount` | always equal (paise = rupees x 100) |

**Nulls (all expected, none are errors):**

| Column | Nulls | Why |
|---|---:|---|
| transactions.device_id | 10,683 (0.97%) | older UPI payments have no device fingerprint |
| transactions.customer_location | 33,067 (3.01%) | location not captured (about 3% by design) |
| transactions.average_transaction_value | 28,325 (2.58%) | customer has no transaction in the preceding 90 days (cold start) |
| payment_outcomes.failure_code | 981,435 (89.2%) | only filled when status is FAILED |
| features: ratio / new device / distance / new city / device count | same counts as above | null follows from the missing input |

**Amount outliers.** Amounts are very skewed (median Rs 1,250.64, max Rs 79,87,337.17).
The plain 1.5 x IQR rule flags 102,543 rows (9.3%) above Rs 5,966.58, which is too many to be useful on skewed data.
On the log scale the same rule flags 13,000 rows outside Rs 56.16 to Rs 28,121.49.
349 payments are above Rs 10 lakh. These are kept: they are valid payments and exactly the kind of spike R05 is for.

**Rows per split:**

| Split | Period | Rows | Fraud rate |
|---|---|---:|---:|
| warmup | Oct to Dec 2024 | 100,000 | 0.600% |
| train | Jan to Oct 2025 | 714,745 | 0.593% |
| validation | Nov to Dec 2025 | 144,803 | 0.641% |
| holdout | Jan to Feb 2026 | 140,452 | 0.595% |
| **total** | | **1,100,000** | **0.600%** |

One more finding: there are **no transactions between 05:00 and 06:00 IST**. Every other hour has transactions
(about 31,000 per night hour and 52,000 per day hour). The generator leaves that hour empty.

## Step 3: Features without future leakage

The rule that stops leakage: sort each customer's transactions by time, and for every transaction look only
**backwards**. Rolling windows use `closed="left"`, so the window is `[t - window, t)`: earlier rows are in,
the current transaction and anything later are out. The warmup split (Oct to Dec 2024) is used as history so
January 2025 transactions have a full 90 days behind them.

| Feature | How it is computed |
|---|---|
| `amount_to_average_ratio` | amount / mean amount of the customer's attempts in the preceding 90 days. Null if there are none (cold start). Rounded to 4 decimals. |
| `is_new_device` | True if this customer did not use this device in the preceding 90 days. Null when the device is unknown. |
| `customer_merchant_distance_km` | Haversine distance between customer and merchant lat/lon, earth radius 6,371 km, rounded to 2 decimals. Null when the customer location is missing. |
| `is_night` | Hour in IST (UTC + 5:30) is 0, 1, 2, 3 or 4 (00:00 inclusive to 05:00 exclusive). |
| `transaction_count_last_1_hour` | Number of the customer's earlier attempts in the last hour (failed ones included). |
| `transaction_amount_last_24_hours` | Sum of the customer's earlier attempts in the last 24 hours, in paise. |

![Features](screenshots/step3_features.png)

History counts every **authorisation attempt**, including failed ones, because at authorisation time the
system has seen the attempt whether or not it later fails.

## Step 4: Reason codes

Thresholds from the Project Work 4 class (reason code walkthrough at 00:38). The 500 km for R02 comes from the
explanation text in the data ("customer to merchant distance above 500 km").

| Code | Rule | Transactions flagged |
|---|---|---:|
| R01_NEW_DEVICE | device not seen for this customer in the preceding 90 days | 72,418 |
| R02_GEO_MISMATCH | city not seen in the preceding 90 days, or distance above 500 km | 895,465 |
| R03_ODD_HOUR | between 00:00 and 05:00 IST | 155,633 |
| R04_FAILED_ATTEMPTS | at least 3 failed attempts in the preceding 24 hours | 98,634 |
| R05_AMOUNT_SPIKE | amount at least 5 x the 90-day average | 30,690 |
| R06_NEW_ACCOUNT | account younger than 30 days | 11,541 |
| R07_VELOCITY | at least 4 preceding attempts within 1 hour | 148,480 |
| R08_HIGH_RISK_MCC | merchant category gaming, gift_cards or electronics | 324,094 |

R02 fires on 81% of transactions because customers and merchants are spread across Indian cities, so most
pairs are more than 500 km apart. In the real system this code would need a tighter rule to be useful.

![Reason codes](screenshots/step4_reason_codes.png)

## Step 5: Match rate against the provided features table

A value matches when both sides are null, or both are present and equal (within 0.0001 for the ratio and
0.01 km for the distance, because the provided table is rounded).

![Match rate](screenshots/step5_match_rate.png)

| Feature | Match rate | Mismatches |
|---|---:|---:|
| amount_to_average_ratio | 100% | 0 |
| is_new_device | 100% | 0 |
| customer_merchant_distance_km | 100% | 0 |
| is_night | 100% | 0 |
| transaction_count_last_1_hour | 100% | 0 |
| transaction_amount_last_24_hours | 100% | 0 |
| reason codes (whole list per transaction) | 100% | 0 |

The match is 100% in every split (warmup, train, validation, holdout).

### Explaining the mismatches

With the correct definitions there are no mismatches to explain. Getting there means making six choices
correctly, so step 5b recomputes each feature with one common mistake and measures how much it breaks.
Each line below is a real source of mismatches:

![Common mistakes](screenshots/step5_mistakes.png)

| Mistake | Feature | Match rate | Why it breaks |
|---|---|---:|---|
| Current transaction included in the window | ratio | 0.2% | leakage: the amount is averaged with itself |
| | 1-hour count | 0% | every count is 1 too high |
| | 24-hour amount | 0% | every sum includes the current amount |
| 30-day window instead of 90 | ratio | 11.4% | different history, different average |
| Failed attempts left out of the history | ratio | 63.0% | the provided table averages every attempt |
| | 1-hour count | 85.1% | velocity counts failed attempts too |
| Device "never seen before" (no 90-day limit) | new device | 99.1% | a device unused for over 90 days counts as new again |
| Missing device treated as new | new device | 99.0% | unknown should stay null, not True |
| Earth radius 6,378 km (equator) | distance | 9.2% | every distance about 0.1% too long, so most differ by more than 0.01 km |
| Missing location filled with 0 km | distance | 97.0% | unknown should stay null |
| Night hour taken in UTC | is_night | 63.3% | UTC 00:00 to 05:00 is 05:30 to 10:30 IST |
| Amount summed in rupees | 24-hour amount | 54.2% | the provided column is in paise (only the zero rows still match) |

**Computing on a sample without history.** If you take 5,000 random transactions and compute the features
from those rows alone, the match rate drops to 2.7% (ratio), 56.0% (1-hour count) and 53.1% (24-hour amount),
because each transaction's earlier history is missing. That is why the sample option in this project samples
**customers** and keeps all of their transactions. It is also why a partial Supabase load will not match.

**One edge case (R04, not one of the six features).** Transaction `TX_0000747401` arrives in exactly the same
millisecond as the failure outcome of the previous attempt. The provided table counts that failure (3 failures,
so R04 fires). A strict "before" rule would count 2 and miss R04. The pipeline applies an outcome once its
time is reached, so the failure counts. This is the only row in 1.1 million where it matters.
