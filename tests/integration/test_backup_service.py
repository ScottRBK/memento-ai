"""
Integration tests for BackupService.

Tests SQLite backup/restore with temporary files.
"""
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from app.services.backup_service import BackupService


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database file for testing"""
    db_path = tmp_path / "forgetful.db"
    db_path.write_text("original database content")
    return db_path


@pytest.mark.asyncio
async def test_sqlite_backup_creates_copy(temp_db):
    """Verify backup file is created at expected path"""
    with patch("app.services.backup_service.settings") as mock_settings:
        mock_settings.DATABASE = "SQLite"
        mock_settings.SQLITE_PATH = str(temp_db)
        mock_settings.SQLITE_MEMORY = False

        service = BackupService(database_type="SQLite")
        backup_path = await service.create_backup()

        assert backup_path.exists()
        assert backup_path.read_text() == "original database content"
        assert backup_path.parent == temp_db.parent


@pytest.mark.asyncio
async def test_sqlite_restore_overwrites_current(temp_db):
    """Verify restore replaces current DB"""
    with patch("app.services.backup_service.settings") as mock_settings:
        mock_settings.DATABASE = "SQLite"
        mock_settings.SQLITE_PATH = str(temp_db)
        mock_settings.SQLITE_MEMORY = False

        service = BackupService(database_type="SQLite")

        # Create backup
        backup_path = await service.create_backup()

        # Modify the original
        temp_db.write_text("modified database content")
        assert temp_db.read_text() == "modified database content"

        # Restore
        await service.restore_backup(backup_path)

        # Should be back to original
        assert temp_db.read_text() == "original database content"


@pytest.mark.asyncio
async def test_backup_path_contains_timestamp(temp_db):
    """Naming convention check"""
    with patch("app.services.backup_service.settings") as mock_settings:
        mock_settings.DATABASE = "SQLite"
        mock_settings.SQLITE_PATH = str(temp_db)
        mock_settings.SQLITE_MEMORY = False

        service = BackupService(database_type="SQLite")
        backup_path = await service.create_backup()

        # Should contain .bak- and a timestamp-like pattern
        assert ".bak-" in backup_path.name
        # Name format: forgetful.db.bak-YYYYMMDD-HHMMSS
        parts = backup_path.name.split(".bak-")
        assert len(parts) == 2
        timestamp_part = parts[1]
        # Should be parseable as YYYYMMDD-HHMMSS
        datetime.strptime(timestamp_part, "%Y%m%d-%H%M%S")


@pytest.mark.asyncio
async def test_sqlite_backup_copies_wal_files(temp_db):
    """Verify WAL and SHM files are also backed up if present"""
    wal_path = Path(str(temp_db) + "-wal")
    shm_path = Path(str(temp_db) + "-shm")
    wal_path.write_text("wal content")
    shm_path.write_text("shm content")

    with patch("app.services.backup_service.settings") as mock_settings:
        mock_settings.DATABASE = "SQLite"
        mock_settings.SQLITE_PATH = str(temp_db)
        mock_settings.SQLITE_MEMORY = False

        service = BackupService(database_type="SQLite")
        backup_path = await service.create_backup()

        backup_wal = Path(str(backup_path) + "-wal")
        backup_shm = Path(str(backup_path) + "-shm")
        assert backup_wal.exists()
        assert backup_shm.exists()
        assert backup_wal.read_text() == "wal content"
        assert backup_shm.read_text() == "shm content"


@pytest.mark.asyncio
async def test_restore_nonexistent_backup_raises():
    """Restoring a nonexistent backup should raise FileNotFoundError"""
    service = BackupService(database_type="SQLite")

    with pytest.raises(FileNotFoundError):
        await service.restore_backup(Path("/nonexistent/backup.db"))


@pytest.mark.asyncio
async def test_backup_missing_db_raises(tmp_path):
    """Backing up a nonexistent database should raise FileNotFoundError"""
    with patch("app.services.backup_service.settings") as mock_settings:
        mock_settings.DATABASE = "SQLite"
        mock_settings.SQLITE_PATH = str(tmp_path / "nonexistent.db")
        mock_settings.SQLITE_MEMORY = False

        service = BackupService(database_type="SQLite")

        with pytest.raises(FileNotFoundError):
            await service.create_backup()
