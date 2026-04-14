#!/usr/bin/env python3
import json
import hmac
import hashlib
import time
import urllib.request
import urllib.error
import os

API_KEY = os.environ.get("DME_API_KEY", "")
API_SECRET = os.environ.get("DME_API_SECRET", "")
DOMAIN = "violincelloacademy.com.au"

RECORDS = [
    {"name": "@", "type": "A", "data": "185.199.108.153", "ttl": 3600},
    {"name": "@", "type": "A", "data": "185.199.109.153", "ttl": 3600},
    {"name": "@", "type": "A", "data": "185.199.110.153", "ttl": 3600},
    {"name": "@", "type": "A", "data": "185.199.111.153", "ttl": 3600},
    {"name": "www", "type": "CNAME", "data": "damianmiller.github.io", "ttl": 3600},
]


def create_signature(method, path, timestamp, data):
    string_to_sign = f"{method}\n{path}\n{timestamp}\n{data}"
    signature = hmac.new(
        API_SECRET.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    print(f"DEBUG: Signing: {string_to_sign[:50]}...")
    print(f"DEBUG: Signature: {signature}")
    return signature


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
    }

    req = urllib.request.Request(url, headers=headers)
    if data:
        req.data = data_str.encode("utf-8")
        req.method = method

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {body}")
        print(f"URL: {url}")
        print(f"Method: {method}")
        print(f"Timestamp: {timestamp}")
        print(f"Signature: {signature[:20]}...")
        raise


def main():
    if not API_KEY or not API_SECRET:
        print("Error: DME_API_KEY and DME_API_SECRET environment variables required")
        return 1

    print(f"Fetching all domains...")
    try:
        all_domains = make_request("GET", "/domains")
        print(f"Found {len(all_domains)} domains in account")
        for d in all_domains:
            print(f"  - {d.get('name', 'unknown')} (ID: {d.get('id', 'unknown')})")

        domain = next((d for d in all_domains if d.get("name") == DOMAIN), None)
        if not domain:
            print(f"Error: Domain {DOMAIN} not found in dnsmadeeasy account")
            return 1

        domain_id = domain["id"]
        print(f"\nUsing domain ID: {domain_id}")
    except Exception as e:
        print(f"Error fetching domains: {e}")
        return 1

    for record in RECORDS:
        print(f"\nUpdating {record['type']} record for {record['name']}...")

        try:
            existing_records = make_request("GET", f"/domains/{domain_id}/records")

            record_found = False
            for existing in existing_records:
                if (
                    existing["name"] == record["name"]
                    and existing["type"] == record["type"]
                    and existing["data"] == record["data"]
                ):
                    print(f"  Record already exists, skipping...")
                    record_found = True
                    break

            if not record_found:
                response = make_request("POST", f"/domains/{domain_id}/records", record)
                print(f"Created: {record['name']} -> {record['data']}")
        except Exception as e:
            print(f"  Error: {e}")

    print("\nDNS records updated successfully!")
    print("Note: DNS propagation may take 24-48 hours")
    return 0


if __name__ == "__main__":
    exit(main())
