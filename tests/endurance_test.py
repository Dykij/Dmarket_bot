import time
import os
import psutil
import logging


# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    filename='logs/performance_audit.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)


def run_endurance_test(duration=300):
    print("Starting 5-minute endurance test...")
    start_time = time.time()
    process = psutil.Process(os.getpid())

    while time.time() - start_time < duration:
        loop_start = time.time()

        # Simulate some work
        _ = [x**2 for x in range(1000)]
        time.sleep(0.1)  # Simulate network/processing delay

        latency = time.time() - loop_start

        ram_usage = process.memory_info().rss / 1024 / 1024
        log_msg = f"[Status] RAM: {ram_usage:.2f} MB, Latency: {latency*1000:.4f} ms"

        print(log_msg)
        logging.info(log_msg)

        # Prevent spamming too fast, but keep it active
        time.sleep(0.9)


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    run_endurance_test()
