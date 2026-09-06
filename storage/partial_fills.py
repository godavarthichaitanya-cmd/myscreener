# ============================================================
# storage/partial_fills.py
#    (logs partial buys separately from score_history.csv,
#    which only logs evaluations, not transactions)
# ============================================================
 
import csv
import os
from datetime import datetime
 
PARTIAL_FILLS_PATH = "partial_fills.csv"
 
 
def log_partial_fill(symbol, qty, price, cost):
    file_exists = os.path.isfile(PARTIAL_FILLS_PATH)
    with open(PARTIAL_FILLS_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["date", "symbol", "qty", "price", "cost"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, qty, price, cost])
 
 
def load_partial_fills():
    if not os.path.isfile(PARTIAL_FILLS_PATH):
        return []
    with open(PARTIAL_FILLS_PATH, newline="") as f:
        return list(csv.DictReader(f))