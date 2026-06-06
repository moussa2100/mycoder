"""Tests for snapshot.py utilities."""

import tempfile
from pathlib import Path
import shutil

import pytest

from pgimcode.tools.snapshot import (
    Snapshot,
    SnapshotManager,
)


def test_save_restore_roundtrip():
    """Test save and restore files from snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        
        # Create test files
        file1 = Path(tmpdir) / "file1.txt"
        file2 = Path(tmpdir) / "file2.txt"
        file1.write_text("original content 1")
        file2.write_text("original content 2")

        # Create snapshot manager
        manager = SnapshotManager(session_dir)
        
        # Save snapshot
        snap_id = manager.save([file1, file2])
        assert snap_id.startswith("snap-")
        
        # Modify original files
        file1.write_text("modified content 1")
        file2.write_text("modified content 2")
        
        # Restore from snapshot
        restored = manager.restore(snap_id)
        assert len(restored) == 2
        
        # Verify restored content
        assert file1.read_text() == "original content 1"
        assert file2.read_text() == "original content 2"


def test_delete_snapshot():
    """Test deleting a snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        
        # Create test file
        file1 = Path(tmpdir) / "file1.txt"
        file1.write_text("test content")
        
        # Create snapshot manager
        manager = SnapshotManager(session_dir)
        
        # Save snapshot
        snap_id = manager.save([file1])
        
        # Verify snapshot exists
        snap_dir = session_dir / "snapshots" / snap_id
        assert snap_dir.exists()
        
        # Delete snapshot
        manager.delete(snap_id)
        
        # Verify snapshot deleted
        assert not snap_dir.exists()


def test_list_snapshots():
    """Test listing snapshots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        
        # Create test file
        file1 = Path(tmpdir) / "file1.txt"
        file1.write_text("test content")
        
        # Create snapshot manager
        manager = SnapshotManager(session_dir)
        
        # Save two snapshots
        snap_id1 = manager.save([file1])
        snap_id2 = manager.save([file1])
        
        # List snapshots
        snaps = manager.list_snapshots()
        assert len(snaps) == 2
        snap_ids = [s.id for s in snaps]
        assert snap_id1 in snap_ids
        assert snap_id2 in snap_ids


def test_restore_nonexistent_snapshot():
    """Test restoring nonexistent snapshot returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        manager = SnapshotManager(session_dir)
        
        restored = manager.restore("nonexistent-snap-id")
        assert restored == []