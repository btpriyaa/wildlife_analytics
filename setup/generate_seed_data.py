"""
generate_seed_data.py
Generates realistic synthetic data and loads it into Snowflake raw schema.
Run once to populate WILDLIFE_DEV.RAW with demo data.

Usage:
    pip install snowflake-connector-python faker python-dotenv
    python setup/generate_seed_data.py
"""
import os
import random
import uuid
from datetime import date, datetime, timedelta

import snowflake.connector
from faker import Faker
from dotenv import load_dotenv

load_dotenv()
fake = Faker()
random.seed(42)

# Configuration

SNOWFLAKE_CONFIG = {
    "account":   os.environ["SNOWFLAKE_ACCOUNT"],
    "user":      os.environ["SNOWFLAKE_USER"],
    "password":  os.environ["SNOWFLAKE_PASSWORD"],
    "role":      "transformer",
    "warehouse": "DBT_DEV_WH",
    "database":  "WILDLIFE_DEV",
    "schema":    "RAW",
}


#Generate Reference Data

ZONES = [
    ("Z01", "Safari",        "WILDLIFE",   2000),
    ("Z02", "River Parks",       "WILDLIFE",   3000),
    ("Z03", "Zoo",       "WILDLIFE",   5000),
    ("Z04", "Bird Park",       "WILDLIFE",   2500),
    ("Z05", "Mount Parks",    "NATURE",      800),
    ("Z06", "Village Restaurent",      "DINING",     1500),
    ("Z07", "Merchendise Store",   "RETAIL",      600),
    ("Z08", "Guest Services",      "FACILITIES",  200),
]

SPECIES = [
    ("ORAN", "Orangutan",          "Pongo pygmaeus",          "CR"),
    ("ELPH", "Asian Elephant",     "Elephas maximus",         "EN"),
    ("RINO", "White Rhinoceros",   "Ceratotherium simum",     "NT"),
    ("PENG", "African Penguin",    "Spheniscus demersus",     "EN"),
    ("GIRA", "Giraffe",            "Giraffa camelopardalis",  "VU"),
    ("LION", "African Lion",       "Panthera leo",            "VU"),
    ("PELT", "Pelican",            "Pelecanus conspicillatus","LC"),
    ("CROC", "Saltwater Crocodile","Crocodylus porosus",      "LC"),
    ("MAND", "Mandrill",           "Mandrillus sphinx",       "VU"),
    ("OTTER","Asian Small-clawed Otter","Aonyx cinereus",     "VU"),
]

TICKET_TYPES = [
    ("ADULT",  52.00, 0.45),
    ("CHILD",  25.00, 0.25),
    ("SENIOR", 25.00, 0.08),
    ("GROUP",  40.00, 0.12),
    ("ANNUAL", 100.00, 0.10),
]

SESSION_SLOTS = ["AM1", "AM2", "PM1", "PM2", "PM3"]
ENCOUNTER_STATUSES = ["CONFIRMED", "CANCELLED", "COMPLETED", "NO_SHOW"]
ENCOUNTER_STATUS_WEIGHTS = [0.10, 0.10, 0.70, 0.10]

START_DATE = date(2024, 1, 1)
END_DATE   = date(2026, 12, 31)

def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def generate_tickets(n: int = 50_000) -> list[tuple]:
    rows = []
    for _ in range(n):
        ticket_id   = str(uuid.uuid4())
        visitor_id  = str(uuid.uuid4())
        zone        = random.choice(ZONES)
        zone_code   = zone[0]
        visit_date  = random_date(START_DATE, END_DATE)
        txn_hour    = random.randint(8, 20)
        txn_ts      = datetime(visit_date.year, visit_date.month, visit_date.day, txn_hour,
                               random.randint(0, 59))
        # Ticket type weighted selection
        types, prices, weights = zip(*TICKET_TYPES)
        idx           = random.choices(range(len(types)), weights=weights)[0]
        ticket_type   = types[idx]
        price         = prices[idx] * random.uniform(0.90, 1.10)  # slight variance
        is_test       = random.random() < 0.01  # 1% test records
        loaded_at     = datetime.utcnow()
        rows.append((ticket_id, visitor_id, zone_code, txn_ts, ticket_type,
                     round(price, 2), is_test, loaded_at))
    return rows


