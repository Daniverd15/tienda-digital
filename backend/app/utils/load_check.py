import argparse
import concurrent.futures
import time
from urllib.request import urlopen


def hit(url: str) -> float:
    start = time.perf_counter()
    with urlopen(url, timeout=10) as response:
        response.read()
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
    return (time.perf_counter() - start) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba simple de concurrencia local.")
    parser.add_argument("--url", default="http://localhost:8000/products")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        durations = list(executor.map(lambda _: hit(args.url), range(args.requests)))
    print(f"requests={len(durations)} avg_ms={sum(durations)/len(durations):.2f} max_ms={max(durations):.2f}")


if __name__ == "__main__":
    main()

