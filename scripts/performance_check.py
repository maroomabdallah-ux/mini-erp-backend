"""Small repeatable SRS smoke/load check against a running seeded API."""

import concurrent.futures
import os
import statistics
import time

import httpx

BASE_URL = os.getenv("ERP_API_URL", "http://localhost:8000")
LOGIN = os.getenv("ERP_TEST_LOGIN", "admin")
PASSWORD = os.getenv("ERP_TEST_PASSWORD", "Passw0rd!")


def request(client: httpx.Client, path: str) -> float:
    started = time.perf_counter()
    response = client.get(f"{BASE_URL}{path}")
    response.raise_for_status()
    return time.perf_counter() - started


def main() -> None:
    with httpx.Client(timeout=10) as client:
        login = client.post(
            f"{BASE_URL}/auth/login", json={"login": LOGIN, "password": PASSWORD}
        )
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        paths = ["/products?page=1&size=100", "/reports/monthly-sales?months=12"]
        for path in paths:
            timings = [request(client, path) for _ in range(5)]
            limit = 3 if path.startswith("/reports") else 0.5
            maximum = max(timings)
            print(f"{path}: max={maximum:.3f}s median={statistics.median(timings):.3f}s")
            if maximum > limit:
                raise SystemExit(f"Performance limit exceeded for {path}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            timings = list(pool.map(lambda _: request(client, "/health"), range(20)))
        print(f"20 concurrent users: max={max(timings):.3f}s")


if __name__ == "__main__":
    main()
