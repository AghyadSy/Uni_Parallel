import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description="Concurrent checkout stress script.")
    parser.add_argument("--mode", choices=["before", "after"], default="after")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    reset = post_json(f"{args.base_url}/api/demo/reset-data/")
    product_id = reset["data"]["race_product_id"]
    payload = {
        "customer_name": "Stress User",
        "items": [{"product_id": product_id, "quantity": 1}],
        "simulate_payment_failure": False,
    }

    start = time.perf_counter()
    results = run_concurrent(args.base_url, args.mode, args.users, payload)
    total_ms = round((time.perf_counter() - start) * 1000, 2)
    durations = [result["duration_ms"] for result in results]
    success_count = sum(1 for result in results if result["ok"])
    failure_count = args.users - success_count
    final_stock = get_race_stock(args.base_url)

    print(f"mode: {args.mode}")
    print(f"total users: {args.users}")
    print(f"success count: {success_count}")
    print(f"failure count: {failure_count}")
    print(f"avg response time ms: {round(statistics.mean(durations), 2) if durations else 0}")
    print(f"min response time ms: {round(min(durations), 2) if durations else 0}")
    print(f"max response time ms: {round(max(durations), 2) if durations else 0}")
    print(f"total duration ms: {total_ms}")
    print(f"final stock: {final_stock}")
    print(f"problem detected: {str(final_stock < 0 or success_count > 5).lower()}")


def run_concurrent(base_url, mode, users, payload):
    with ThreadPoolExecutor(max_workers=users) as executor:
        futures = [
            executor.submit(checkout_once, base_url, mode, payload)
            for _ in range(users)
        ]
        return [future.result() for future in as_completed(futures)]


def checkout_once(base_url, mode, payload):
    start = time.perf_counter()
    try:
        data = post_json(f"{base_url}/api/orders/checkout/?{urlencode({'mode': mode})}", payload)
        return {"ok": bool(data.get("success")), "duration_ms": elapsed_ms(start), "data": data}
    except Exception as exc:
        return {"ok": False, "duration_ms": elapsed_ms(start), "error": str(exc)}


def get_race_stock(base_url):
    products = get_json(f"{base_url}/api/products/")["data"]
    for product in products:
        if product["sku"] == "RACE-001":
            return int(product["stock"])
    return 0


def post_json(url, payload=None):
    body = json.dumps(payload or {}).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    return read_json(request)


def get_json(url):
    return read_json(Request(url, method="GET"))


def read_json(request):
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach server: {exc}") from exc


def elapsed_ms(start):
    return round((time.perf_counter() - start) * 1000, 2)


if __name__ == "__main__":
    main()
