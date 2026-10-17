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
from photolab.parsers import PhotometryError, load_photometry
from photolab.quality import assess_quality

st.set_page_config(page_title="PhotometryLab | Analiza rozsyłów", page_icon="💡", layout="wide")

st.title("💡 PhotometryLab")
st.caption("Wersja badawcza 0.1 · Porównywanie plików IES i LDT · Wszystkie obliczenia wykonywane lokalnie")
st.write("Wczytaj pliki fotometryczne, wybierz oprawę odniesienia, a następnie porównaj jej rozsył z pozostałymi. ")

with st.sidebar:
    st.header("1. Zbiór opraw")
    files = st.file_uploader("Import plików .ies i .ldt", type=["ies", "ldt"], accept_multiple_files=True,
                             help="Jeden plik maksymalnie 5 MB. Pliki nie są wysyłane do zewnętrznego API AI.")
    with_demo = st.checkbox("Dołącz syntetyczne pliki demonstracyjne", value=not bool(files),
                            help="Próbki służą do sprawdzania aplikacji, nie do wnioskowania naukowego.")
    allow_rotation = st.checkbox("Dopasuj obrót C (co 10°)", value=True,
                                 help="Pozwala dopasować różne orientacje układów fotometrycznych producentów.")
    st.divider()
    st.caption("Obsługa: IES LM-63 typu C z TILT=NONE oraz wybrane warianty EULUMDAT LDT. Nieobsługiwane pliki są jawnie odrzucane.")

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

parsed = []
errors = []
for name, content in payload.items():
    try:
        parsed.append(load_photometry(name, content))
    except PhotometryError as error:
        errors.append((name, str(error)))

if errors:
    with st.expander(f"Nie udało się wczytać {len(errors)} plików", expanded=True):
        for name, message in errors:
            st.warning(f"**{name}**: {message}")

if not parsed:
    st.info("Dodaj własne pliki po lewej albo włącz zestaw demonstracyjny.")
    st.stop()

eligible = []
excluded = []
quality_reports = {}
for item in parsed:
    report = assess_quality(item)
    quality_reports[item.filename] = report
    if report.comparison_ready:
        eligible.append(item)
    else:
        excluded.append((item.filename, " | ".join(report.issues)))

m1, m2, m3 = st.columns(3)
m1.metric("Pliki odczytane", len(parsed))
m2.metric("Oprawy do porównania", len(eligible))
m3.metric("Wymagają uzupełnienia danych", len(errors)+len(excluded))
if excluded:
    with st.expander("Pliki odczytane, ale wyłączone z porównania"):
        for name, message in excluded:
            st.write(f"**{name}**: {message}")

st.warning("**Interpretacja:** Ranking porównuje przede wszystkim **kształt rozsyłu**, a nie pełną równoważność opraw. "
           "Dobór zamiennika wymaga także sprawdzenia strumienia, mocy, barwy, gabarytów, klasy ochrony i obliczeń oświetleniowych.")

t1, t2, t3 = st.tabs(["Porównanie i ranking", "Katalog i jakość danych", "Eksploracja ML (eksperymentalna)"])

