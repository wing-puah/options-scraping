import csv
import io


def parse_csv(raw: str) -> list[dict]:
    """Parse a Barchart-exported CSV, stopping at the 'Downloaded from' footer row."""
    rows = []
    reader = csv.DictReader(io.StringIO(raw))
    for row in reader:
        first_val = next(iter(row.values()), "") if row else ""
        if first_val.startswith("Downloaded from"):
            break
        rows.append(dict(row))
    return rows
