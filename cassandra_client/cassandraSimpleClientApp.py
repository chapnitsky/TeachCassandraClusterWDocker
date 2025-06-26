import os
import sys
import uuid
import time
from datetime import datetime, timedelta
from cassandra.cluster import Cluster

# Configuration
CLUSTER_HOSTS = os.getenv("CLUSTER_HOSTS", "cassandra-1").split(",")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
KEYSPACE = "demo"
TABLE = "birds_tracking"

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
base_time = datetime.utcnow()


def print_trace(trace):
    if not trace:
        print("No trace available.")
        return
    print(f"Trace Coordinator: {trace.coordinator}")
    for event in trace.events:
        print(f"{event.source} - {event.description} at {event.timestamp}")


def run_bird_client():
    print("Running Bird Client...")
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
            future = session.execute_async(bound)
            result = future.result()
            trace = future.get_query_trace()
            print(f"Inserted bird_id {bird_id} at {ts}")
            print_trace(trace)
            time.sleep(0.1)


def run_tracker_client():
    print("Running Tracker Client...")
    with open("/app/tracker_log.csv", "w") as log_file:
        log_file.write("bird_id,timestamp,latitude,longitude\n")
        for bird_id in bird_ids:
            # Simulate tracking from the most recent insert
            ts = base_time + timedelta(minutes=20)
            date_str = ts.strftime('%Y-%m-%d')

            stmt = session.prepare(f"""
                SELECT * FROM {TABLE}
                WHERE bird_id = ? AND date = ?
                LIMIT 1
            """)
            bound = stmt.bind((bird_id, date_str))
            future = session.execute_async(bound)
            result = future.result()
            trace = future.get_query_trace()
            print_trace(trace)

            for row in result:
                log_file.write(f"{bird_id},{row.timestamp},{row.latitude},{row.longitude}\n")
                print(f"Logged latest location of bird_id {bird_id}")


if __name__ == "__main__":
    role = os.getenv("ROLE", sys.argv[1] if len(sys.argv) > 1 else "").lower()

    if not role or role not in ("bird", "tracker"):
        print("Usage: python cassandraSimpleClientApp.py [bird|tracker] or set ROLE env var")
        sys.exit(1)

    try:
        if role == "bird":
            run_bird_client()
        elif role == "tracker":
            run_tracker_client()
    finally:
        session.shutdown()
        cluster.shutdown()
