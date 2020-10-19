from cs50 import SQL

db = SQL("sqlite:///finance.db")

status = db.execute("SELECT upper(symbol) symbol, sum(shares) shares FROM history GROUP BY symbol HAVING id=4")

other = {"name": "TSLA",
    "price": 300
}

print(status)

print(other)

limit = len(status)

for row in status:

    if limit == 0:
        continue

    row.update(other)
    limit -= 1

print(status)

cash = {"symbol": "CASH", "price": 20000}

status.append(cash)

for row in status:
    print(row["price"])