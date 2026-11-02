# Suspicious cluster: device D_0c947fb45bb50e72 (mobile)

## Cypher used for the screenshot
```cypher
MATCH (d:Device {device_id: "D_0c947fb45bb50e72"})<-[u:USED_DEVICE]-(c:Customer)
OPTIONAL MATCH (c)-[p:PAID]->(m:Merchant)
WHERE p.device_id = d.device_id
RETURN d, u, c, p, m
```

- Customers on this device: **3**
- Payments made from it: **19**, total **262,206.51**
- Fraud-labelled payments: **1**
- Time span: 2024-10-25T23:05 to 2024-10-29T19:48
- Merchant categories: gaming, gift_cards
- Customers' home cities: Delhi, Lucknow, Patna

## Customers
| customer           |   age | home_city   | first_used               | last_used                |   uses |
|:-------------------|------:|:------------|:-------------------------|:-------------------------|-------:|
| C_1aa451e90647f952 |    48 | Delhi       | 2024-10-25T23:05:32.631Z | 2024-10-25T23:12:37.994Z |      6 |
| C_984cb84b0a294365 |    43 | Lucknow     | 2024-10-27T06:40:22.83Z  | 2024-10-27T06:46:58.291Z |      7 |
| C_148927ad36a84923 |    28 | Patna       | 2024-10-29T19:43:34.353Z | 2024-10-29T19:48:34.771Z |      6 |

## Payments from this device
| customer           | merchant                  | category   | merchant_city   |    amount | time                     |   fraud_label |
|:-------------------|:--------------------------|:-----------|:----------------|----------:|:-------------------------|--------------:|
| C_1aa451e90647f952 | Synthetic Merchant 000185 | gaming     | Lucknow         |   4088.01 | 2024-10-25T23:05:32.631Z |             0 |
| C_1aa451e90647f952 | Synthetic Merchant 000185 | gaming     | Lucknow         |   4582.16 | 2024-10-25T23:05:55.251Z |             0 |
| C_1aa451e90647f952 | Synthetic Merchant 000185 | gaming     | Lucknow         |  10224.6  | 2024-10-25T23:06:35.495Z |             0 |
| C_1aa451e90647f952 | Synthetic Merchant 000185 | gaming     | Lucknow         |  10689.5  | 2024-10-25T23:08:24.076Z |             0 |
| C_1aa451e90647f952 | Synthetic Merchant 000185 | gaming     | Lucknow         |   9887.43 | 2024-10-25T23:11:24.332Z |             0 |
| C_1aa451e90647f952 | Synthetic Merchant 000185 | gaming     | Lucknow         | 138851    | 2024-10-25T23:12:37.994Z |             0 |
| C_984cb84b0a294365 | Synthetic Merchant 000026 | gift_cards | Kochi           |   1979.73 | 2024-10-27T06:40:22.83Z  |             0 |
| C_984cb84b0a294365 | Synthetic Merchant 000026 | gift_cards | Kochi           |   3754.59 | 2024-10-27T06:41:02.217Z |             0 |
| C_984cb84b0a294365 | Synthetic Merchant 000026 | gift_cards | Kochi           |   3340.41 | 2024-10-27T06:41:54.684Z |             0 |
| C_984cb84b0a294365 | Synthetic Merchant 000026 | gift_cards | Kochi           |   1285.19 | 2024-10-27T06:42:42.043Z |             0 |
| C_984cb84b0a294365 | Synthetic Merchant 000026 | gift_cards | Kochi           |   7497.66 | 2024-10-27T06:42:47.52Z  |             0 |
| C_984cb84b0a294365 | Synthetic Merchant 000026 | gift_cards | Kochi           |   1755.79 | 2024-10-27T06:44:52.812Z |             0 |
| C_984cb84b0a294365 | Synthetic Merchant 000026 | gift_cards | Kochi           |  32579.5  | 2024-10-27T06:46:58.291Z |             0 |
| C_148927ad36a84923 | Synthetic Merchant 000165 | gaming     | Chennai         |   2389.37 | 2024-10-29T19:43:34.353Z |             0 |
| C_148927ad36a84923 | Synthetic Merchant 000165 | gaming     | Chennai         |   2784.8  | 2024-10-29T19:44:31.647Z |             0 |
| C_148927ad36a84923 | Synthetic Merchant 000165 | gaming     | Chennai         |   1212.31 | 2024-10-29T19:44:40.425Z |             0 |
| C_148927ad36a84923 | Synthetic Merchant 000165 | gaming     | Chennai         |   6276.03 | 2024-10-29T19:47:46.947Z |             0 |
| C_148927ad36a84923 | Synthetic Merchant 000165 | gaming     | Chennai         |   2891.74 | 2024-10-29T19:48:26.485Z |             0 |
| C_148927ad36a84923 | Synthetic Merchant 000165 | gaming     | Chennai         |  16137.1  | 2024-10-29T19:48:34.771Z |             1 |
