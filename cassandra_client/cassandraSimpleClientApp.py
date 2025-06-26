import os
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement
from cassandra import ConsistencyLevel

# Configuration
CLUSTER_HOSTS = os.getenv('CLUSTER_HOSTS', 'localhost').split(
    ',')  # Fetch from environment variable
CASSANDRA_PORT = 9042
KEYSPACE = 'demo'
TABLE = 'birds_tracking'

# Optional: Authentication (if enabled)
# auth_provider = PlainTextAuthProvider(username='your_username', password='your_password')
# cluster = Cluster(contact_points=CLUSTER_HOSTS, port=CASSANDRA_PORT, auth_provider=auth_provider)

# Without authentication
cluster = Cluster(contact_points=CLUSTER_HOSTS, port=CASSANDRA_PORT)
session = cluster.connect()

# Create Keyspace if it doesn't exist
session.execute(f"""
    CREATE KEYSPACE IF NOT EXISTS {KEYSPACE}
    WITH REPLICATION = {{ 'class': 'SimpleStrategy', 'replication_factor': 1 }}
""")

# Set the keyspace
session.set_keyspace(KEYSPACE)

# Create Table if it doesn't exist
session.execute("""
    CREATE TABLE IF NOT EXISTS birds_tracking (
        bird_id UUID,
        date text,
        timestamp timestamp,
        latitude double,
        longitude double,
        PRIMARY KEY ((bird_id, date), timestamp)
    ) WITH CLUSTERING ORDER BY (timestamp DESC);
""")

# Insert a new user


def insert_user(id, date, timestamp, latitude, longitude):
    insert_stmt = session.prepare(f"""
        INSERT INTO {TABLE} (bird_id, date, timestamp, latitude, longitude)
        VALUES (?, ?, ?, ?, ?)
    """)
    session.execute(insert_stmt, (id, date, timestamp, latitude, longitude))
    print(f"Inserted user: {id} {date}")

# Read user information


def get_user(lastname):
    select_stmt = session.prepare(f"""
        SELECT firstname, age, city, email FROM {TABLE} WHERE lastname = ?
    """)
    row = session.execute(select_stmt, (lastname,)).one()
    if row:
        print(
            f"User Details - First Name: {row.firstname}, Age: {row.age}, City: {row.city}, Email: {row.email}")
    else:
        print(f"No user found with lastname: {lastname}")

# Update user's age


def update_user_age(lastname, new_age):
    update_stmt = session.prepare(f"""
        UPDATE {TABLE} SET age = ? WHERE lastname = ?
    """)
    session.execute(update_stmt, (new_age, lastname))
    print(f"Updated age for user with lastname: {lastname}")

# Delete a user


def delete_user(lastname):
    delete_stmt = session.prepare(f"""
        DELETE FROM {TABLE} WHERE lastname = ?
    """)
    session.execute(delete_stmt, (lastname,))
    print(f"Deleted user with lastname: {lastname}")


# Example usage
if __name__ == "__main__":
    insert_user('Doe', 30, 'New York', 'jdoe@example.com', 'John')
    get_user('Doe')
    update_user_age('Doe', 31)
    get_user('Doe')
    delete_user('Doe')
    get_user('Doe')

    # Close the session and cluster connection
    session.shutdown()
    cluster.shutdown()
