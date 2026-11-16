"""Manual-refresh import monitor; it does not control the worker."""
from pathlib import Path

import pandas as pd

from .artifacts import artifact_root
from .database import DatabaseError, database_url
from .import_monitor import ImportMonitorError, read_batch_report, read_checkpoint
from .zip_import import database_target_key


def render_import_monitor(st):
    st.subheader('Folder import progress')
    st.caption('Read-only view of the default checkpoint across all recorded runs for this PostgreSQL target. '
               'A custom --state-file or another server is not included. Refresh manually; '
               'this panel cannot start, stop or retry the worker.')
    st.button('Refresh import progress', key='refresh_import_progress')
    path = artifact_root().parent / 'zip-import-checkpoints.sqlite3'
    if not Path(path).is_file():
        st.info('No default checkpoint file exists on this server. Start the folder worker first; '
                'a custom --state-file is not shown in this view.')
        return
    try:
        url = database_url()
        target = database_target_key(url)
        snapshot = read_checkpoint(path, target)
    except (DatabaseError, ImportMonitorError, OSError, ValueError) as error:
        st.warning(str(error))
        return
    if snapshot is None:
        st.info('The default checkpoint file is no longer available.')
        return
    statuses = snapshot.status_counts
    columns = st.columns(5)
    for column, (label, count) in zip(columns, (
        ('Recorded ZIPs', sum(statuses.values())),
        ('Completed', statuses.get('completed', 0)),
        ('Completed with errors', statuses.get('completed_with_errors', 0)),
        ('Running / interrupted', statuses.get('running', 0)),
        ('Needs review', statuses.get('needs_review', 0)),
    )):
        column.metric(label, count)
    unknown = {key: value for key, value in statuses.items()
               if key not in {'completed', 'completed_with_errors', 'running', 'needs_review'}}
    if unknown:
        st.warning(f'Unrecognized checkpoint states: {unknown}')
    st.caption('Recorded ZIPs count path + SHA-256 versions already encountered across runs, '
               'not all ZIPs in the folder. Repeated files under other paths count separately. '
               'Running can also mean interrupted; this panel does not check whether a worker is alive. '
               'No completion percentage or time estimate is available.')
    if snapshot.summarized_archives:
        outcomes = snapshot.outcome_counts
        st.write(f"From {snapshot.summarized_archives:,} recognized completed summaries: "
                 f"new {outcomes.get('new', 0):,}, duplicates {outcomes.get('duplicate', 0):,}, "
                 f"errors / skipped / rejected {outcomes.get('errors', 0):,}. "
                 'These are report outcomes, not counts of unique files.')
    if snapshot.unsummarized_finished:
        st.warning(f'{snapshot.unsummarized_finished} completed checkpoint(s) lack a recognized file summary; '
                   'the above file counts exclude them.')
    if not snapshot.recent:
        st.info('No checkpoints match the configured PostgreSQL target. '
                'A different database or a custom --state-file may have been used.')
        return
    st.caption('Latest 50 recorded archives. Timestamps come from SQLite in UTC; '
               'the short hash distinguishes files with the same name.')
    st.dataframe(pd.DataFrame(snapshot.recent).rename(columns={
        'archive': 'Archive', 'sha256_prefix': 'SHA-256 prefix', 'status': 'Status',
        'batch_id': 'Batch ID', 'message': 'Worker summary / message', 'updated_utc': 'Updated [UTC]',
    }), hide_index=True, width='stretch')
    available = {row['batch_id'] for row in snapshot.recent if row['batch_id'] is not None}
    if available and st.checkbox('Show an import batch report', key='monitor_show_batch'):
        batch_id = st.selectbox('Import batch ID', sorted(available, reverse=True), key='monitor_batch_id')
        try:
            batch = read_batch_report(url, batch_id)
            if batch is None:
                st.warning('This batch is not present in the configured database.')
            else:
                st.caption(f"Batch #{batch['id']} · status {batch['status']} · "
                           f"expected files {batch['expected_files']} · reported {len(batch['report'])}")
                st.dataframe(pd.DataFrame(batch['report']), hide_index=True, width='stretch')
        except DatabaseError as error:
            st.warning(str(error))
    st.caption('ZIP imports started before checkpoints existed are not represented. '
               'A crash may leave a committed batch without a checkpoint batch ID. '
               'Inspect history before any retry.')
