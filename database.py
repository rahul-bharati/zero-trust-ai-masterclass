import sqlite3
import random
from faker import Faker

fake = Faker('en_IN') # Using Indian locale for realistic names/addresses
DB_NAME = "vulnerable_app.db"


def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Drop existing tables if re-running
    cursor.executescript("""
                         DROP TABLE IF EXISTS internal_notes;
                         DROP TABLE IF EXISTS users;
                         DROP TABLE IF EXISTS orders;
                         """)

    # Orders Table (single-table dataset for LLM security demos)
    cursor.execute("""
                   CREATE TABLE orders (
                                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                                           customer_name TEXT,
                                           customer_email TEXT,
                                           amount REAL,
                                           item TEXT,
                                           status TEXT,
                                           shipping_address TEXT,
                                           created_at TEXT
                   )
                   """)

    print("Generating orders...")
    order_statuses = ["placed", "packed", "shipped", "delivered", "cancelled"]
    orders_data = []
    for _ in range(500):
        orders_data.append((
            fake.name(),
            fake.email(),
            round(random.uniform(100.0, 5000.0), 2),
            fake.word().capitalize(),
            random.choice(order_statuses),
            fake.address().replace('\n', ', '),
            fake.date_this_year().isoformat()
        ))

    cursor.executemany(
        """
        INSERT INTO orders (customer_name, customer_email, amount, item, status, shipping_address, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        orders_data
    )

    conn.commit()
    conn.close()
    print(f"Database {DB_NAME} created successfully. The vulnerability is live.")


if __name__ == "__main__":
    setup_database()