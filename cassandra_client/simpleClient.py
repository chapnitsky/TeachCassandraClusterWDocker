import os
import sys
import uuid
import time
from datetime import datetime, timedelta
from cassandra.cluster import Cluster
import json

# Configuration
CLUSTER_HOSTS = os.getenv("CLUSTER_HOSTS", "cassandra-1").split(",")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
KEYSPACE = "demo"
TABLE = "birds_tracking"
BASE_TIME_FILE = "/app/base_time.txt"

# Connect to Cassandra
cluster = Cluster(contact_points=CLUSTER_HOSTS, port=CASSANDRA_PORT)
session = cluster.connect()

# Create keyspace and table
session.execute(f"""
    CREATE KEYSPACE IF NOT EXISTS {KEYSPACE}
    WITH REPLICATION = {{ 'class': 'SimpleStrategy', 'replication_factor': 1 }}
""")
session.set_keyspace(KEYSPACE)

session.execute(f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
        bird_id UUID,
        date text,
        timestamp timestamp,
        latitude double,
        longitude double,
        PRIMARY KEY ((bird_id, date), timestamp)
    ) WITH CLUSTERING ORDER BY (timestamp DESC);
""")

# Shared setup
bird_ids = [uuid.uuid4() for _ in range(10)]
BIRD_IDS_FILE = "/app/bird_ids.json"
base_time = datetime.utcnow()


def save_bird_ids(ids):
    with open(BIRD_IDS_FILE, "w") as f:
        json.dump([str(bid) for bid in ids], f)


def save_base_time():
    with open(BASE_TIME_FILE, "w") as f:
        f.write(base_time.isoformat())


def load_bird_ids():
    try:
        with open(BIRD_IDS_FILE) as f:
            return [uuid.UUID(bid) for bid in json.load(f)]
    except FileNotFoundError:
        return []


def load_base_time():
    global base_time
    try:
        with open(BASE_TIME_FILE) as f:
            base_time = datetime.fromisoformat(f.read().strip())
    except FileNotFoundError:
        print("⚠️  base_time.txt not found, using current time.")
        base_time = datetime.utcnow()


def print_trace(trace):
    if not trace:
        print("No trace available.")
        return
    for event in trace.events:
        print(f"Trace Coordinator: {trace.coordinator} - {event.source} - {event.description} at {event.datetime}")


def run_bird_client():
    global base_time
    save_base_time()

    for bird_id in bird_ids:
        for i in range(21):  # 1 initial + 20 updates
            ts = base_time + timedelta(minutes=i)
            date_str = ts.strftime('%Y-%m-%d')
            lat = 30.0 + i * 0.01
            lon = 34.0 + i * 0.01

            stmt = session.prepare(f"""
                INSERT INTO {TABLE} (bird_id, date, timestamp, latitude, longitude)
                VALUES (?, ?, ?, ?, ?)
            """)
            bound = stmt.bind((bird_id, date_str, ts, lat, lon))

            future = session.execute_async(bound, trace=True)
            result = future.result()
            trace = future.get_query_trace()
            print(f"Inserted: bird_id={bird_id}, date={date_str}, timestamp={ts}")
            print_trace(trace)

            time.sleep(0.1)


def run_tracker_client():
    global base_time
    load_base_time()

    with open("/app/tracker_log.csv", "w", encoding="utf-8") as log_file:
        log_file.write("bird_id,timestamp,latitude,longitude\n")

        for bird_id in bird_ids:
            ts = base_time + timedelta(minutes=20)
            date_str = ts.strftime('%Y-%m-%d')

            stmt = session.prepare(f"""
                SELECT * FROM {TABLE}
                WHERE bird_id = ? AND date = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            bound = stmt.bind((bird_id, date_str))

            future = session.execute_async(bound, trace=True)
            result = future.result()

            # Retry until trace is ready
            trace = None
            for _ in range(10):
                trace = future.get_query_trace()
                if trace and trace.events:
                    break
                time.sleep(0.2)

            print(f"\nUsed query of bird_id={bird_id} for date={date_str}")
            print_trace(trace)

            if result.current_rows:
                for row in result:
                    log_file.write(
                        f"{bird_id},{row.timestamp.isoformat()},{row.latitude},{row.longitude}\n"
                    )
                    print(f"Logged latest location for bird_id {bird_id}")
            else:
                print(f"No data found for bird_id {bird_id}")


if __name__ == "__main__":
    role = os.getenv("ROLE", sys.argv[1] if len(sys.argv) > 1 else "").lower()

    if not role or role not in ("bird", "tracker"):
        print(
            "Usage: python cassandraSimpleClientApp.py [bird|tracker] or set ROLE env var")
        sys.exit(1)

    try:
        if role == "bird":
            bird_ids = [uuid.uuid4() for _ in range(10)]
            save_bird_ids(bird_ids)
            run_bird_client()
        elif role == "tracker":
            bird_ids = load_bird_ids()
            if not bird_ids:
                print("No bird IDs found to track. Run Bird Client first.")
                sys.exit(1)
            run_tracker_client()
    finally:
        session.shutdown()
        cluster.shutdown()
