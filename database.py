import sqlite3
import random
from datetime import datetime
from faker import Faker

fake = Faker('en_IN') # Using Indian locale for realistic names/addresses
DB_NAME = "vulnerable_app.db"

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Drop existing tables if re-running
    cursor.executescript("""
                         DROP TABLE IF EXISTS internal_notes;
                         DROP TABLE IF EXISTS orders;
                         DROP TABLE IF EXISTS users;
                         """)

    # 1. Users Table (The Goldmine)
    cursor.execute("""
                   CREATE TABLE users (
                                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                                          full_name TEXT,
                                          email TEXT,
                                          date_of_birth TEXT,
                                          age INTEGER,
                                          phone TEXT,
                                          address TEXT,
                                          aadhaar_number TEXT,
                                          password_plaintext TEXT,
                                          password_hash TEXT,
                                          salary INTEGER,
                                          credit_card_number TEXT,
                                          medical_notes TEXT,
                                          created_at TEXT
                   )
                   """)

    # 2. Orders Table
    cursor.execute("""
                   CREATE TABLE orders (
                                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                                           user_id INTEGER,
                                           amount REAL,
                                           item TEXT,
                                           created_at TEXT,
                                           FOREIGN KEY(user_id) REFERENCES users(id)
                   )
                   """)

    # 3. Internal Notes Table
    cursor.execute("""
                   CREATE TABLE internal_notes (
                                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                   user_id INTEGER,
                                                   note TEXT,
                                                   FOREIGN KEY(user_id) REFERENCES users(id)
                   )
                   """)

    print("Generating 300 vulnerable user records...")

    # Seed Users
    users_data = []
    for _ in range(300):
        dob = fake.date_of_birth(minimum_age=18, maximum_age=70)
        age = datetime.now().year - dob.year
        # Using a masked string format to safely simulate the ID without generating real ones
        safe_aadhaar = f"XXXX-XXXX-{random.randint(1000, 9999)}"

        users_data.append((
            fake.name(),
            fake.email(),
            dob.isoformat(),
            age,
            fake.phone_number(),
            fake.address().replace('\n', ', '),
            safe_aadhaar,
            fake.password(length=10, special_chars=False, digits=True, upper_case=True, lower_case=True), # Plaintext!
            fake.sha256(), # Hash for the illusion of security
            random.randint(300000, 2500000), # Salary in INR
            fake.credit_card_number(),
            random.choice(["None", "Allergic to penicillin", "Asthma", "High blood pressure", "None", "None"]),
            fake.date_this_decade().isoformat()
        ))

    cursor.executemany("""
                       INSERT INTO users (full_name, email, date_of_birth, age, phone, address, aadhaar_number, password_plaintext, password_hash, salary, credit_card_number, medical_notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """, users_data)

    # Seed Orders
    print("Generating orders...")
    orders_data = []
    for _ in range(500):
        orders_data.append((
            random.randint(1, 300),
            round(random.uniform(100.0, 5000.0), 2),
            fake.word().capitalize(),
            fake.date_this_year().isoformat()
        ))

    cursor.executemany("INSERT INTO orders (user_id, amount, item, created_at) VALUES (?, ?, ?, ?)", orders_data)

    # Seed Internal Notes
    print("Generating juicy internal notes...")
    juicy_notes = [
        "VIP customer, do not refund under any circumstances.",
        "Flagged for potential fraud investigation.",
        "Complains constantly, route to automated support.",
        "CEO's friend, apply 50% discount automatically.",
        "Owes us money, block next transaction."
    ]
    notes_data = []
    for _ in range(20): # Only a few users have notes
        notes_data.append((
            random.randint(1, 300),
            random.choice(juicy_notes)
        ))

    cursor.executemany("INSERT INTO internal_notes (user_id, note) VALUES (?, ?)", notes_data)

    conn.commit()
    conn.close()
    print(f"Database {DB_NAME} created successfully. The vulnerability is live.")

if __name__ == "__main__":
    setup_database()