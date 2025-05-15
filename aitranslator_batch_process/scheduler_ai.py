# scheduler.py
import schedule
import time
import subprocess

def run_main():
    print("Heartbeat: Task is running...")
    subprocess.run(["python", "/app/aitranslator_batch_process/main.py"])

schedule.every(1).minutes.do(run_main)

while True:
    schedule.run_pending()
    time.sleep(1)