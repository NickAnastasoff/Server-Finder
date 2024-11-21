import sqlite3


def initialize_found():
    conn = sqlite3.connect("servers.db")
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS servers (
            hash TEXT PRIMARY KEY,
            ip_str TEXT,
            port INTEGER,
            location_city TEXT,
            location_country_name TEXT,
            version TEXT,
            players_online INTEGER,
            players_max INTEGER,
            description TEXT
        )
    """
    )
    conn.commit()
    conn.close()

def initialize_starred():
    conn = sqlite3.connect("servers.db")
    c = conn.cursor()

    # Create the starred_servers table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS starred_servers (
            hash TEXT PRIMARY KEY,
            ip_str TEXT,
            port INTEGER,
            location_city TEXT,
            location_country_name TEXT,
            version TEXT,
            players_online INTEGER,
            players_max INTEGER,
            description TEXT
        )
        """
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_found()
    initialize_starred()
