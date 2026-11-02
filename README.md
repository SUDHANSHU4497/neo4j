SENTINEL fraud graph on Neo4j
Neo4j assignment, steps 1 to 5, using the SENTINEL fraud data from Project Work 4 and 5.

Files
sentinel_neo4j.py: the whole assignment as a script (steps 1 to 5)
sentinel_neo4j.ipynb: the same code as a notebook (click Run All)
queries.cypher: the constraints, the three fraud queries and the screenshot query, ready to paste into Neo4j Browser
docker-compose.yml: starts Neo4j locally on ports 7474 and 7687
requirements.txt, .env.example
cluster_report.md: written by the script on each run, with the facts for the step 5 explanation
How to run
1. Start Neo4j (pick one)
Docker (local). Install Docker Desktop, then in this folder:

docker compose up -d
or without the compose file:

docker run -d --name sentinel-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/sentinel123 neo4j:5.26-community
Port 7474 is Neo4j Browser (open http://localhost:7474, log in with neo4j / sentinel123). Port 7687 is Bolt, which the Python driver uses (neo4j://localhost:7687).

Aura (cloud). Go to console.neo4j.io, create a free instance and download the credentials file when it is shown (the password is only shown once). Use its NEO4J_URI (looks like neo4j+s://xxxxxxxx.databases.neo4j.io), NEO4J_USERNAME and NEO4J_PASSWORD. Open the instance with “Query” to get the graph view.

2. Run the script
pip install -r requirements.txt
Copy .env.example to .env and set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
Choose where the data comes from:
SOURCE=files (default): set DATA_PATH to Sentinel project data.zip (default C:\Users\sudha\Downloads\Sentinel project data.zip) or to the unzipped sentinel_data\tables folder. These are the same CSV files that python ingest.py all loads into Supabase.
SOURCE=supabase: set SUPABASE_URL and SUPABASE_KEY (the ones from your .env in the Project Work 5 kit). The script reads the transactions, labels, customers, devices and merchants tables through the Supabase REST API, 1,000 rows per request.
python sentinel_neo4j.py, or open the notebook and click Run All.
Each run is safe to repeat: nothing is deleted and nothing is duplicated (see step 3). To start from an empty graph, run MATCH (n) DETACH DELETE n in Browser.

Step 1: Connect from Python
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
driver.verify_connectivity()
verify_connectivity() opens a connection and checks the login. If the URI, port or password is wrong it raises an error straight away, instead of failing later in the middle of the load. The script then prints the server version (for example Neo4j/5.26).

The same code works for Docker and Aura. Only the URI changes: neo4j://localhost:7687 for Docker, neo4j+s://... for Aura (the +s means the connection is encrypted, which Aura requires).

Step 2: Graph model and data
Which data, and how much
The Excel files in sentinel_excel are only previews (8 to 10 rows per table), so they are not enough for this task. The sample comes from the full SENTINEL data instead:

Default: the first 2 part files of transactions/train and labels/train = 10,000 transactions (each part file has 5,000 rows), which is above the 5,000 the task asks for. Change NUM_PARTS to load more.
Or the same rows from your own Supabase load (SOURCE=supabase, SAMPLE_SIZE=10000).
The fraud label comes from the labels table (joined on transaction_id), device kind from devices, merchant name, category and city from merchants, and customer age and home city from customers. Only customers, devices and merchants that appear in the sample are loaded. The script stops with an error if the sample has fewer than 5,000 transactions.

Nodes and relationships
(:Customer {customer_id, customer_age, home_city, region})
(:Device   {device_id, device_kind})
(:Merchant {merchant_id, name, merchant_category, city})

(:Customer)-[:USED_DEVICE {times, first_seen, last_seen, tx_count}]->(:Device)
(:Customer)-[:PAID {transaction_id, amount, time, fraud_label, payment_channel, device_id}]->(:Merchant)
Why a payment is an edge (PAID) and not a node. The task asks for amount, time and fraud_label on the PAID edge. A payment always joins exactly one customer to one merchant, so an edge with properties is the simplest way to show it, and the graph view shows who paid whom directly.

Why one USED_DEVICE edge per customer and device. A customer often uses the same device many times. One edge per pair keeps the picture clean (one line between a customer and their phone), and the edge keeps the list of times it was used, plus first_seen, last_seen and tx_count. The times are needed for the 7-day query.

Why PAID also stores device_id. The PAID edge goes customer to merchant, so on its own it does not say which device the payment came from. Storing device_id on it lets query 3 count payments made from a shared device.

Times are stored as Neo4j datetime values (not text), so they can be compared and added to duration({days: 7}).

Step 3: MERGE, not CREATE, and uniqueness constraints
Constraints
CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE;
CREATE CONSTRAINT device_id   IF NOT EXISTS FOR (d:Device)   REQUIRE d.device_id   IS UNIQUE;
CREATE CONSTRAINT merchant_id IF NOT EXISTS FOR (m:Merchant) REQUIRE m.merchant_id IS UNIQUE;
CREATE CONSTRAINT paid_tx_id  IF NOT EXISTS FOR ()-[p:PAID]-() REQUIRE p.transaction_id IS UNIQUE;
A uniqueness constraint makes Neo4j refuse a second node with the same id, so duplicates are impossible even if some other code uses CREATE by mistake.
Each constraint also builds an index on the id. MERGE has to look up the id before deciding whether to create, so without the index every MERGE would scan all nodes and the load would get slower and slower.
The fourth constraint does the same for payments: one PAID edge per transaction_id (relationship uniqueness constraints need Neo4j 5.7 or newer, which both the Docker image and Aura are).
IF NOT EXISTS lets the script run again without an error.
MERGE
UNWIND $rows AS row
MERGE (c:Customer {customer_id: row.id})
SET c.customer_age = row.age, c.home_city = row.city, c.region = row.region
UNWIND $rows AS row
MATCH (c:Customer {customer_id: row.c})
MATCH (m:Merchant {merchant_id: row.m})
MERGE (c)-[p:PAID {transaction_id: row.tx}]->(m)
SET p.amount = row.amount, p.time = datetime(row.time), p.fraud_label = row.fraud, ...
CREATE always makes a new node or edge, so running the load twice would give two copies of every customer and payment.
MERGE first looks for a match on the key (customer_id, or transaction_id for PAID) and only creates it if it is not there. On the second run everything already exists, so nothing new is made.
MERGE is done on the id only, and the other properties are written with SET afterwards. If MERGE used all properties and one changed (say a corrected amount), it would not match and would make a duplicate.
Values are always set, never added to (for example u.tx_count = size(row.times), not u.tx_count = u.tx_count + 1), so a rerun does not change the numbers.
Rows are sent in batches of 1,000 with UNWIND $rows, which is much faster than one query per row.
Proof
Step 3c in the script runs the PAID load a second time and prints the node and edge counts before and after. They are the same, and it prints no duplicates: True. Running the whole script twice gives the same counts as well.

Step 4: Fraud queries
All three are in queries.cypher and in the script.

Q1. Devices shared by 3 or more customers in 7 days
MATCH (d:Device)<-[:USED_DEVICE]-(:Customer)
WITH d, count(*) AS total_customers
WHERE total_customers >= 3
MATCH (d)<-[u:USED_DEVICE]-(c:Customer)
UNWIND u.times AS t
WITH d, collect({customer: c.customer_id, time: t}) AS uses
UNWIND uses AS start
WITH d, start.time AS window_start,
     [x IN uses WHERE x.time >= start.time AND x.time < start.time + duration({days: 7}) | x.customer] AS in_window
UNWIND in_window AS customer
WITH d, window_start, collect(DISTINCT customer) AS customers
WHERE size(customers) >= 3
WITH d, window_start, customers
ORDER BY size(customers) DESC, window_start
WITH d, collect({start: window_start, customers: customers})[0] AS best
RETURN d.device_id AS device_id, d.device_kind AS device_kind,
       size(best.customers) AS customers_in_window,
       toString(date(best.start)) AS window_start, best.customers AS customer_ids
ORDER BY customers_in_window DESC, window_start
LIMIT 25
How it works.

Keep only devices that have 3 or more customers at all (a quick filter, so the rest of the query only looks at a few devices).
List every use of the device: which customer, and when.
Treat each use as the start of a 7-day window and count the distinct customers who used the device inside that window.
Keep windows with 3 or more customers, and for each device report the busiest window.
The 7 days are a sliding window, not calendar weeks, so 3 customers on Sunday, Monday and Tuesday are caught even though they cross a week boundary.

Why it matters. A phone or browser normally belongs to one person, maybe a family. Many different customers on one device within a few days is a classic sign of account takeover or a fraud ring, where one person runs many stolen or mule accounts from the same phone.

Q2. Customers within 2 hops of a fraud-labelled payment
MATCH (fc:Customer)-[:PAID {fraud_label: 1}]->(:Merchant)
WITH DISTINCT fc
MATCH (fc)-[:USED_DEVICE|PAID]-(link)-[:USED_DEVICE|PAID]-(c:Customer)
WHERE c <> fc
RETURN c.customer_id AS customer_id,
       count(DISTINCT fc) AS fraud_customers_nearby,
       count(DISTINCT CASE WHEN link:Device THEN link END) AS shared_devices,
       count(DISTINCT CASE WHEN link:Merchant THEN link END) AS shared_merchants,
       EXISTS { (c)-[:PAID {fraud_label: 1}]->() } AS has_own_fraud
ORDER BY shared_devices DESC, fraud_customers_nearby DESC, shared_merchants DESC
LIMIT 25
How it works. Start from every customer who made a payment with fraud_label = 1. Two hops away from them there are two kinds of customer:

customer -> Device <- customer: someone who used the same device as the fraud customer.
customer -> Merchant <- customer: someone who paid the same merchant.
For each nearby customer the query counts how many fraud customers they are near, through how many shared devices and how many shared merchants, and whether they have a fraud payment of their own.

How to read it. A shared device is a strong link (the same physical phone). A shared merchant is a weak link, because a popular merchant is paid by many honest customers too. That is why the results are sorted by shared devices first, and why queries.cypher also has a stricter version that only follows shared devices. Customers near a fraud payment who are not yet labelled fraud themselves (has_own_fraud = false) are the ones to send to review: labels are only final about 60 days after the payment, so some of them may turn out to be fraud too.

Q3. Merchants most often paid from shared devices
MATCH (d:Device)<-[:USED_DEVICE]-(:Customer)
WITH d, count(*) AS n_customers
WHERE n_customers >= 2
MATCH (d)<-[:USED_DEVICE]-(c:Customer)-[p:PAID]->(m:Merchant)
WHERE p.device_id = d.device_id
RETURN m.merchant_id AS merchant_id, m.name AS merchant, m.merchant_category AS category,
       count(p) AS payments_from_shared_devices,
       count(DISTINCT d) AS shared_devices,
       count(DISTINCT c) AS customers,
       sum(p.fraud_label) AS fraud_payments,
       round(sum(p.amount), 2) AS total_amount
ORDER BY payments_from_shared_devices DESC, fraud_payments DESC
LIMIT 10
How it works. A shared device is one used by 2 or more customers. For each such device, find the payments made from it (p.device_id = d.device_id makes sure the payment was made on that device, not on another of the customer’s devices), then count them per merchant.

Why it matters. Fraudsters cash out where goods are easy to resell or the money is hard to trace, so the merchants at the top of this list (often gift cards, gaming and electronics in SENTINEL, which also have the highest fraud rates) are where a fraud ring is spending. The fraud_payments column shows how many of those payments are already confirmed fraud.

Step 5: Screenshot of one suspicious cluster
How to take it
Run the script. At the end it prints a Cypher query for the most suspicious device (the top device from Q1) and writes cluster_report.md with its customers and payments.
Open Neo4j Browser (http://localhost:7474, or “Query” in Aura) and paste the printed query. It looks like:
MATCH (d:Device {device_id: "D_..."})<-[u:USED_DEVICE]-(c:Customer)
OPTIONAL MATCH (c)-[p:PAID]->(m:Merchant)
WHERE p.device_id = d.device_id
RETURN d, u, c, p, m
Make the picture readable:
Click the Customer, Device and Merchant labels at the top of the result and pick a different colour for each (for example device red, customers blue, merchants green).
Set the caption: Customer = customer_id, Device = device_kind, Merchant = merchant_category.
Click the PAID relationship type and set its caption to fraud_label (or amount), so you can see which payments are fraud.
Drag the device to the middle so the star shape is clear.
Take the screenshot (Windows: Win + Shift + S), or use the download icon on the result panel to save it as PNG or SVG.
Click a fraud PAID edge before the screenshot if you want its properties (amount, time, fraud_label) shown in the side panel.
What to write (use the numbers from cluster_report.md)
Fill in the brackets from your own run:

The screenshot shows device [device_id] (a [mobile/browser]) in the middle, with [N] customers connected to it by USED_DEVICE edges, all within [7 days / the dates]. Each customer then has PAID edges to the merchants they paid from this device: [M] payments worth [total] in total, [F] of them labelled fraud.

This is suspicious because a single device normally belongs to one person. Here [N] different customers, with different ages and home cities ([cities]), all paid from the same [phone/browser] within a few days. Most of them used it only once or twice, which looks like one person logging into many accounts rather than a shared family device. The payments go mostly to [categories, e.g. gift_cards / gaming / electronics], which are easy to resell and have the highest fraud rates in SENTINEL.

[F] of the payments are already confirmed fraud. The other customers on this device are not labelled fraud yet, but they are only one hop from the device and two hops from a fraud payment (Q2), so they should be reviewed: labels in SENTINEL are only final about 60 days after a payment. This is something a model that looks at one transaction at a time would miss, because each payment on its own can look normal. Seeing the payments as a graph shows they all come from the same device.

Next steps: block the device (SENTINEL’s list_entries has a blocked_devices list), send the unlabelled customers to manual review, and add “number of customers on this device in the last 7 days” as a model feature.

If Q1 finds nothing in your sample, the script falls back to the device with the most customers. Q1 can also come back empty if the sample covers only a few days; set NUM_PARTS=4 (20,000 transactions) or more and run again.

Results from my run
The script prints every number below; copy them in after running on your data.

Sample: [10,000] transactions, [ ] customers, [ ] devices, [ ] merchants, [ ] fraud, dates [ ] to [ ].
Constraints: 4 (Customer, Device, Merchant ids, PAID transaction_id).
Rerun: counts before and after are the same (no duplicates: True).
Q1: [ ] devices shared by 3+ customers within 7 days; the top one had [ ] customers.
Q2: [ ] customers within 2 hops of a fraud payment, [ ] of them through a shared device.
Q3: top merchant [ ] ([category]) with [ ] payments from shared devices, [ ] of them fraud.
