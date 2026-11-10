"""Local archive-level checkpoints; uncertain imports are never retried silently."""
from pathlib import Path
import sqlite3


class ZipCheckpoint:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute('''CREATE TABLE IF NOT EXISTS archives (
            target TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL,
            status TEXT NOT NULL, batch_id INTEGER, message TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (target, path, sha256)
        )''')
        self.connection.commit()

    def claim(self, target, path, digest, *, retry_uncertain=False):
        """Atomically claim new work; retrying uncertain work requires opt-in."""
        with self.connection:
            cur = self.connection.execute('''INSERT OR IGNORE INTO archives
                (target, path, sha256, status) VALUES (?, ?, ?, 'running')''',
                (target, path, digest))
            if cur.rowcount:
                return True, 'running'
            row = self.connection.execute('''SELECT status FROM archives
                WHERE target=? AND path=? AND sha256=?''', (target, path, digest)).fetchone()
            status = row[0]
            if retry_uncertain and status in ('running', 'needs_review'):
                self.connection.execute('''UPDATE archives SET status='running',
                    message='', updated_at=CURRENT_TIMESTAMP
                    WHERE target=? AND path=? AND sha256=?''', (target, path, digest))
                return True, 'running'
            return False, status

    def finish(self, target, path, digest, *, status, batch_id=None, message=''):
        if status not in ('completed', 'completed_with_errors', 'needs_review'):
            raise ValueError('Invalid checkpoint status.')
        with self.connection:
            self.connection.execute('''UPDATE archives SET status=?, batch_id=?, message=?,
                updated_at=CURRENT_TIMESTAMP WHERE target=? AND path=? AND sha256=?''',
                (status, batch_id, message[:2000], target, path, digest))

    def details(self, target, path, digest):
        return self.connection.execute('''SELECT batch_id, message FROM archives
            WHERE target=? AND path=? AND sha256=?''', (target, path, digest)).fetchone()

    def close(self):
        self.connection.close()
