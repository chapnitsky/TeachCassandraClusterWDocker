import uuid
import time
import queue
import threading
from datetime import datetime, timedelta
from cassandra.cluster import Cluster

cluster = Cluster(['127.0.0.1'])
session = cluster.connect('demo')
TABLE = 'birds_tracking'

q = queue.Queue()
bird_ids = [uuid.uuid4() for _ in range(10)]
base_time = datetime.utcnow()

def insert_task(bird_id, date, ts, lat, lon):
    q.put(f"""
        INSERT INTO {TABLE} (bird_id, date, timestamp, latitude, longitude)
        VALUES ({bird_id}, '{date}', '{ts}', {lat}, {lon});
    """)

def tracker_task(bird_id, date):
    q.put(f"""
        SELECT * FROM {TABLE}
        WHERE bird_id = {bird_id} AND date = '{date}'
        LIMIT 1;
    """)

def worker():
    while True:
        cql = q.get()
        if cql is None:
            break
        try:
            result = session.execute(cql)
            print(f"Executed: {cql.strip()[:60]}...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            q.task_done()

# Start thread
thread = threading.Thread(target=worker)
thread.start()

# Enqueue Bird insertions
for bird_id in bird_ids:
    for i in range(21):
        ts = base_time + timedelta(minutes=i)
        date_str = ts.strftime('%Y-%m-%d')
        insert_task(bird_id, date_str, ts.isoformat(), 30.0 + i * 0.01, 34.0 + i * 0.01)

# Enqueue tracker queries
for bird_id in bird_ids:
    date_str = base_time.strftime('%Y-%m-%d')
    tracker_task(bird_id, date_str)

q.join()
q.put(None)
thread.join()

session.shutdown()
cluster.shutdown()