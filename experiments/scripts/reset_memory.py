"""
reset_memory.py — Wipe ChromaDB before a clean Stage D seeding run.

Usage:
    python scripts/reset_memory.py [--confirm]

Without --confirm, prints the count and exits (dry-run). With --confirm, wipes.
"""
import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "backend"))
sys.path.insert(0, BACKEND_DIR)

CHROMA_PATH = os.path.join(BACKEND_DIR, "chroma_db")


def main():
    parser = argparse.ArgumentParser(description="Reset ChromaDB memory for a clean Stage D seed.")
    parser.add_argument("--confirm", action="store_true", help="Actually wipe. Without this flag, just prints count.")
    args = parser.parse_args()

    from app.utils.memory import FinancialMemory
    memory = FinancialMemory(persist_directory=CHROMA_PATH)
    count = memory.collection.count()
    print(f"ChromaDB currently contains {count} memories.")

    if not args.confirm:
        print("Dry-run — no changes made. Pass --confirm to wipe.")
        return

    memory.clear_all()
    remaining = memory.collection.count()
    print(f"Cleared. Remaining: {remaining}")


if __name__ == "__main__":
    main()
