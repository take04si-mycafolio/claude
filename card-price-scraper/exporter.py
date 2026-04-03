"""
CSV exporter for card price data.
"""
import csv
import os
from datetime import datetime


FIELDNAMES = [
    "fetched_at",
    "game",
    "id",
    "name",
    "set",
    "number",
    "rarity",
    "price_type",
    "price_market_usd",
    "price_low_usd",
    "price_mid_usd",
    "price_high_usd",
    "price_eur",
    "currency",
    "source_url",
]


def export_to_csv(records: list[dict], filepath: str) -> str:
    """
    Export a list of card price records to CSV.
    Appends to existing file if it exists; creates new otherwise.
    Returns the final filepath.
    """
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.isfile(filepath)

    with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")

        if not file_exists:
            writer.writeheader()

        for record in records:
            row = {field: record.get(field, "") for field in FIELDNAMES}
            row["fetched_at"] = fetched_at
            # Blank out None values
            for k, v in row.items():
                if v is None:
                    row[k] = ""
            writer.writerow(row)

    return filepath


def export_new_csv(records: list[dict], filepath: str) -> str:
    """
    Always create a fresh CSV (overwrite if exists).
    """
    if os.path.exists(filepath):
        os.remove(filepath)
    return export_to_csv(records, filepath)
