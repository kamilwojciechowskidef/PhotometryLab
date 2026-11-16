"""Explicit batch import and persisted history controls."""
import pandas as pd
import streamlit as st

from .artifacts import artifact_root
from .database import database_url, DatabaseError
from .bulk import prepare_files, import_batch, batch_history
from .zip_products import import_product_zip
from .catalogue_controls import invalidate_catalogue_cache

MAX_BROWSER_ZIP_BYTES = 500_000_000


def render_bulk_import(version):
    st.subheader('Import and save to catalogue')
    st.caption('Selecting files does not save them. Enter a source and press the save button below.')
    st.caption('Up to 500 entries and 100 MB expanded per ZIP. For large collections use the local-folder worker below.')
    if st.checkbox('Import a large local ZIP folder', key='large_zip_instructions'):
        st.caption('Use a folder on the machine running the app. The worker reads one ZIP at a time and keeps archive-level checkpoints; there is no total dataset-size limit.')
        st.code('.venv\\Scripts\\python.exe -m photolab.zip_import "C:\\path\\to\\zips" --source "Dataset source" --recursive', language='powershell')
        st.caption('Replace the folder and source. Interrupted or uncertain archives need review; do not start two workers with --retry-uncertain.')
    uploads = st.file_uploader('Batch IES/LDT files', type=['ies', 'ldt'], accept_multiple_files=True, key='batch_files')
    archives = st.file_uploader('Or multiple ZIP archives', type=['zip'], accept_multiple_files=True, key='batch_zips')
    description = st.text_input('Batch source / provenance', key='batch_description')
    if st.button('Import and save to catalogue', key='import_batch', type='primary'):
        try:
            if uploads and archives:
                raise ValueError('Choose individual files or ZIP archives, not both.')
            if not description.strip():
                raise ValueError('Describe the source of this batch before importing.')
            if archives:
                if sum(archive.size for archive in archives) > MAX_BROWSER_ZIP_BYTES:
                    raise ValueError('Browser ZIP uploads exceed 500 MB. Use the local-folder worker for large collections.')
                summaries = []
                for number, archive in enumerate(archives, 1):
                    st.write(f'Archive {number}/{len(archives)}: {archive.name}')
                    try:
                        batch_id, rows, groups, skipped = import_product_zip(
                            database_url(), archive.getvalue(), artifact_root(),
                            f'{description.strip()} / {archive.name}', version)
                        invalidate_catalogue_cache()
                        summaries.append(dict(archive=archive.name, batch_id=batch_id,
                            bundles=len(groups), photometry_files=len(rows) - len(skipped), skipped=len(skipped),
                            new=sum(r['outcome'] == 'new' for r in rows),
                            duplicate=sum(r['outcome'] == 'duplicate' for r in rows),
                            rejected=sum(r['outcome'] == 'rejected' for r in rows),
                            errors=sum(r['outcome'] in ('error', 'skipped', 'rejected') for r in rows)))
                    except (ValueError, OSError, DatabaseError) as error:
                        # A failed archive may already have committed some photometry.
                        invalidate_catalogue_cache()
                        summaries.append(dict(archive=archive.name, error=str(error)))
                st.dataframe(pd.DataFrame(summaries), hide_index=True)
                if all(not item.get('error') and not item.get('errors') for item in summaries):
                    st.success('Import completed and saved to the catalogue. Check the archive summary.')
                else:
                    st.warning('Some archives or files were not saved successfully. Check the archive summary and batch history.')
                st.download_button('Download archive summary', pd.DataFrame(summaries).to_csv(index=False).encode('utf-8-sig'),
                                   file_name='archive_summary.csv', mime='text/csv')
                return
            files = prepare_files([(u.name, u.getvalue()) for u in uploads or []])
            progress = st.progress(0.0)
            batch_id, rows = import_batch(database_url(), files, artifact_root(), description.strip(), version,
                                         progress=lambda done, total: progress.progress(done / total))
            invalidate_catalogue_cache()
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
