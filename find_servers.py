import requests
import json

API_URL = "https://api.shodan.io/shodan/host/search"
PAGE_SIZE = 100
CONFIG = {}


def do_request(page_num):
    api_params = {"key": CONFIG["API_KEY"], "page": page_num, "query": "Minecraft"}

    if CONFIG["MC_VERSION"] != "":
        api_params["query"] = "Minecraft " + CONFIG["MC_VERSION"]

    result = requests.get(API_URL, params=api_params)

    if result.status_code == 401:
        print("Error 401")
        exit()

    result = result.json()
    if "error" in result:
        print("ERROR: " + result["error"])
        return None

    return result


def parse_page(page_json):
    result = []
    for server in page_json["matches"]:
        if CONFIG["ACTIVE_ONLY"]:
            if "Online Players: 0" in server["data"]:
                continue

        ip = server["ip_str"]
        port = str(server["port"])
        result.append(ip + ":" + port)
    return result


if __name__ == "__main__":
    try:
        with open("config.json") as f:
            CONFIG = json.loads(f.read())
    except Exception as e:
        print("Failed to load config.json!")
        print(e)
        exit()

    if CONFIG["API_KEY"] == "":
        print("put your API key in config.json.")
        exit()

    print("finding servers...")
    server_results = []
    for i in range(CONFIG["PAGES"]):
        resp = do_request(i + 1)
        with open("resp.json", "w") as f:
            f.write(json.dumps(resp))

        if resp is not None:
            ips = parse_page(resp)
            server_results.extend(ips)

    if CONFIG["OUTPUT_FILE"] == "":
        for ip in server_results:
            print(ip)
    else:
        try:
            with open(CONFIG["OUTPUT_FILE"], "w") as f:
                for ip in server_results:
                    f.write(ip + "\n")
        except Exception as e:
            print("Failed to open output file!")
            print(e)
            exit()
