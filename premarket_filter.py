"""
premarket_filter.py — NODE 7: The Pre-Market Sniper
====================================================
Parses a standard NSE Bhavcopy CSV (equity segment, cm<date>bhav.csv)
and filters rows against desk parameters:

  CLOSE  >= 20  AND  CLOSE  <= 150
  TOTTRDQTY  >= 1,000,000  (1M shares daily volume floor)

Passing symbols are formatted as  NSE|<SYMBOL>-EQ
and written line-by-line to  target_list.txt  in the same directory as
this script.  The Shoonya data_ingestion.py will load this file on boot.

Usage:
    python premarket_filter.py <path_to_bhavcopy.csv>

    # Example:
    python premarket_filter.py "C:/Downloads/cm27MAR2026bhav.csv"

Bhavcopy column reference (NSE equity segment):
    SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, LAST, PREVCLOSE,
    TOTTRDQTY, TOTTRDVAL, TIMESTAMP, TOTALTRADES, ISIN
"""

import csv
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Desk parameters
# ---------------------------------------------------------------------------
PRICE_MIN   = 20.0
PRICE_MAX   = 150.0
VOL_MIN     = 1_000_000          # 1 million shares
EQUITY_SERIES = {"EQ", "BE", "BZ"}   # standard equity series on NSE

OUTPUT_FILE = Path(__file__).resolve().parent / "target_list.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("node7.premarket_filter")


# ---------------------------------------------------------------------------
# Core filter
# ---------------------------------------------------------------------------
def parse_bhavcopy(csv_path: str | Path) -> list[str]:
    """
    Parse NSE Bhavcopy CSV and return a list of formatted symbols that
    pass all desk filters.

    Args:
        csv_path: Absolute or relative path to the Bhavcopy CSV file.

    Returns:
        List of strings in the format  "NSE|<SYMBOL>-EQ"
    """
    csv_path = Path(csv_path).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"Bhavcopy file not found: {csv_path}")

    passing: list[str] = []
    total_rows = 0
    skipped_series = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Normalise header names (strip whitespace — NSE sometimes pads them)
        reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]

        for row in reader:
            total_rows += 1

            # Strip all values
            row = {k.strip(): v.strip() for k, v in row.items()}

            # Only equity series
            series = row.get("SERIES", "").upper()
            if series not in EQUITY_SERIES:
                skipped_series += 1
                continue

            symbol = row.get("SYMBOL", "").strip()
            if not symbol:
                continue

            try:
                close = float(row.get("CLOSE", 0) or 0)
                volume = int(float(row.get("TOTTRDQTY", 0) or 0))
            except (ValueError, TypeError):
                logger.warning("Skipping malformed row for symbol %r", symbol)
                continue

            # Apply desk filters
            if PRICE_MIN <= close <= PRICE_MAX and volume >= VOL_MIN:
                passing.append(f"NSE|{symbol}-EQ")

    logger.info(
        "Bhavcopy parse complete — total rows: %d | non-equity skipped: %d | passing filter: %d",
        total_rows, skipped_series, len(passing),
    )
    return passing


def write_target_list(symbols: list[str], output: Path = OUTPUT_FILE) -> None:
    """Write formatted symbols to target_list.txt, one per line."""
    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(symbols))
        if symbols:
            f.write("\n")   # trailing newline

    logger.info(
        "Wrote %d symbols → %s",
        len(symbols), output,
    )
    for sym in symbols:
        logger.info("  %s", sym)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python premarket_filter.py <path_to_bhavcopy.csv>\n"
            "Example: python premarket_filter.py cm27MAR2026bhav.csv"
        )
        sys.exit(1)

    csv_path = sys.argv[1]

    try:
        symbols = parse_bhavcopy(csv_path)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        sys.exit(1)

    if not symbols:
        logger.warning(
            "No symbols passed the filter. "
            "Check PRICE_MIN=%.0f, PRICE_MAX=%.0f, VOL_MIN=%,d",
            PRICE_MIN, PRICE_MAX, VOL_MIN,
        )
        sys.exit(0)

    write_target_list(symbols)
    print(f"\n✓ target_list.txt updated — {len(symbols)} symbols ready.")


if __name__ == "__main__":
    main()
