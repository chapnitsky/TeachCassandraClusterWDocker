import os
import uuid
import time
from datetime import datetime, timedelta
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
from cassandra import ConsistencyLevel

# Config
CLUSTER_HOSTS = os.getenv('CLUSTER_HOSTS', 'localhost').split(',')
CASSANDRA_PORT = 9042
KEYSPACE = 'demo'
TABLE = 'birds_tracking'

cluster = Cluster(contact_points=CLUSTER_HOSTS, port=CASSANDRA_PORT)
session = cluster.connect()

# Setup
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

# --------- Bird Client ---------
bird_ids = [uuid.uuid4() for _ in range(10)]
base_time = datetime.utcnow()

def insert_bird_location(bird_id, date_str, timestamp, lat, lon):
    stmt = session.prepare(f"""
        INSERT INTO {TABLE} (bird_id, date, timestamp, latitude, longitude)
        VALUES (?, ?, ?, ?, ?)
    """)
    future = session.execute_async(stmt.bind((bird_id, date_str, timestamp, lat, lon)))
    future.add_callbacks(
        callback=lambda _: print(f"Inserted: {bird_id} @ {timestamp}"),
        errback=lambda exc: print(f"Error: {exc}")
    )
    trace = future.get_query_trace()
    print_trace(trace)

def print_trace(trace):
    if not trace: return
    print(f"[TRACE] Coordinator: {trace.coordinator}")
    for event in trace.events:
        print(f"[{event.source}] {event.description} at {event.timestamp}")

print("🚀 Bird Client Running...")
for bird_id in bird_ids:
    for i in range(21):  # Initial + 20 updates
        ts = base_time + timedelta(minutes=i)
        date_str = ts.strftime('%Y-%m-%d')
        lat = 30.0 + i * 0.01
        lon = 34.0 + i * 0.01
        insert_bird_location(bird_id, date_str, ts, lat, lon)
        time.sleep(0.1)  # simulate 1 minute delay as 0.1s

# --------- Tracker Client ---------
def query_latest_location(bird_id, date_str):
    stmt = session.prepare(f"""
        SELECT * FROM {TABLE}
        WHERE bird_id = ? AND date = ?
        LIMIT 1
    """)
    future = session.execute_async(stmt.bind((bird_id, date_str)))
    result = future.result()
    trace = future.get_query_trace()
    print_trace(trace)

    if result:
        for row in result:
            return f"{bird_id},{row.timestamp},{row.latitude},{row.longitude}"
    return None

print("\n🔍 Tracker Client Logging...")
with open("tracker_log.csv", "w") as log_file:
    log_file.write("bird_id,timestamp,latitude,longitude\n")
    for bird_id in bird_ids:
        date_str = base_time.strftime('%Y-%m-%d')
        latest = query_latest_location(bird_id, date_str)
        if latest:
            log_file.write(f"{latest}\n")

# Shutdown
session.shutdown()
cluster.shutdown()