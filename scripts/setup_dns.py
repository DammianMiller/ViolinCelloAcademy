#!/usr/bin/env python3
import json
import hmac
import hashlib
import time
import os
import subprocess
import sys

try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

API_KEY = os.environ.get("DME_API_KEY", "").strip()
API_SECRET = os.environ.get("DME_API_SECRET", "").strip()
DOMAIN_NAME = "violincelloacademy.com.au"

RECORDS = [
    {"name": "@", "type": "A", "data": "185.199.108.153", "ttl": 3600},
    {"name": "@", "type": "A", "data": "185.199.109.153", "ttl": 3600},
    {"name": "@", "type": "A", "data": "185.199.110.153", "ttl": 3600},
    {"name": "@", "type": "A", "data": "185.199.111.153", "ttl": 3600},
    {"name": "www", "type": "CNAME", "data": "damianmiller.github.io", "ttl": 3600},
]


def create_signature(method, path, timestamp, data):
    string_to_sign = f"{method}\n{path}\n{timestamp}\n{data}"
    return hmac.new(
        API_SECRET.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def make_request(method, path, data=None):
    timestamp = str(int(time.time()))
    data_str = json.dumps(data) if data else ""
    signature = create_signature(method, path, timestamp, data_str)
    url = f"https://api.dnsmadeeasy.com/v2.0{path}"

    headers = {
        "X-Auth-User": API_KEY,
        "X-Auth-Signature": signature,
        "X-Auth-Timestamp": timestamp,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        if response.status_code >= 400:
            print(f"HTTP Error {response.status_code}: {response.text}")
            response.raise_for_status()

        return response.json()
    except Exception as e:
        print(f"Request failed: {e}")
        raise


def main():
    if not API_KEY or not API_SECRET:
        print("Error: DME_API_KEY and DME_API_SECRET environment variables required")
        return 1

    print(f"Fetching domain information for {DOMAIN_NAME}...")
    try:
        domain_info = make_request("GET", f"/domains/{DOMAIN_NAME}")
        domain_id = domain_info["id"]
        print(f"Found Domain ID: {domain_id}")
    except Exception as e:
        print(
            f"Could not find domain {DOMAIN_NAME} in account. Ensure it is added to dnsmadeeasy."
        )
        return 1

    for record in RECORDS:
        print(f"Updating {record['type']} record for {record['name']}...")
        try:
            existing = make_request("GET", f"/domains/{domain_id}/records")
            found = any(
                r["name"] == record["name"]
                and r["type"] == record["type"]
                and r["data"] == record["data"]
                for r in existing
            )
            if not found:
                make_request("POST", f"/domains/{domain_id}/records", record)
                print(f"  Created: {record['name']} -> {record['data']}")
            else:
                print(f"  Already exists")
        except Exception as e:
            print(f"  Error updating record: {e}")

    print("\nDNS setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