with t1:
    if len(eligible) < 2:
        st.info("Do rankingu potrzebne są co najmniej dwa pliki z danymi dla γ = 0–90°.")
    else:
        selected = st.selectbox("Oprawa odniesienia", [i.filename for i in eligible], key="ref_file")
        ref = next(i for i in eligible if i.filename == selected)
        results = find_similar(ref, eligible, allow_rotation)
        result_df = pd.DataFrame([{
            "Miejsce": no + 1,
            "Kandydat": r.filename,
            "Cosinus (1 = zgodne)": round(r.cosine, 5),
            "RMSE (0 = zgodne)": round(r.rmse, 5),
            "Obrót [°]": r.rotation_deg,
        } for no, r in enumerate(results)])
        st.subheader("Ranking najbardziej podobnych rozsyłów")
        st.dataframe(result_df, use_container_width=True, hide_index=True)
        csv_data = result_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button("Pobierz ranking CSV", csv_data, file_name="ranking_fotometrii.csv",
                           mime="text/csv")
        candidate_name = st.selectbox("Porównaj z kandydatem", result_df["Kandydat"].tolist())
        cand = next(i for i in eligible if i.filename == candidate_name)
        score = compare(ref, cand, allow_rotation)
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Podobieństwo cosinusowe", f"{score.cosine:.4f}")
        col_b.metric("Ważony RMSE", f"{score.rmse:.4f}")
        col_c.metric("Dopasowany obrót", f"{score.rotation_deg}°")
        ref_a = shape_matrix(ref)
        cand_a = np.roll(shape_matrix(cand), score.rotation_deg // 10, axis=0)
        fig = go.Figure()
        for idx, plane in ((0, "C0"), (9, "C90")):
            fig.add_trace(go.Scatter(x=GAMMA_GRID, y=ref_a[idx], mode="lines+markers",
                                     name=f"Odniesienie · {plane}"))
            fig.add_trace(go.Scatter(x=GAMMA_GRID, y=cand_a[idx], mode="lines",
                                     line=dict(dash="dash"), name=f"Kandydat · {plane}"))
        fig.update_layout(title="Porównanie przekrojów po dopasowaniu obrotu", height=430,
                          xaxis_title="Kąt γ [°]", yaxis_title="Światłość / maksimum [-]",
                          legend=dict(orientation="h", y=-0.3), margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Macierze każdej oprawy są niezależnie skalowane do maksimum = 1. "
                   "Porównanie: C co 10°, γ = 0–90° co 5°. Wagi kątowe: sin(γ). "
                   "Obrót dopasowany przez minimalizację RMSE.")
        h = go.Figure(data=go.Heatmap(x=GAMMA_GRID, y=C_GRID, z=ref_a,
                                      colorbar=dict(title="I / Imax"), colorscale="Viridis"))
        h.update_layout(title=f"Mapa rozsyłu · {ref.filename}", height=360,
                        xaxis_title="γ [°]", yaxis_title="C [°]", margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(h, use_container_width=True)

with t2:
    table_rows = []
    for item in parsed:
        down = estimated_downward_lumens(item)
        table_rows.append({
            "Plik": item.filename, "Format": item.format, "Producent": item.manufacturer,
            "Model": item.luminaire, "C-plane": len(item.c_angles),
            "Kąty γ": len(item.gamma_angles), "Symetria": item.symmetry,
            "Jednostka źródłowa": item.unit,
            "Moc [W]": round(item.power_w, 2) if item.power_w is not None else "brak",
            "Strumień nagłówkowy [lm]": round(item.source_flux_lm, 1) if item.source_flux_lm is not None else "brak",
            "Strumień dolny obliczony [lm]": round(down, 1) if down is not None else "brak",
            "Pokrywa γ 0–90°": "tak" if item.covers_downward else "nie",
            "Status jakości": quality_reports[item.filename].status,
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    st.caption("Strumień dolny jest przybliżeniem numerycznym z rozsyłu w cd, a wartość z nagłówka może mieć inne znaczenie. "
               "Nie są to wyniki pomiaru ani deklarowana przez producenta skuteczność oprawy.")
    with st.expander("Ostrzeżenia i ograniczenia plików"):
        for item in parsed:
            issues = quality_reports[item.filename].issues
            if issues:
                st.write(f"**{item.filename}**")
                for note in issues:
                    st.caption("• " + note)
            else:
                st.caption(f"{item.filename}: brak dodatkowych ostrzeżeń parsera.")

with t3:
    st.write("Rzutowanie PCA i grupowanie KMeans służą do **eksploracji zbioru**. "
             "Wykrywanie odstających opraw Isolation Forest uruchamia się od 8 plików. "
             "Na próbkach demonstracyjnych wynik nie jest oceną skuteczności modeli.")
    if len(eligible) < 3:
        st.info("Potrzebne są przynajmniej 3 porównywalne oprawy.")
    else:
        groups = st.slider("Liczba grup KMeans", min_value=2, max_value=min(6, len(eligible)-1),
                           value=min(3, len(eligible)-1))
        xy, clusters, anomalies, explained = embedding(eligible, groups)
        ml_data = pd.DataFrame({
            "Plik": [i.filename for i in eligible], "PC1": xy[:,0], "PC2": xy[:,1],
            "Klaster": [f"Grupa {x+1}" for x in clusters],
            "Odstająca": ["tak" if bool(v) else "nie" for v in anomalies] if anomalies is not None else ["nie oceniano"]*len(eligible),
        })
        fig_ml = px.scatter(ml_data, x="PC1", y="PC2", color="Klaster", symbol="Odstająca",
                            hover_name="Plik", title="PCA · cechy rozsyłu fotometrycznego")
        fig_ml.update_traces(marker=dict(size=12))
        fig_ml.update_layout(height=480)
        st.plotly_chart(fig_ml, use_container_width=True)
        st.caption(f"Wyjaśniona wariancja: PC1 {explained[0]*100:.1f}%, PC2 {explained[1]*100:.1f}%")
        st.dataframe(ml_data, use_container_width=True, hide_index=True)
        st.download_button("Pobierz wyniki ML CSV", ml_data.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           "wyniki_ml.csv", mime="text/csv")

st.divider()
st.caption("PhotometryLab 0.1 · Zastosowanie badawcze / prototyp · Dane przykładowe są wyłącznie syntetyczne")
