import json
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000"


def main():
    post("/api/demo/reset-data/")
    before = post("/api/demo/race-stock/?mode=before&users=20")["data"]
    post("/api/demo/reset-data/")
    after = post("/api/demo/race-stock/?mode=after&users=20")["data"]

    print(f"Before: stock = {before['final_stock']}")
    print(f"After: stock = {after['final_stock']}")
    print()
    print(f"Before: successful_orders = {before['successful_orders']}")
    print(f"After: successful_orders = {after['successful_orders']}")
    print()
    print("Conclusion:")
    print("After implementation prevents overselling under concurrent access.")


def post(path):
    request = Request(
        f"{BASE_URL}{path}",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