def generate_encounters(ticket_rows: list[tuple], participation_rate: float = 0.25) -> list[tuple]:
    rows = []
    for ticket in ticket_rows:
        if random.random() > participation_rate:
            continue
        visitor_id  = ticket[1]
        zone_code   = ticket[2]
        visit_date  = ticket[3].date()
        encounter_id = str(uuid.uuid4())
        species_code = random.choice(SPECIES)[0]
        session_slot = random.choice(SESSION_SLOTS)
        status       = random.choices(ENCOUNTER_STATUSES, weights=ENCOUNTER_STATUS_WEIGHTS)[0]
        loaded_at    = datetime.utcnow()
        rows.append((encounter_id, visitor_id, species_code, zone_code,
                     visit_date, session_slot, status, loaded_at))
    return rows


def load_to_snowflake(conn, table: str, columns: list[str], rows: list[tuple]) -> None:
    placeholders = ", ".join(["%s"] * len(columns))
    col_list     = ", ".join(columns)
    sql          = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    cursor = conn.cursor()
    batch_size = 5000
    for i in range(0, len(rows), batch_size):
        cursor.executemany(sql, rows[i:i + batch_size])
        print(f"  Loaded {min(i + batch_size, len(rows))}/{len(rows)} rows into {table}")
    cursor.close()


def main():
    print("Connecting to Snowflake...")
    conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
    cur  = conn.cursor()

    # Create Raw Tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS park_zones (
            zone_code       VARCHAR(10)  NOT NULL,
            zone_name       VARCHAR(100) NOT NULL,
            zone_category   VARCHAR(50)  NOT NULL,
            max_capacity    INTEGER      NOT NULL,
            updated_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS species (
            species_code        VARCHAR(10)  NOT NULL,
            common_name         VARCHAR(100) NOT NULL,
            scientific_name     VARCHAR(150),
            conservation_status VARCHAR(5)   NOT NULL,
            updated_at          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ticket_transactions (
            ticket_id       VARCHAR(36)   NOT NULL,
            visitor_id      VARCHAR(36)   NOT NULL,
            park_zone_code  VARCHAR(10)   NOT NULL,
            txn_ts          TIMESTAMP_NTZ NOT NULL,
            ticket_type_cd  VARCHAR(10)   NOT NULL,
            ticket_price_sgd FLOAT,
            is_test_record  BOOLEAN       DEFAULT FALSE,
            _loaded_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS animal_encounters (
            encounter_id    VARCHAR(36)  NOT NULL,
            visitor_id      VARCHAR(36)  NOT NULL,
            species_code    VARCHAR(10)  NOT NULL,
            zone_code       VARCHAR(10)  NOT NULL,
            encounter_date  DATE         NOT NULL,
            session_slot    VARCHAR(5)   NOT NULL,
            status          VARCHAR(20)  NOT NULL,
            _loaded_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)

    # Load reference data
    print("\nLoading park_zones...")
    cur.executemany(
        "INSERT INTO park_zones (zone_code, zone_name, zone_category, max_capacity) VALUES (%s,%s,%s,%s)",
        [(z[0], z[1], z[2], z[3]) for z in ZONES]
    )

    print("Loading species...")
    cur.executemany(
        "INSERT INTO species (species_code, common_name, scientific_name, conservation_status) VALUES (%s,%s,%s,%s)",
        [(s[0], s[1], s[2], s[3]) for s in SPECIES]
    )

    # Generate and load transactional data
    print("\nGenerating 50,000 ticket transactions...")
    tickets = generate_tickets(50_000)
    load_to_snowflake(conn, "ticket_transactions",
                      ["ticket_id","visitor_id","park_zone_code","txn_ts",
                       "ticket_type_cd","ticket_price_sgd","is_test_record","_loaded_at"],
                      tickets)

    print("\nGenerating encounter bookings (25% participation)...")
    encounters = generate_encounters(tickets, participation_rate=0.25)
    load_to_snowflake(conn, "animal_encounters",
                      ["encounter_id","visitor_id","species_code","zone_code",
                       "encounter_date","session_slot","status","_loaded_at"],
                      encounters)

    conn.commit()
    conn.close()

    print(f"\nDone! Loaded:")
    print(f"  {len(ZONES)} zones")
    print(f"  {len(SPECIES)} species")
    print(f"  {len(tickets):,} ticket transactions")
    print(f"  {len(encounters):,} encounter bookings")


if __name__ == "__main__":
    main()
