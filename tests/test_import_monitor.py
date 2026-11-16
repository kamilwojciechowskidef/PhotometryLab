import sqlite3

import pytest

from photolab.import_monitor import (ImportMonitorError, open_checkpoint_readonly,
                                     read_batch_report, read_checkpoint)
from photolab.zip_checkpoint import ZipCheckpoint


def test_missing_checkpoint_is_not_created(tmp_path):
    path = tmp_path / 'missing.sqlite3'
    assert read_checkpoint(path, 'database') is None
    assert not path.exists()


def test_snapshot_filters_target_and_counts_only_recognized_summaries(tmp_path):
    path = tmp_path / 'state with # and space.sqlite3'
    checkpoint = ZipCheckpoint(path)
    try:
        for name, status, batch, message in [
            ('a.zip', 'completed', 1, 'new=4 duplicate=2 errors=0'),
            ('b.zip', 'completed_with_errors', 2, 'new=3 duplicate=1 errors=2'),
            ('c.zip', 'needs_review', None, 'Batch may have partly committed'),
            ('d.zip', 'completed', 3, 'legacy summary'),
        ]:
            checkpoint.claim('db1', f'C:\\source\\{name}', name * 16)
            checkpoint.finish('db1', f'C:\\source\\{name}', name * 16,
                              status=status, batch_id=batch, message=message)
        checkpoint.claim('db1', 'C:\\source\\running.zip', 'a' * 64)
        checkpoint.claim('other-db', 'C:\\source\\other.zip', 'b' * 64)
        checkpoint.finish('other-db', 'C:\\source\\other.zip', 'b' * 64,
                          status='completed', batch_id=4, message='new=900 duplicate=0 errors=0')
        snapshot = read_checkpoint(path, 'db1', limit=2)
        assert snapshot.status_counts == {'completed': 2, 'completed_with_errors': 1,
                                          'needs_review': 1, 'running': 1}
        assert snapshot.outcome_counts == {'new': 7, 'duplicate': 3, 'errors': 2}
        assert snapshot.summarized_archives == 2
        assert snapshot.unsummarized_finished == 1
        assert len(snapshot.recent) == 2
        assert all('C:\\source' not in row['archive'] for row in snapshot.recent)
        # Writer remains usable after the read-only snapshot.
        checkpoint.finish('db1', 'C:\\source\\running.zip', 'a' * 64,
                          status='completed', batch_id=5, message='new=1 duplicate=0 errors=0')
        assert read_checkpoint(path, 'db1').status_counts['completed'] == 3
    finally:
        checkpoint.close()


def test_readonly_sqlite_connection_forbids_writes(tmp_path):
    path = tmp_path / 'state.sqlite3'
    checkpoint = ZipCheckpoint(path)
    checkpoint.claim('db', 'a.zip', 'x' * 64)
    checkpoint.close()
    connection = open_checkpoint_readonly(path)
    try:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            connection.execute('DELETE FROM archives')
    finally:
        connection.close()
    assert read_checkpoint(path, 'db').status_counts == {'running': 1}


def test_incompatible_checkpoint_is_reported(tmp_path):
    path = tmp_path / 'bad.sqlite3'
    path.write_bytes(b'not a database')
    with pytest.raises(ImportMonitorError, match='checkpoint'):
        read_checkpoint(path, 'db')
    assert path.read_bytes() == b'not a database'


class Cursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, args):
        self.calls.append((sql, args))

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, cursor):
        self.value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.value


def test_batch_report_is_read_only_and_parameterized(monkeypatch):
    cursor = Cursor((7, 'completed_with_errors', 2, [{'filename': 'a.ies', 'outcome': 'rejected'}]))
    options = {}
    def connect(*args, **kwargs):
        options.update(kwargs)
        return Connection(cursor)
    monkeypatch.setattr('photolab.import_monitor.psycopg.connect', connect)
    report = read_batch_report('unused', 7)
    assert options['autocommit'] is True
    assert options['options'] == '-c default_transaction_read_only=on'
    assert cursor.calls[0][1] == (7,)
    assert report['report'][0]['outcome'] == 'rejected'


def test_monitor_interface_reports_recorded_count_without_progress_percentage(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from photolab import import_monitor_ui

    root = tmp_path / 'sources'
    state_path = tmp_path / 'zip-import-checkpoints.sqlite3'
    checkpoint = ZipCheckpoint(state_path)
    checkpoint.claim('db', 'a.zip', 'a' * 64)
    checkpoint.finish('db', 'a.zip', 'a' * 64, status='completed', batch_id=4,
                      message='new=2 duplicate=1 errors=0')
    checkpoint.close()
    monkeypatch.setattr(import_monitor_ui, 'artifact_root', lambda: root)
    monkeypatch.setattr(import_monitor_ui, 'database_url', lambda: 'unused')
    monkeypatch.setattr(import_monitor_ui, 'database_target_key', lambda url: 'db')
    app = AppTest.from_string('''
import streamlit as st
from photolab.import_monitor_ui import render_import_monitor
render_import_monitor(st)
''').run(timeout=20)
    assert not app.exception
    assert app.metric[0].label == 'Recorded ZIPs'
    assert app.metric[0].value == '1'
    assert len(app.dataframe) == 1
    assert not app.get('progress')
