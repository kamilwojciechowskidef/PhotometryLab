"""Explicit batch import and persisted history controls."""
import pandas as pd
import streamlit as st

from .artifacts import artifact_root
from .database import database_url, DatabaseError
from .bulk import prepare_files, prepare_zip, import_batch, batch_history


def render_bulk_import(version):
    st.subheader('Batch import')
    st.caption('Up to 500 entries, 5 MB per file and 100 MB per batch. ZIP files are read without extraction. Each file is committed separately.')
    uploads = st.file_uploader('Batch IES/LDT files', type=['ies', 'ldt'], accept_multiple_files=True, key='batch_files')
    archives = st.file_uploader('Or multiple ZIP archives', type=['zip'], accept_multiple_files=True, key='batch_zips')
    description = st.text_input('Batch source / provenance', key='batch_description')
    if st.button('Import batch', key='import_batch'):
        try:
            if uploads and archives:
                raise ValueError('Choose individual files or ZIP archives, not both.')
            if not description.strip():
                raise ValueError('Describe the source of this batch before importing.')
            if archives:
                if sum(archive.size for archive in archives) > 100_000_000:
                    raise ValueError('Browser ZIP uploads exceed 100 MB. Import smaller groups.')
                summaries = []
                for number, archive in enumerate(archives, 1):
                    st.write(f'Archive {number}/{len(archives)}: {archive.name}')
                    try:
                        files = prepare_zip(archive.getvalue())
                        batch_id, rows = import_batch(database_url(), files, artifact_root(),
                            f'{description.strip()} / {archive.name}', version)
                        summaries.append(dict(archive=archive.name, batch_id=batch_id,
                            files=len(rows), errors=sum(r['outcome'] in ('error', 'skipped', 'rejected') for r in rows)))
                        del files
                    except (ValueError, OSError, DatabaseError) as error:
                        summaries.append(dict(archive=archive.name, error=str(error)))
                st.dataframe(pd.DataFrame(summaries), hide_index=True)
                st.download_button('Download archive summary', pd.DataFrame(summaries).to_csv(index=False).encode('utf-8-sig'),
                                   file_name='archive_summary.csv', mime='text/csv')
                return
            files = prepare_files([(u.name, u.getvalue()) for u in uploads or []])
            progress = st.progress(0.0)
            batch_id, rows = import_batch(database_url(), files, artifact_root(), description.strip(), version,
                                         progress=lambda done, total: progress.progress(done / total))
            st.success(f'Batch #{batch_id} finished. See per-file outcomes below.')
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            st.download_button('Download batch report', pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),
                               file_name=f'batch_{batch_id}.csv', mime='text/csv')
        except (ValueError, OSError, DatabaseError) as error:
            st.error(str(error))
    if st.checkbox('Show batch history', key='batch_history'):
        try:
            page = st.number_input('History page', min_value=1, value=1, step=1)
            batches = batch_history(database_url(), (int(page) - 1) * 20)
            if not batches:
                st.info('No batches on this page.')
            else:
                st.dataframe(pd.DataFrame([{k: v for k, v in b.items() if k != 'report'} for b in batches]), hide_index=True)
                mapping = {b['id']: b for b in batches}
                chosen = st.selectbox('Batch report', list(mapping))
                report = pd.DataFrame(mapping[chosen]['report'])
                st.dataframe(report, hide_index=True)
                st.download_button('Download historical report', report.to_csv(index=False).encode('utf-8-sig'),
                                   file_name=f'batch_{chosen}.csv', mime='text/csv')
                st.caption('Running batches may be interrupted. Already committed files remain saved; reports can lag the last commit if the connection was lost.')
        except DatabaseError as error:
            st.error(str(error))
