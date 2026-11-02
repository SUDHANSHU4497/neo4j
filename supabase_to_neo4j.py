"""
Step 2: build the SENTINEL fraud graph in Neo4j from my own Supabase load.

    Supabase (Project Work 5: sql/create_table + python ingest.py all)
        transactions, labels, customers, devices, merchants
            |
            v   read with the Supabase REST API (1,000 rows per request)
        pandas: join fraud_label onto each transaction
            |
            v   MERGE in batches of 1,000
        Neo4j:
        (:Customer)-[:USED_DEVICE]->(:Device)
        (:Customer)-[:PAID {amount, time, fraud_label}]->(:Merchant)

Run:  python step2_supabase_to_neo4j.py
Needs in .env:  NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, SUPABASE_URL, SUPABASE_KEY
Optional:       SAMPLE_SIZE (default 10000, must be at least 5000)
"""
import json
import os

import pandas as pd
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# ---------------------------------------------------------------------------
# 0. Settings
# ---------------------------------------------------------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

SUPABASE_URL = os.environ["SUPABASE_URL"].strip().strip('"').rstrip("/")   # https://<project>.supabase.co
if SUPABASE_URL.endswith("/rest/v1"):   # accept the URL with or without /rest/v1
    SUPABASE_URL = SUPABASE_URL[: -len("/rest/v1")]
SUPABASE_KEY = os.environ["SUPABASE_KEY"].strip().strip('"')             # Project Settings > API > anon key
SAMPLE_SIZE = int(os.getenv("SAMPLE_SIZE", "10000"))     # the task asks for at least 5,000

PAGE = 1000    # Supabase returns at most 1,000 rows per request
BATCH = 1000   # rows sent to Neo4j per query

REST = f"{SUPABASE_URL}/rest/v1/"
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


# ---------------------------------------------------------------------------
# 1. Read from Supabase
# ---------------------------------------------------------------------------
def supabase_get(table, params):
    """One GET request to the Supabase REST API. Returns a list of rows (dicts)."""
    r = requests.get(REST + table, headers=HEADERS, params=params, timeout=60)
    r.raise_for_status()  # stops with a clear error if the URL, key or table name is wrong
    return r.json()


def read_transactions(n):
    """Read the first n transactions, ordered by transaction_id, one page of 1,000 at a time."""
    rows = []
    while len(rows) < n:
        page = supabase_get("transactions", {
            "select": "transaction_id,customer_id,merchant_id,device_id,"
                      "transaction_amount,payment_channel,transaction_time",
            "order": "transaction_id",
            "limit": min(PAGE, n - len(rows)),
            "offset": len(rows),
        })
        if not page:          # no more rows in the table
            break
        rows += page
        print(f"  transactions read: {len(rows):,}")
    return pd.DataFrame(rows)


def read_by_ids(table, id_column, ids, select="*"):
    """Read only the rows whose id is in `ids` (200 ids per request so the URL stays short)."""
    ids = list(dict.fromkeys(str(x) for x in ids if pd.notna(x)))  # unique, no blanks, keeps order
    rows = []
    for i in range(0, len(ids), 200):
        chunk = ",".join(ids[i:i + 200])
        rows += supabase_get(table, {"select": select, id_column: f"in.({chunk})"})
    return pd.DataFrame(rows)


print("Reading from Supabase:", SUPABASE_URL)
tx = read_transactions(SAMPLE_SIZE)
labels = read_by_ids("labels", "transaction_id", tx["transaction_id"], "transaction_id,fraud_label")
customers = read_by_ids("customers", "customer_id", tx["customer_id"])
devices = read_by_ids("devices", "device_id", tx["device_id"])
merchants = read_by_ids("merchants", "merchant_id", tx["merchant_id"])

# ---------------------------------------------------------------------------
# 2. Prepare the data with pandas
# ---------------------------------------------------------------------------
# fraud_label lives in the labels table: join it on transaction_id (missing label = 0, genuine)
tx = tx.merge(labels, on="transaction_id", how="left")
tx["fraud_label"] = tx["fraud_label"].fillna(0).astype(int)
tx["transaction_time"] = pd.to_datetime(tx["transaction_time"], utc=True, format="ISO8601")  # some have fractional seconds, some don't
tx = tx.sort_values("transaction_time")

print(f"\nSample: {len(tx):,} transactions | {len(customers):,} customers | {len(devices):,} devices | "
      f"{len(merchants):,} merchants | {tx['fraud_label'].sum():,} fraud | "
      f"{tx['transaction_time'].min():%Y-%m-%d} to {tx['transaction_time'].max():%Y-%m-%d}")
if len(tx) < 5000:
    raise SystemExit("Fewer than 5,000 transactions: check that ingest.py all loaded the transactions table.")


def city(location_json):
    """merchant_location is stored as JSON text like {"city":"Delhi","lat":..,"lon":..}."""
    try:
        return json.loads(location_json).get("city")
    except (TypeError, ValueError):
        return location_json.get("city") if isinstance(location_json, dict) else None


customer_rows = [{"id": r["customer_id"], "age": int(r["customer_age"]),
                  "city": r.get("home_city"), "region": r.get("region")}
                 for r in customers.to_dict("records")]

