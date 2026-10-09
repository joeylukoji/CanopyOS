import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class ScanBusy(RuntimeError):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "canopyos.db"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, created_at TEXT NOT NULL,
                area_type TEXT NOT NULL, status TEXT NOT NULL, stage INTEGER NOT NULL DEFAULT 0,
                error TEXT, report TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS scans_owner_date ON scans(owner, created_at)")
            db.execute("CREATE TABLE IF NOT EXISTS rate_events (owner TEXT, kind TEXT, at REAL)")

    def allow(self, owner: str, kind: str, personal: int, global_limit: int) -> bool:
        import time

        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM rate_events WHERE at < ?", (now - 60,))
            total = db.execute("SELECT count(*) FROM rate_events WHERE kind=?", (kind,)).fetchone()[
                0
            ]
            own = db.execute(
                "SELECT count(*) FROM rate_events WHERE kind=? AND owner=?", (kind, owner)
            ).fetchone()[0]
            if own >= personal or total >= global_limit:
                return False
            db.execute("INSERT INTO rate_events VALUES (?, ?, ?)", (owner, kind, now))
        return True

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def recover(self):
        with self.connect() as db:
            db.execute(
                "UPDATE scans SET status='failed', error='The server restarted during analysis. Please retry.' WHERE status='processing'"
            )

    def create(self, owner: str, area_type: str) -> str:
        scan_id = str(uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO scans (id, owner, created_at, area_type, status) VALUES (?, ?, ?, ?, ?)",
                (scan_id, owner, datetime.now(UTC).isoformat(), area_type, "uploaded"),
            )
        self.folder(scan_id).mkdir()
        return scan_id

    def folder(self, scan_id: str) -> Path:
        from uuid import UUID

        return self.root / str(UUID(scan_id))

    def get(self, scan_id: str, owner: str):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM scans WHERE id=? AND owner=?", (scan_id, owner)
            ).fetchone()
        return self.serialize(row) if row else None

    @staticmethod
    def serialize(row):
        result = dict(row)
        result["scan_id"] = result.pop("id")
        result.pop("owner")
        result["report"] = json.loads(result["report"]) if result["report"] else None
        return result

    def list(self, owner: str, limit: int = 20, offset: int = 0):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM scans WHERE owner=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (owner, limit, offset),
            ).fetchall()
        return [self.serialize(row) for row in rows]

    def update(self, scan_id: str, *, status: str, stage: int, error=None, report=None):
        with self.connect() as db:
            db.execute(
                "UPDATE scans SET status=?, stage=?, error=?, report=? WHERE id=?",
                (status, stage, error, report.model_dump_json() if report else None, scan_id),
            )

    def claim(self, scan_id: str, owner: str) -> bool:
        with self.connect() as db:
            result = db.execute(
                "UPDATE scans SET status='processing', stage=1, error=NULL, report=NULL "
                "WHERE id=? AND owner=? AND status IN ('uploaded', 'failed', 'rejected')",
                (scan_id, owner),
            )
            return result.rowcount == 1

    def delete(self, scan_id: str, owner: str):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM scans WHERE id=? AND owner=?", (scan_id, owner)
            ).fetchone()
            if row is None:
                return
            if row["status"] == "processing":
                raise ScanBusy("Wait for analysis to finish before deleting this scan.")
            folder = self.folder(scan_id).resolve()
            if folder.parent != self.root:
                raise ValueError("Invalid asset location")
            for name in ("original.jpg", "segmentation.jpg", "concept.jpg"):
                (folder / name).unlink(missing_ok=True)
            if folder.exists():
                folder.rmdir()
            db.execute("DELETE FROM scans WHERE id=? AND owner=?", (scan_id, owner))

    def prune(self, owner: str):
        for scan in self.list(owner, limit=1000, offset=20):
            if scan["status"] != "processing":
                try:
                    self.delete(scan["scan_id"], owner)
                except ScanBusy:
                    continue
