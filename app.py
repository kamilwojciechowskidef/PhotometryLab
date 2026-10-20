"""Local Streamlit UI for reproducible photometric file comparisons."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from photolab.analysis import (C_GRID, GAMMA_GRID, compare, embedding,
                               estimated_downward_lumens, find_similar,
                               shape_matrix)
from photolab.demo import samples
from photolab.identifiers import identify_files
from photolab.parsers import PhotometryError, load_photometry
from photolab.quality import assess_quality, rejected_file_report

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
for upload in files or []:
    name = upload.name
    if name in payload:
        stem, suffix = name.rsplit(".", 1)
        counter = 2
        while f"{stem} ({counter}).{suffix}" in payload:
            counter += 1
        name = f"{stem} ({counter}).{suffix}"
    payload[name] = upload.getvalue()

identities_by_filename = {identity.filename: identity for identity in identify_files(payload)}
parsed = []
quality_reports = []
for name, content in payload.items():
    try:
        item = load_photometry(name, content)
        parsed.append(item)
        quality_reports.append(assess_quality(item))
    except PhotometryError as error:
        quality_reports.append(rejected_file_report(name, str(error)))

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

t1, t2, t3 = st.tabs(["Comparison and ranking", "Catalogue and data quality", "ML exploration (experimental)"])

with t1:
    if len(eligible) < 2:
        st.info("Ranking requires at least two files with γ = 0–90° data.")
    else:
        selected = st.selectbox("Reference luminaire", [i.filename for i in eligible], key="ref_file")
        ref = next(i for i in eligible if i.filename == selected)
        results = find_similar(ref, eligible, allow_rotation)
        result_df = pd.DataFrame([{
            "Rank": no + 1, "Candidate": r.filename,
            "Cosine (1 = identical)": round(r.cosine, 5), "RMSE (0 = identical)": round(r.rmse, 5),
            "Rotation [°]": r.rotation_deg,
        } for no, r in enumerate(results)])
        st.subheader("Most similar distributions")
        st.dataframe(result_df, use_container_width=True, hide_index=True)
        csv_data = result_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button("Download ranking CSV", csv_data, file_name="photometry_ranking.csv",
                           mime="text/csv")
        candidate_name = st.selectbox("Compare with candidate", result_df["Candidate"].tolist())
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
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Each luminaire matrix is independently scaled to maximum = 1. "
                   "Comparison: C every 10°, γ = 0–90° every 5°. Angular weights: sin(γ). "
                   "Rotation is aligned by minimizing RMSE.")
        h = go.Figure(data=go.Heatmap(x=GAMMA_GRID, y=C_GRID, z=ref_a,
                                      colorbar=dict(title="I / Imax"), colorscale="Viridis"))
        h.update_layout(title=f"Distribution map · {ref.filename}", height=360,
                        xaxis_title="γ [°]", yaxis_title="C [°]", margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(h, use_container_width=True)

with t2:
    table_rows = []
    items_by_filename = {item.filename: item for item in parsed}
    for report in quality_reports:
        item = items_by_filename.get(report.filename)
        identity = identities_by_filename[report.filename]
        down = estimated_downward_lumens(item) if item is not None else None
        table_rows.append({
            "File": report.filename, "Quality status": report.status,
            "SHA-256": identity.sha256,
            "Size [bytes]": identity.size_bytes,
            "Duplicate of": identity.duplicate_of or "no",
            "Ready to compare": "yes" if report.comparison_ready else "no",
            "Format": item.format if item is not None else "unavailable — file rejected",
            "Manufacturer": item.manufacturer if item is not None else "unavailable",
            "Model": item.luminaire if item is not None else "unavailable",
            "C planes": len(item.c_angles) if item is not None else "unavailable",
            "Gamma angles": len(item.gamma_angles) if item is not None else "unavailable",
            "Symmetry": item.symmetry if item is not None else "unavailable",
            "Source unit": item.unit if item is not None else "unavailable",
            "Power [W]": round(item.power_w, 2) if item is not None and item.power_w is not None else "unavailable",
            "Header flux [lm]": round(item.source_flux_lm, 1) if item is not None and item.source_flux_lm is not None else "unavailable",
            "Calculated downward flux [lm]": round(down, 1) if down is not None else "unavailable",
            "Covers γ 0–90°": "yes" if item is not None and item.covers_downward else "no",
            "Reasons / warnings": " | ".join(report.issues) or "none",
        })
    quality_df = pd.DataFrame(table_rows)
    st.dataframe(quality_df, use_container_width=True, hide_index=True)
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
        st.plotly_chart(fig_ml, use_container_width=True)
        st.caption(f"Explained variance: PC1 {explained[0]*100:.1f}%, PC2 {explained[1]*100:.1f}%")
        st.dataframe(ml_data, use_container_width=True, hide_index=True)
        st.download_button("Download ML results CSV", ml_data.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           "ml_results.csv", mime="text/csv")

st.divider()
st.caption("PhotometryLab 0.1 · Research use / prototype · Sample data are synthetic only")
