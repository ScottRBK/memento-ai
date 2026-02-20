"""
Backup service for database backup and restore operations.

Supports both SQLite (file copy) and PostgreSQL (pg_dump/psql) backup strategies.
"""
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from app.config.settings import settings

import logging

logger = logging.getLogger(__name__)


class BackupService:
    """Handles database backup and restore for both SQLite and PostgreSQL"""

    def __init__(self, database_type: str | None = None):
        self.database_type = database_type or settings.DATABASE

    async def create_backup(self) -> Path:
        """Create a timestamped backup. Returns the backup path."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if self.database_type == "SQLite":
            return self._backup_sqlite(timestamp)
        elif self.database_type == "Postgres":
            return self._backup_postgres(timestamp)
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    async def restore_backup(self, backup_path: Path) -> None:
        """Restore database from backup."""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        if self.database_type == "SQLite":
            self._restore_sqlite(backup_path)
        elif self.database_type == "Postgres":
            self._restore_postgres(backup_path)
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def _backup_sqlite(self, timestamp: str) -> Path:
        """Backup SQLite database by copying the .db file and WAL/SHM if present"""
        db_path = Path(settings.SQLITE_PATH)
        if not db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {db_path}")

        backup_path = db_path.parent / f"{db_path.name}.bak-{timestamp}"
        shutil.copy2(str(db_path), str(backup_path))

        # Also copy WAL and SHM files if they exist
        for suffix in ["-wal", "-shm"]:
            wal_path = Path(str(db_path) + suffix)
            if wal_path.exists():
                shutil.copy2(str(wal_path), str(backup_path) + suffix)

        logger.info("SQLite backup created", extra={"backup_path": str(backup_path)})
        return backup_path

    def _restore_sqlite(self, backup_path: Path) -> None:
        """Restore SQLite database from backup file"""
        db_path = Path(settings.SQLITE_PATH)

        shutil.copy2(str(backup_path), str(db_path))

        # Restore WAL and SHM if they exist in backup, otherwise remove stale ones
        for suffix in ["-wal", "-shm"]:
            backup_extra = Path(str(backup_path) + suffix)
            db_extra = Path(str(db_path) + suffix)
            if backup_extra.exists():
                shutil.copy2(str(backup_extra), str(db_extra))
            elif db_extra.exists():
                db_extra.unlink()

        logger.info("SQLite database restored", extra={"backup_path": str(backup_path)})

    def _backup_postgres(self, timestamp: str) -> Path:
        """Backup PostgreSQL database using pg_dump"""
        backup_dir = Path(settings.SQLITE_PATH).parent  # reuse data dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"forgetful-pg-{timestamp}.sql"

        cmd = [
            "pg_dump",
            "-h", settings.POSTGRES_HOST,
            "-p", str(settings.PGPORT),
            "-U", settings.POSTGRES_USER,
            "-d", settings.POSTGRES_DB,
            "-f", str(backup_path),
        ]

        env = {"PGPASSWORD": settings.POSTGRES_PASSWORD}

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr}")

        logger.info("PostgreSQL backup created", extra={"backup_path": str(backup_path)})
        return backup_path

    def _restore_postgres(self, backup_path: Path) -> None:
        """Restore PostgreSQL database from pg_dump file"""
        cmd = [
            "psql",
            "-h", settings.POSTGRES_HOST,
            "-p", str(settings.PGPORT),
            "-U", settings.POSTGRES_USER,
            "-d", settings.POSTGRES_DB,
            "-f", str(backup_path),
        ]

        env = {"PGPASSWORD": settings.POSTGRES_PASSWORD}

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"psql restore failed: {result.stderr}")

        logger.info("PostgreSQL database restored", extra={"backup_path": str(backup_path)})
