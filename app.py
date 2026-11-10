"""Local Streamlit UI for reproducible photometric file comparisons."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dataclasses import replace
from pathlib import PureWindowsPath
from photolab.artifacts import artifact_root, read_source, ArtifactError
from photolab.database import list_sources

from photolab.analysis import (C_GRID, GAMMA_GRID, compare, embedding,
                               estimated_downward_lumens, find_similar,
                               shape_matrix)
from photolab.demo import samples
from photolab.database import DatabaseError, database_url, register_file_import
from photolab.database import list_catalogue, load_stored_photometries
from photolab.indexing import rank_catalogue
from photolab.identifiers import identify_file
from photolab.parsers import PhotometryError, load_photometry
from photolab.quality import assess_quality, rejected_file_report
from photolab.product_labels import product_label
from photolab.catalogue_controls import BRAND_LIMIT, get_brands, get_count, select_page


APP_VERSION = "0.1"

st.set_page_config(page_title="PhotometryLab | Photometric Analysis", page_icon="💡", layout="wide")

st.title("💡 PhotometryLab")
st.caption("Research version 0.1 · IES and LDT comparison · All calculations run locally")
st.write("Upload photometric files, choose a reference luminaire, and compare its distribution with the others.")

with st.sidebar:
    st.header("1. Luminaire set")
    files = st.file_uploader("Upload .ies and .ldt files", type=["ies", "ldt"], accept_multiple_files=True,
                             help="Maximum size: 5 MB per file. Files are not sent to an external AI API.")
    with_demo = st.checkbox("Include synthetic demonstration files", value=not bool(files),
                            help="Samples are for testing the application, not for scientific conclusions.")
    allow_rotation = st.checkbox("Align C rotation (10° steps)", value=True,
                                 help="Aligns different manufacturer orientations of photometric coordinate systems.")
    st.divider()
    st.caption("Supported: IES LM-63 Type C with TILT=NONE and selected EULUMDAT LDT variants. Unsupported files are explicitly rejected.")

payload: dict[str, bytes] = samples() if with_demo else {}
uploaded_records: dict[str, tuple[str, bytes]] = {}
for upload in files or []:
    original_name = upload.name
    name = original_name
    if name in payload:
        stem, suffix = name.rsplit(".", 1)
        counter = 2
        while f"{stem} ({counter}).{suffix}" in payload:
            counter += 1
        name = f"{stem} ({counter}).{suffix}"
    content = upload.getvalue()
    payload[name] = content
    uploaded_records[name] = (original_name, content)

parsed = []
quality_reports = []
for name, content in payload.items():
    try:
        item = load_photometry(name, content)
        parsed.append(item)
        quality_reports.append(assess_quality(item))
    except PhotometryError as error:
        quality_reports.append(rejected_file_report(name, str(error)))

with st.sidebar:
    session_state = getattr(st, 'session_state', {})
    selected_catalogue = session_state.setdefault('selected_catalogue_files', {})
    browse_catalogue = st.checkbox("Browse saved catalogue", value=False, key="browse_catalogue")
    if browse_catalogue:
        try:
            catalogue_url = database_url()
            brand_search = st.text_input("Find manufacturer", key="sidebar_brand_search")
            brands = get_brands(catalogue_url, brand_search)
            if len(brands) == BRAND_LIMIT:
                st.caption('Showing the first 500 manufacturers. Refine the search to find others.')
            manufacturer_filter = st.selectbox("Manufacturer", [None, *brands], key='sidebar_brand',
                format_func=lambda brand: brand if brand is not None else 'All manufacturers')
            model_filter = st.text_input("Catalogue number or model contains", key='sidebar_model')
            total = get_count(catalogue_url, manufacturer_filter or '', model_filter)
            st.caption(f'{total:,} matching photometry file(s).')
            page = select_page(st, total, key=f'sidebar_page_{manufacturer_filter}_{model_filter}')
            catalogue_rows = list_catalogue(catalogue_url, manufacturer=manufacturer_filter or '',
                                           manufacturer_exact=bool(manufacturer_filter), model=model_filter,
                                           offset=(int(page) - 1) * 50)
            if not catalogue_rows:
                st.info("No saved photometry on this page. Earlier metadata-only imports must be uploaded and saved again.")
            else:
                choices = {row['file_id']: row for row in catalogue_rows}
                selected_ids = st.multiselect(
                    "Choose saved luminaires on this page", list(choices),
                    format_func=lambda file_id: f"{choices[file_id]['manufacturer']} · {choices[file_id].get('catalogue_number') or choices[file_id]['model'] or 'Unavailable'} · #{file_id}",
                )
                if st.button('Add selected to comparison', key='add_catalogue_selection'):
                    new_ids = [file_id for file_id in selected_ids if file_id not in selected_catalogue]
                    if len(selected_catalogue) + len(new_ids) > 20:
                        st.warning('Select at most 20 saved photometry files for the local comparison.')
                    elif not selected_ids:
                        st.info('Choose at least one saved luminaire above first.')
                    else:
                        for file_id in new_ids:
                            row = choices[file_id]
                            selected_catalogue[file_id] = {
                                'sha256': row['sha256'], 'filename': row['filename'],
                                'label': f"#{file_id} · {row['manufacturer']} · {row.get('catalogue_number') or row['model'] or 'Unavailable'}",
                            }
                        session_state['select_catalogue_reference'] = selected_ids[0]
                        st.success(f'{len(new_ids)} saved file(s) added to the comparison set.')
                st.caption('Choose entries, then press Add selected. Saved choices persist when changing page or filters.')
                st.caption('Older entries may show the source description in place of a catalogue number.')
                with st.expander('Show current page table'):
                    st.dataframe(pd.DataFrame([{
                        'ID': row['file_id'], 'Brand': row['manufacturer'],
                        'Catalogue / model': row.get('catalogue_number') or row['model'] or 'Unavailable',
                    } for row in catalogue_rows]), hide_index=True, width='stretch')
        except DatabaseError as error:
            st.error(str(error))

    if selected_catalogue:
        st.caption(f"Saved files in comparison: {len(selected_catalogue)} / 20")
        for record in selected_catalogue.values():
            st.caption(record['label'])
        if st.button('Clear saved comparison set', key='clear_catalogue_selection'):
            selected_catalogue.clear()
            session_state.pop('select_catalogue_reference', None)

    st.divider()
    if st.checkbox('Import and save ZIP files', value=False, key='open_bulk'):
        from photolab.bulk_ui import render_bulk_import
        render_bulk_import(APP_VERSION)

if selected_catalogue:
    try:
        saved_items = load_stored_photometries(database_url(), list(selected_catalogue))
        loaded_hashes = {identify_file(content).sha256 for content in payload.values()}
        used_names = set(payload)
        for file_id, record in selected_catalogue.items():
            saved = saved_items.get(file_id)
            if saved is None:
                st.warning(f'#{file_id}: stored photometry is missing or invalid; it was not added.')
                continue
            if record['sha256'] in loaded_hashes:
                st.info(f'#{file_id}: identical file already in the comparison set.')
                continue
            name = f'[DB {file_id}] {saved.filename}'
            while name in used_names:
                name = '[DB] ' + name
            used_names.add(name)
            saved = replace(saved, filename=name)
            parsed.append(saved)
            quality_reports.append(assess_quality(saved))
            loaded_hashes.add(record['sha256'])
    except DatabaseError as error:
        st.error(str(error))

eligible = []
excluded = []
reports_by_filename = {report.filename: report for report in quality_reports}
for item in parsed:
    report = reports_by_filename[item.filename]
    if report.comparison_ready:
        eligible.append(item)
    else:
        excluded.append((item.filename, " | ".join(report.issues)))

m1, m2, m3 = st.columns(3)
m1.metric("Files read", len(parsed))
m2.metric("Luminaires ready to compare", len(eligible))
m3.metric("Limited or rejected", len(quality_reports)-len(eligible))
if excluded:
    with st.expander("Files read but excluded from comparison"):
        for name, message in excluded:
            st.write(f"**{name}**: {message}")

st.warning("**Interpretation:** The ranking compares primarily the **distribution shape**, not full luminaire equivalence. "
           "Selecting a replacement also requires checking flux, power, colour, geometry, protection class, and lighting calculations.")

t0, t1, t2, t3, t4 = st.tabs(["Saved catalogue", "Comparison and ranking", "Catalogue and data quality",
                             "ML exploration (experimental)", "Photometric diagnostics"])

with t0:
    st.subheader('Saved photometry catalogue')
    st.caption('Persistent catalogue from PostgreSQL. ZIP imports and individually saved files remain available after restarting the app.')
    try:
        main_url = database_url()
        main_total = get_count(main_url)
        st.caption(f'{main_total:,} saved photometry file(s).')
        catalogue_page_main = select_page(st, main_total, key='main_page')
        main_rows = list_catalogue(main_url, limit=50, offset=(int(catalogue_page_main) - 1) * 50)
        if main_rows:
            st.dataframe(pd.DataFrame([{
                'ID': row['file_id'], 'Brand': row['manufacturer'],
                'Catalogue / model': row.get('catalogue_number') or row['model'] or 'Unavailable',
                'Format': row['format'],
            } for row in main_rows]), width='stretch', hide_index=True)
            st.caption('Select a saved entry for comparisons through Browse saved catalogue in the sidebar. '
                       'Each IES or LDT is a separate photometry entry.')
            main_choices = {row['file_id']: row for row in main_rows}
            main_file = st.selectbox('Saved photometry details', list(main_choices),
                format_func=lambda key: f"#{key} · {main_choices[key]['manufacturer']} · "
                                        f"{main_choices[key].get('catalogue_number') or main_choices[key]['model'] or 'Unavailable'}",
                key='catalogue_main_file')
            st.caption(f"Original filename: {main_choices[main_file]['filename']}")
            if st.checkbox('Show associated ZIP assets', key='catalogue_assets'):
                from photolab.zip_products import list_related_bundles, load_bundle, preview_image
                try:
                    bundles = list_related_bundles(database_url(), main_file)
                    if not bundles:
                        st.info('No ZIP bundle is linked to this file. Older imports remain accessible as photometry.')
                    else:
                        bundle_names = dict(bundles)
                        selected_bundle = st.selectbox('Import bundle', list(bundle_names),
                            format_func=lambda key: f"#{key} · {bundle_names[key]}")
                        metadata, assets = load_bundle(database_url(), selected_bundle)
                        st.dataframe(pd.DataFrame(assets).drop(columns=['sha256']), width='stretch', hide_index=True)
                        if metadata is not None:
                            with st.expander('Original JSON metadata'):
                                st.json(metadata)
                        pictures = [asset for asset in assets if asset['kind'] in ('jpg', 'png')]
                        if pictures:
                            photo_by_name = {asset['filename']: asset for asset in pictures}
                            photo = st.selectbox('Product image', list(photo_by_name))
                            st.image(preview_image(artifact_root(), photo_by_name[photo]), caption=photo)
                        st.caption('ZIP group is based on archive path and filename; '
                                   'it does not prove that IES and LDT describe identical photometry.')
                except (DatabaseError, ArtifactError, OSError, ValueError) as error:
                    st.warning(str(error))
        else:
            st.info('No saved photometry on this page. Import a ZIP or save uploaded files first.')
    except DatabaseError as error:
        st.info(f'Catalogue unavailable: {error}')

with t4:
    from photolab.diagnostics_ui import render_diagnostics
    render_diagnostics(st, parsed)

with t1:
    if eligible:
        eligible_by_filename = {i.filename: i for i in eligible}
        requested_reference = session_state.pop('select_catalogue_reference', None)
        if requested_reference is not None:
            prefix = f'[DB {requested_reference}] '
            match = next((item.filename for item in eligible if item.filename.startswith(prefix)), None)
            if match is not None:
                session_state['ref_file'] = match
        selected = st.selectbox("Reference luminaire", list(eligible_by_filename), key="ref_file",
                                format_func=lambda name: product_label(eligible_by_filename[name]))
        ref = next(i for i in eligible if i.filename == selected)
        if st.button("Search indexed catalogue", key="search_indexed_catalogue"):
            try:
                catalogue_search = rank_catalogue(database_url(), ref, allow_rotation=allow_rotation)
                indexed_df = pd.DataFrame([{
                    "Catalogue ID": file_id,
                    "Candidate": score.filename,
                    "Brand": score.manufacturer or "unavailable",
                    "Catalogue number": score.catalogue_number or "unavailable",
                    "Cosine (1 = identical)": round(score.cosine, 5),
                    "RMSE (0 = identical)": round(score.rmse, 5),
                    "Rotation [°]": score.rotation_deg,
                } for file_id, score in catalogue_search.results])
                if indexed_df.empty:
                    st.info("No indexed candidates were found. Build features for the saved catalogue first.")
                else:
                    st.subheader("Indexed catalogue candidates")
                    st.dataframe(indexed_df, width='stretch', hide_index=True)
                    st.download_button("Download indexed catalogue CSV", indexed_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                                       file_name="catalogue_ranking.csv", mime="text/csv")
                    st.caption(
                        f"Exact metrics were calculated for {catalogue_search.candidates_examined} candidates "
                        "retrieved from the feature index. This is a candidate search, not an exhaustive scan of the full catalogue."
                    )
            except (DatabaseError, ValueError) as error:
                st.error(str(error))
    if len(eligible) < 2:
        st.info("Local ranking requires at least two files with γ = 0–90° data. Indexed catalogue search works with one reference file.")
    else:
        results = find_similar(ref, eligible, allow_rotation)
        result_df = pd.DataFrame([{
            "Rank": no + 1, "Candidate": r.filename,
            "Brand": r.manufacturer or "unavailable", "Catalogue number": r.catalogue_number or "unavailable",
            "Cosine (1 = identical)": round(r.cosine, 5), "RMSE (0 = identical)": round(r.rmse, 5),
            "Rotation [°]": r.rotation_deg,
        } for no, r in enumerate(results)])
        st.subheader("Most similar distributions")
        st.dataframe(result_df, width='stretch', hide_index=True)
        csv_data = result_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button("Download ranking CSV", csv_data, file_name="photometry_ranking.csv",
                           mime="text/csv")
        candidate_name = st.selectbox("Compare with candidate", result_df["Candidate"].tolist(),
                                      format_func=lambda name: product_label(eligible_by_filename[name]))
        cand = next(i for i in eligible if i.filename == candidate_name)
        score = compare(ref, cand, allow_rotation)
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Cosine similarity", f"{score.cosine:.4f}")
        col_b.metric("Weighted RMSE", f"{score.rmse:.4f}")
        col_c.metric("Aligned rotation", f"{score.rotation_deg}°")
        ref_a = shape_matrix(ref)
        cand_a = np.roll(shape_matrix(cand), score.rotation_deg // 10, axis=0)
        fig = go.Figure()
        for idx, plane in ((0, "C0"), (9, "C90")):
            fig.add_trace(go.Scatter(x=GAMMA_GRID, y=ref_a[idx], mode="lines+markers",
                                     name=f"Reference · {plane}"))
            fig.add_trace(go.Scatter(x=GAMMA_GRID, y=cand_a[idx], mode="lines",
                                     line=dict(dash="dash"), name=f"Candidate · {plane}"))
        fig.update_layout(title="Cross-section comparison after rotation alignment", height=430,
                          xaxis_title="Gamma angle γ [°]", yaxis_title="Intensity / maximum [-]",
                          legend=dict(orientation="h", y=-0.3), margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(fig, width='stretch')
        st.caption("Each luminaire matrix is independently scaled to maximum = 1. "
                   "Comparison: C every 10°, γ = 0–90° every 5°. Angular weights: sin(γ). "
                   "Rotation is aligned by minimizing RMSE.")
        h = go.Figure(data=go.Heatmap(x=GAMMA_GRID, y=C_GRID, z=ref_a,
                                      colorbar=dict(title="I / Imax"), colorscale="Viridis"))
        h.update_layout(title=f"Distribution map · {ref.filename}", height=360,
                        xaxis_title="γ [°]", yaxis_title="C [°]", margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(h, width='stretch')

with t2:
    table_rows = []
    items_by_filename = {item.filename: item for item in parsed}
    for report in quality_reports:
        item = items_by_filename.get(report.filename)
        down = estimated_downward_lumens(item) if item is not None else None
        table_rows.append({
            "File": report.filename, "Quality status": report.status,
            "Ready to compare": "yes" if report.comparison_ready else "no",
            "Format": item.format if item is not None else "unavailable — file rejected",
            "Manufacturer": item.manufacturer if item is not None else "unavailable",
            "Catalogue number": item.catalogue_number or "unavailable" if item is not None else "unavailable",
            "Model": item.luminaire if item is not None else "unavailable",
            "C planes": len(item.c_angles) if item is not None else None,
            "Gamma angles": len(item.gamma_angles) if item is not None else None,
            "Symmetry": item.symmetry if item is not None else "unavailable",
            "Source unit": item.unit if item is not None else "unavailable",
            "Power [W]": round(item.power_w, 2) if item is not None and item.power_w is not None else None,
            "Header flux [lm]": round(item.source_flux_lm, 1) if item is not None and item.source_flux_lm is not None else None,
            "Calculated downward flux [lm]": round(down, 1) if down is not None else None,
            "Covers γ 0–90°": "yes" if item is not None and item.covers_downward else "no",
            "Reasons / warnings": " | ".join(report.issues) or "none",
        })
    quality_df = pd.DataFrame(table_rows)
    if not quality_df.empty:
        quality_df = quality_df.astype({
            'C planes': 'Int64', 'Gamma angles': 'Int64',
            'Power [W]': 'Float64', 'Header flux [lm]': 'Float64',
            'Calculated downward flux [lm]': 'Float64',
        })
    st.dataframe(quality_df, width='stretch', hide_index=True)
    st.caption('Missing numeric values are shown as empty cells and exported as empty CSV fields; they are not zero.')
    st.download_button("Download quality report CSV", quality_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name="import_quality_report.csv", mime="text/csv")
    st.caption("Downward flux is a numerical estimate from the intensity distribution in cd; the header value may have a different meaning. "
               "Neither value is a measurement result or a manufacturer-declared luminaire efficacy.")
    with st.expander("File warnings and limitations"):
        for report in quality_reports:
            if report.issues:
                st.write(f"**{report.filename}** ({report.status})")
                for note in report.issues:
                    st.caption("• " + note)
            else:
                st.caption(f"{report.filename}: no additional parser warnings.")

    st.divider()
    st.subheader("Local PostgreSQL catalogue")
    st.caption("Only files uploaded in this session can be saved. Synthetic demonstration files are excluded. "
               "Original bytes are archived locally; PostgreSQL stores photometry, quality reports and source references.")
    if not uploaded_records:
        st.info("Upload at least one IES or LDT file to save it to the local catalogue.")
    elif st.button("Save uploaded files to PostgreSQL", type="primary"):
        saved_new = 0
        saved_duplicates = 0
        save_errors = []
        try:
            url = database_url()
        except DatabaseError as error:
            save_errors.append(str(error))
        else:
            for display_name, (original_name, content) in uploaded_records.items():
                item = items_by_filename.get(display_name)
                try:
                    stored = register_file_import(
                        url,
                        original_filename=original_name,
                        content=content,
                        format_name=item.format if item is not None else None,
                        quality_report=reports_by_filename[display_name],
                        application_version=APP_VERSION,
                        photometry=item,
                        source_root=artifact_root(),
                        source_description="Streamlit upload",
                    )
                except (DatabaseError, ValueError, OSError) as error:
                    save_errors.append(f"{original_name}: {error}")
                    continue
                if stored.duplicate:
                    saved_duplicates += 1
                else:
                    saved_new += 1
        if saved_new:
            st.success(f"Added {saved_new} new file(s) to the catalogue.")
        if saved_duplicates:
            st.info(f"Detected {saved_duplicates} duplicate(s); added an import alias instead.")
        for message in save_errors:
            st.error(message)

    if st.checkbox("Browse source archive", value=False, key="browse_sources"):
        try:
            source_page = st.number_input('Source archive page', min_value=1, value=1, step=1)
            source_rows = list_sources(database_url(), offset=(int(source_page) - 1) * 50)
            if not source_rows:
                st.info('No source records on this page.')
            else:
                sources = {row['file_id']: row for row in source_rows}
                chosen = st.selectbox('Source file', list(sources),
                                      format_func=lambda key: f"#{key} · {sources[key]['filename']} · {sources[key]['status']}")
                source = sources[chosen]
                if not source['path']:
                    st.info('This legacy record has no archived source. Upload and save the original again.')
                else:
                    content = read_source(artifact_root(), source['sha256'], source['size_bytes'])
                    filename = PureWindowsPath(source['filename'] or 'source.ies').name
                    st.success('Source integrity verified: SHA-256 and size match.')
                    st.download_button('Download original source', content, file_name=filename,
                                       mime='application/octet-stream', key=f'source_download_{chosen}')
                    if st.button('Reparse source and preview quality', key=f'reparse_{chosen}'):
                        try:
                            reparsed = load_photometry(filename, content)
                            report = assess_quality(reparsed)
                        except PhotometryError as error:
                            report = rejected_file_report(filename, str(error))
                        st.write({'status': report.status, 'comparison_ready': report.comparison_ready,
                                  'downward_flux_ready': report.downward_flux_ready, 'issues': list(report.issues)})
                        st.caption('Preview uses the current parser. Stored photometry is unchanged.')
        except (DatabaseError, ArtifactError, OSError) as error:
            st.error(str(error))

with t3:
    st.write("PCA projection and KMeans clustering are for **dataset exploration**. "
             "Isolation Forest anomaly detection runs with at least 8 files. "
             "Results on demonstration samples are not an assessment of model performance.")
    if len(eligible) < 3:
        st.info("At least 3 comparable luminaires are required.")
    else:
        groups = st.slider("Number of KMeans groups", min_value=2, max_value=min(6, len(eligible)-1),
                           value=min(3, len(eligible)-1))
        xy, clusters, anomalies, explained = embedding(eligible, groups)
        ml_data = pd.DataFrame({
            "File": [i.filename for i in eligible], "PC1": xy[:,0], "PC2": xy[:,1],
            "Cluster": [f"Group {x+1}" for x in clusters],
            "Anomalous": ["yes" if bool(v) else "no" for v in anomalies] if anomalies is not None else ["not assessed"]*len(eligible),
        })
        fig_ml = px.scatter(ml_data, x="PC1", y="PC2", color="Cluster", symbol="Anomalous",
                            hover_name="File", title="PCA · photometric distribution features")
        fig_ml.update_traces(marker=dict(size=12))
        fig_ml.update_layout(height=480)
        st.plotly_chart(fig_ml, width='stretch')
        st.caption(f"Explained variance: PC1 {explained[0]*100:.1f}%, PC2 {explained[1]*100:.1f}%")
        st.dataframe(ml_data, width='stretch', hide_index=True)
        st.download_button("Download ML results CSV", ml_data.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           "ml_results.csv", mime="text/csv")

st.divider()
st.caption("PhotometryLab 0.1 · Research use / prototype · Sample data are synthetic only")
