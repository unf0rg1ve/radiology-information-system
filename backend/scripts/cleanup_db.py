"""
Database cleanup script for RIS MVP.

Usage:
    python scripts/cleanup_db.py                  # Clean transactional data only (keep reference data)
    python scripts/cleanup_db.py --all            # Clean everything including reference data
    python scripts/cleanup_db.py --reseed         # Clean transactional data + re-seed reference data
    python scripts/cleanup_db.py --all --reseed   # Clean everything + re-seed reference data
    python scripts/cleanup_db.py --dry-run        # Show what would be deleted without deleting
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Suppress SQLAlchemy logging before importing database module
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine

# Disable SQL echo on the engine
engine.echo = False


# Tables in dependency-safe order (children first, parents last)
TRANSACTIONAL_TABLES = [
    # Level 0 - no FK dependencies
    "audit_log",
    "unmatched_studies",
    # Level 1 - depends on orders, users, devices
    "reports",
    "studies",
    "appointments",
    # Level 2 - central hub
    "orders",
    # Level 3 - depends on organizations, users
    "patients",
]

REFERENCE_TABLES = [
    # Level 4 - depends on organizations, devices
    "users",
    # Level 3 - depends on organizations, services
    "protocol_templates",
    # Level 5 - depends on organizations
    "devices",
    # Level 6 - top-level
    "organizations",
    "services",
    "diagnosis_icd",
]


async def get_table_counts(session) -> dict:
    """Get row counts for all tables."""
    counts = {}
    all_tables = TRANSACTIONAL_TABLES + REFERENCE_TABLES
    
    for table in all_tables:
        try:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = result.scalar()
        except Exception:
            counts[table] = -1  # Table doesn't exist
    
    return counts


async def truncate_tables(session, tables: list[str], dry_run: bool = False) -> int:
    """Truncate tables in order. Returns total rows deleted."""
    total_deleted = 0
    
    for table in tables:
        try:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            
            if count == 0:
                continue
            
            if dry_run:
                print(f"  [DRY RUN] Would delete {count:>8,} rows from {table}")
            else:
                await session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                print(f"  Deleted {count:>8,} rows from {table}")
            
            total_deleted += count
        except Exception as e:
            print(f"  Warning: Could not truncate {table}: {e}")
    
    return total_deleted


async def main():
    parser = argparse.ArgumentParser(description="Clean RIS database")
    parser.add_argument("--all", action="store_true", help="Clean everything including reference data (services, ICD-10, org)")
    parser.add_argument("--reseed", action="store_true", help="Re-seed reference data after cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
    async with AsyncSessionLocal() as session:
        # Show current state
        print("\n=== Current Database State ===\n")
        counts = await get_table_counts(session)
        
        for table in TRANSACTIONAL_TABLES:
            count = counts.get(table, -1)
            if count >= 0:
                print(f"  {table:<25} {count:>8,} rows")
        
        if args.all:
            print("\n  --- Reference Data ---")
            for table in REFERENCE_TABLES:
                count = counts.get(table, -1)
                if count >= 0:
                    print(f"  {table:<25} {count:>8,} rows")
        
        # Calculate what will be deleted
        tables_to_clean = TRANSACTIONAL_TABLES.copy()
        if args.all:
            tables_to_clean.extend(REFERENCE_TABLES)
        
        total_rows = sum(max(0, counts.get(t, 0)) for t in tables_to_clean)
        
        if total_rows == 0:
            print("\n  Database is already clean!")
            return
        
        # Confirmation
        print(f"\n  Total rows to delete: {total_rows:,}")
        
        if args.dry_run:
            print("\n=== Dry Run ===\n")
        else:
            if not args.yes:
                confirm = input("\n  Are you sure? (yes/no): ").strip().lower()
                if confirm not in ("yes", "y"):
                    print("  Cancelled.")
                    return
            print("\n=== Cleaning Database ===\n")
        
        # Clean transactional data
        deleted = await truncate_tables(session, TRANSACTIONAL_TABLES, args.dry_run)
        
        # Clean reference data if requested
        if args.all:
            ref_deleted = await truncate_tables(session, REFERENCE_TABLES, args.dry_run)
            deleted += ref_deleted
        
        if not args.dry_run:
            await session.commit()
        
        print(f"\n  Total: {deleted:,} rows {'would be' if args.dry_run else ''} deleted")
    
    # Re-seed if requested
    if args.reseed and not args.dry_run:
        print("\n=== Re-seeding Reference Data ===\n")
        from scripts.seed_refs import seed
        await seed()
        print("\n  Seed data restored!")
    
    print("\nDone!\n")


if __name__ == "__main__":
    asyncio.run(main())
