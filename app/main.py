"""Explicit spreadsheet import entry point. Database schema is managed by Alembic."""
import argparse
from pathlib import Path

from app.db.database import SessionLocal
from app.deals.importer import import_deals


def main() -> None:
    parser = argparse.ArgumentParser(description="Import deals from an Excel workbook.")
    parser.add_argument(
        "workbook",
        nargs="?",
        help="Path to an .xlsx workbook. If omitted, no import is performed.",
    )
    args = parser.parse_args()

    if not args.workbook:
        parser.print_help()
        return

    workbook = Path(args.workbook)
    if not workbook.is_file():
        parser.error(f"Workbook not found: {workbook}")

    db = SessionLocal()
    try:
        import_deals(db, workbook)
    finally:
        db.close()


if __name__ == "__main__":
    main()