device_rows = [{"id": r["device_id"], "kind": r.get("device_kind")}
               for r in devices.to_dict("records")]

merchant_rows = [{"id": r["merchant_id"], "name": r.get("synthetic_name"),
                  "category": r.get("merchant_category"), "city": city(r.get("merchant_location"))}
                 for r in merchants.to_dict("records")]

# USED_DEVICE: one edge per (customer, device), with every time that device was used
used = (tx.groupby(["customer_id", "device_id"])["transaction_time"]
          .apply(lambda s: [t.isoformat() for t in s])
          .reset_index(name="times"))
used_rows = used.to_dict("records")

# PAID: one edge per transaction, with amount, time and fraud_label
paid_rows = [{"tx": r["transaction_id"], "c": r["customer_id"], "m": r["merchant_id"],
              "d": r["device_id"] if pd.notna(r["device_id"]) else None,  # some transactions have no device
              "amount": float(r["transaction_amount"]), "time": r["transaction_time"].isoformat(),
              "fraud": int(r["fraud_label"]), "channel": r["payment_channel"]}
             for r in tx.to_dict("records")]

# ---------------------------------------------------------------------------
# 3. Connect to Neo4j
# ---------------------------------------------------------------------------
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
driver.verify_connectivity()
print("\nConnected to Neo4j:", NEO4J_URI)


def run(query, **params):
    records, _, _ = driver.execute_query(query, params)
    return [r.data() for r in records]


def write_in_batches(query, rows, name):
    for i in range(0, len(rows), BATCH):
        run(query, rows=rows[i:i + BATCH])
    print(f"  {name}: {len(rows):,} rows merged")


# ---------------------------------------------------------------------------
# 4. Uniqueness constraints (also create the indexes MERGE uses to find ids fast)
# ---------------------------------------------------------------------------
run("CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE")
run("CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.device_id IS UNIQUE")
run("CREATE CONSTRAINT merchant_id IF NOT EXISTS FOR (m:Merchant) REQUIRE m.merchant_id IS UNIQUE")
run("CREATE CONSTRAINT paid_tx_id IF NOT EXISTS FOR ()-[p:PAID]-() REQUIRE p.transaction_id IS UNIQUE")

# ---------------------------------------------------------------------------
# 5. Nodes: MERGE on the id, then SET the other properties
# ---------------------------------------------------------------------------
print("\nLoading nodes")
write_in_batches("""
UNWIND $rows AS row
MERGE (c:Customer {customer_id: row.id})
SET c.customer_age = row.age, c.home_city = row.city, c.region = row.region
""", customer_rows, "Customer")

write_in_batches("""
UNWIND $rows AS row
MERGE (d:Device {device_id: row.id})
SET d.device_kind = row.kind
""", device_rows, "Device")

write_in_batches("""
UNWIND $rows AS row
MERGE (m:Merchant {merchant_id: row.id})
SET m.name = row.name, m.merchant_category = row.category, m.city = row.city
""", merchant_rows, "Merchant")

# ---------------------------------------------------------------------------
# 6. Relationships
# ---------------------------------------------------------------------------
print("\nLoading relationships")
write_in_batches("""
UNWIND $rows AS row
MATCH (c:Customer {customer_id: row.customer_id})
MATCH (d:Device   {device_id:   row.device_id})
MERGE (c)-[u:USED_DEVICE]->(d)
SET u.times      = [t IN row.times | datetime(t)],
    u.first_seen = datetime(row.times[0]),
    u.last_seen  = datetime(row.times[-1]),
    u.tx_count   = size(row.times)
""", used_rows, "USED_DEVICE")

write_in_batches("""
UNWIND $rows AS row
MATCH (c:Customer {customer_id: row.c})
MATCH (m:Merchant {merchant_id: row.m})
MERGE (c)-[p:PAID {transaction_id: row.tx}]->(m)
SET p.amount          = row.amount,
    p.time            = datetime(row.time),
    p.fraud_label     = row.fraud,
    p.payment_channel = row.channel,
    p.device_id       = row.d
""", paid_rows, "PAID")

# ---------------------------------------------------------------------------
# 7. Check what is in the graph
# ---------------------------------------------------------------------------
print("\nGraph now contains:")
for label in ["Customer", "Device", "Merchant"]:
    print(f"  (:{label}) nodes:", run(f"MATCH (n:{label}) RETURN count(n) AS n")[0]["n"])
for rel in ["USED_DEVICE", "PAID"]:
    print(f"  [:{rel}] edges:", run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n")[0]["n"])
print("  fraud PAID edges:", run("MATCH ()-[p:PAID {fraud_label: 1}]->() RETURN count(p) AS n")[0]["n"])

print("\nSample PAID edges:")
for row in run("""
MATCH (c:Customer)-[p:PAID]->(m:Merchant)
RETURN c.customer_id AS customer, m.merchant_category AS category,
       p.amount AS amount, toString(p.time) AS time, p.fraud_label AS fraud_label
ORDER BY p.fraud_label DESC, p.time LIMIT 5"""):
    print(" ", row)

driver.close()
print("\nDone. Run it again: the counts stay the same (MERGE, no duplicates).")
