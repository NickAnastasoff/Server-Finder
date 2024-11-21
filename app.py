from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
import requests
import json
import os
from init_db import initialize_found, initialize_starred

# if servers.db does not exist, create it
if not os.path.exists("servers.db"):
    initialize_found()
    initialize_starred()

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flashing messages

# Define the mode based on environment variable
DEVELOPMENT_MODE = True


@app.before_request
def skip_auth_in_dev():
    if DEVELOPMENT_MODE:
        print("Authentication skipped in development mode.")
        return  # Allows request to proceed without authentication


@app.before_request
def enforce_auth():
    if not DEVELOPMENT_MODE and request.remote_addr != "127.0.0.1":
        print("Authentication required for external IP.")
        # Implement actual authentication logic here
        # For now, we just return a simple unauthorized message
        return "Unauthorized access", 401


def get_db_connection():
    conn = sqlite3.connect("servers.db")
    conn.row_factory = sqlite3.Row
    return conn


# Configuration
CONFIG = {}
API_URL = "https://api.shodan.io/shodan/host/search"
PAGE_SIZE = 100  # Number of results per page


def load_config():
    global CONFIG
    try:
        with open("config.json") as f:
            CONFIG = json.load(f)
    except Exception as e:
        print("Failed to load config.json!")
        print(e)
        exit()


def do_request(page_num):
    api_params = {"key": CONFIG["API_KEY"], "page": page_num, "query": "Minecraft"}

    if CONFIG.get("MC_VERSION", "") != "":
        api_params["query"] += " " + CONFIG["MC_VERSION"]

    result = requests.get(API_URL, params=api_params)

    if result.status_code == 401:
        print("Error 401: Unauthorized. Check your API key.")
        return None

    result = result.json()
    if "error" in result:
        print("ERROR: " + result["error"])
        return None

    return result


def shodan_scan():
    all_servers = []
    pages = CONFIG.get("PAGES", 1)
    for page_num in range(1, pages + 1):
        resp = do_request(page_num)
        if resp is not None:
            all_servers.extend(resp.get("matches", []))
        else:
            break
    return all_servers


def update_database_with_servers(servers):
    conn = get_db_connection()
    c = conn.cursor()

    # Delete all existing servers
    c.execute("DELETE FROM servers")

    for server in servers:
        # Extract fields
        hash_value = str(server.get("hash"))
        ip_str = server.get("ip_str")
        port = server.get("port")
        # For location
        location = server.get("location", {})
        location_city = location.get("city")
        location_country_name = location.get("country_name")
        # For version
        version = server.get("version")
        # For minecraft data
        minecraft = server.get("minecraft", {})
        players = minecraft.get("players", {})
        players_online = players.get("online")
        players_max = players.get("max")

        # Handle description field
        description_field = minecraft.get("description")
        if isinstance(description_field, dict):
            description = description_field.get("text", "")
        elif isinstance(description_field, str):
            description = description_field
        else:
            description = ""

        # Insert the server into the database
        c.execute(
            """
            INSERT OR REPLACE INTO servers (
                hash, ip_str, port, location_city, location_country_name, version,
                players_online, players_max, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                hash_value,
                ip_str,
                port,
                location_city,
                location_country_name,
                version,
                players_online,
                players_max,
                description,
            ),
        )
    conn.commit()
    conn.close()


from flask import request


@app.route("/")
def index():
    """
    Home route to display the server list.
    """
    allowed_sort_columns = [
        "ip_str",
        "port",
        "location_city",
        "location_country_name",
        "version",
        "players_online",
        "players_max",
        "description",
    ]

    # Get sort parameters from query or cookies
    sort_by = request.args.get("sort") or request.cookies.get("sort", "players_online")
    if sort_by not in allowed_sort_columns:
        sort_by = "players_online"

    sort_order = request.args.get("order") or request.cookies.get("order", "asc")
    if sort_order not in ["asc", "desc"]:
        sort_order = "asc"

    filter_option = request.args.get("filter", None)  # 'starred', 'unstarred', or None

    conn = get_db_connection()

    # Build the base query with LEFT JOIN to determine star status
    query = f"""
    SELECT servers.*, 
        CASE WHEN starred_servers.hash IS NOT NULL THEN 1 ELSE 0 END AS is_starred
    FROM servers
    LEFT JOIN starred_servers ON servers.hash = starred_servers.hash
    """

    # Add WHERE clause based on filter
    if filter_option == "starred":
        query += " WHERE starred_servers.hash IS NOT NULL"
    elif filter_option == "unstarred":
        query += " WHERE starred_servers.hash IS NULL"

    # Add ORDER BY clause
    query += f" ORDER BY {sort_by} {sort_order}"

    servers = conn.execute(query).fetchall()
    conn.close()
    response = render_template(
        "index.html",
        servers=servers,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_option=filter_option,
    )
    return response


@app.route("/remove/<server_id>", methods=["POST"])
def remove_server(server_id):
    """
    Route to handle the removal of a server.
    """
    conn = get_db_connection()
    conn.execute("DELETE FROM servers WHERE hash = ?", (server_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/api/servers", methods=["GET"])
def get_servers():
    """
    API endpoint to get the current server list.
    """
    conn = get_db_connection()
    servers = conn.execute("SELECT * FROM servers").fetchall()
    conn.close()
    server_list = [dict(server) for server in servers]
    return jsonify(server_list)


@app.route("/rescan", methods=["POST"])
def rescan_servers():
    """
    Route to trigger a rescan of servers using the Shodan API.
    """
    load_config()
    if CONFIG.get("API_KEY", "") == "":
        flash("API key is not set in config.json.", "error")
        return redirect(url_for("index"))

    # Get pages parameter from the form
    pages = request.form.get("pages", type=int, default=1)
    if pages < 1 or pages > 10:
        pages = 1  # default to 1 if invalid
    CONFIG["PAGES"] = pages

    # Get query parameter from the form
    query = request.form.get("query", default="Minecraft")
    CONFIG["QUERY"] = query

    flash(
        f"Starting server rescan for {pages} page(s) with query '{query}'. This may take a few moments...",
        "info",
    )
    servers = shodan_scan()
    if servers:
        update_database_with_servers(servers)
        flash(f"Rescan complete. {len(servers)} servers found and updated.", "success")
    else:
        flash("Rescan failed. Please check the logs for details.", "error")
    return redirect(url_for("index"))


@app.route("/star/<server_id>", methods=["POST"])
def star_server(server_id):
    conn = get_db_connection()
    # Fetch server details from servers table
    server = conn.execute(
        "SELECT * FROM servers WHERE hash = ?", (server_id,)
    ).fetchone()
    if server:
        # Insert into starred_servers
        conn.execute(
            """
            INSERT OR REPLACE INTO starred_servers (
                hash, ip_str, port, location_city, location_country_name, version,
                players_online, players_max, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                server["hash"],
                server["ip_str"],
                server["port"],
                server["location_city"],
                server["location_country_name"],
                server["version"],
                server["players_online"],
                server["players_max"],
                server["description"],
            ),
        )
        conn.commit()
        flash("Server starred successfully!", "success")
    else:
        flash("Server not found.", "error")
    conn.close()
    return redirect(url_for("index"))


@app.route("/unstar/<server_id>", methods=["POST"])
def unstar_server(server_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM starred_servers WHERE hash = ?", (server_id,))
    conn.commit()
    conn.close()
    flash("Server unstarred successfully!", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=DEVELOPMENT_MODE)
