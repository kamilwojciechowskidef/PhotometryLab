"""Plotly views of one photometry model; rendering does not write catalogue data."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .diagnostics import DIAGNOSTICS_VERSION, diagnose, distance_rows

COLORS = ('#0284c7', '#ea580c')


def polar_figure(result):
    figure = go.Figure()
    for section, color in zip(result.sections, COLORS):
        label = f'C{section.plane}-C{section.plane + 180}'
        # Separate traces preserve gaps where gamma=0/180 was not measured.
        for positive, values in ((True, section.positive), (False, section.negative)):
            figure.add_trace(go.Scatterpolar(
                theta=section.gamma if positive else -section.gamma, r=values,
                mode='lines', name=label, legendgroup=label, showlegend=positive,
                line=dict(color=color, dash='solid' if section.plane == 0 else 'dash'),
                customdata=np.column_stack((section.gamma, np.full(len(section.gamma),
                    section.plane if positive else section.plane + 180))),
                hovertemplate='C=%{customdata[1]}° · γ=%{customdata[0]}°<br>I=%{r:.4g}<extra>%{fullData.name}</extra>',
            ))
    figure.update_layout(
        title=f'Polar luminous intensity · {result.unit}', height=540,
        polar=dict(radialaxis=dict(rangemode='tozero'),
                   angularaxis=dict(rotation=270, direction='counterclockwise',
                                    tickmode='array', tickvals=list(range(0, 360, 30)),
                                    ticktext=[f'{min(a, 360-a)}°' for a in range(0, 360, 30)])),
        legend=dict(orientation='h'), margin=dict(t=60, b=40, l=55, r=55),
    )
    return figure


def beam_figure(result, rows):
    figure = go.Figure()
    for section, color in zip(result.sections, COLORS):
        label = f'C{section.plane}-C{section.plane + 180}'
        if rows[0][f'{label} width [m]'] is None:
            continue
        distances = [0.0] + [row['Distance [m]'] for row in rows]
        left = [0.0] + [row[f'{label} left [m]'] for row in rows]
        right = [0.0] + [row[f'{label} right [m]'] for row in rows]
        figure.add_trace(go.Scatter(x=distances, y=left, mode='lines', name=label,
                                   legendgroup=label, line=dict(color=color)))
        figure.add_trace(go.Scatter(x=distances, y=right, mode='lines', name=label,
                                   legendgroup=label, showlegend=False, line=dict(color=color)))
        xs, ys = [], []
        for row in rows:
            xs.extend([row['Distance [m]'], row['Distance [m]'], None])
            ys.extend([row[f'{label} left [m]'], row[f'{label} right [m]'], None])
        figure.add_trace(go.Scatter(x=xs, y=ys, mode='lines', name=f'{label} widths',
                                   showlegend=False, line=dict(color=color, dash='dot')))
    figure.update_layout(title='Projected half-intensity boundaries — two plane sections',
                         xaxis_title='Axial distance [m]', yaxis_title='Signed transverse position [m]',
                         yaxis=dict(scaleanchor='x', scaleratio=1), height=420,
                         legend=dict(orientation='h'))
    return figure


def render_diagnostics(st, items):
    st.subheader('Single-luminaire photometric diagnostics')
    if not items:
        st.info('Upload one readable IES/LDT file or select a saved luminaire in the sidebar.')
        return
    selected = st.selectbox('Diagnostic luminaire', [item.filename for item in items], key='diagnostic_file')
    item = next(item for item in items if item.filename == selected)
    labels = {'Absolute intensity [cd]': 'absolute', 'Source units': 'source',
              'Normalized to native maximum': 'normalized'}
    if item.to_cd is None:
        del labels['Absolute intensity [cd]']
    scale_label = st.selectbox('Diagnostic intensity scale', list(labels), key='diagnostic_scale')
    try:
        result = diagnose(item, labels[scale_label])
    except ValueError as error:
        st.warning(str(error))
        return
    st.caption(f'{item.manufacturer} · {item.luminaire} · {item.format} · '
               f'Native gamma range {item.gamma_angles[0]:g}–{item.gamma_angles[-1]:g}°. '
               f'Largest native gamma step: {result.native_gamma_step_max:g}°.')
    for warning in item.warnings:
        st.warning(warning)
    cols = st.columns(3)
    cols[0].metric(f'Native sampled maximum [{result.unit}]', f'{result.peak:.4g}')
    cols[1].metric('One native maximum direction', f'C={result.peak_c:g}° / γ={result.peak_gamma:g}°')
    cols[2].metric('Axial intensity [cd]', 'unavailable' if result.axis_cd is None else f'{result.axis_cd:.4g}')
    st.plotly_chart(polar_figure(result), width='stretch')
    st.caption('γ=0 points down; positive angles on the right are C0/C90, negative angles on the left '
               'are C180/C270. Only the measured gamma range is drawn. '
               'Both cuts use the same scale; no rotation alignment is applied. '
               'The peak is a native sample, not a claim about unmeasured directions.')
    st.subheader('Lower-hemisphere beam width (FWHM)')
    widths = []
    for section in result.sections:
        widths.append({'Section': f'C{section.plane}-C{section.plane + 180}',
                       'Left boundary [°]': section.beam.left_deg,
                       'Right boundary [°]': section.beam.right_deg,
                       'FWHM [°]': section.beam.width_deg,
                       'Status': section.beam.reason or 'Single connected half-maximum region'})
    st.dataframe(pd.DataFrame(widths), hide_index=True, width='stretch')
    st.caption('Half of each section\'s own lower-hemisphere maximum; crossings are linearly interpolated '
               'on native angular knots. A coarse grid limits angular accuracy. '
               'Several separated lobes or missing crossings do not receive a single FWHM.')
    st.subheader('Beam projection and axial illuminance')
    maximum = st.slider('Maximum axial distance [m]', min_value=1.0, max_value=50.0,
                        value=10.0, step=1.0, key='diagnostic_distance')
    rows = distance_rows(result, np.linspace(maximum / 5, maximum, 5))
    if any(row[key] is not None for row in rows[:1] for key in row if 'width' in key):
        st.plotly_chart(beam_figure(result, rows), width='stretch')
    else:
        st.info('No finite beam projection: half-maximum boundaries are unavailable or reach the horizon.')
    if result.axis_reason:
        st.warning(result.axis_reason)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    st.warning('Far-field point-source estimate: E_axis = I_axis / d² on a plane normal to γ=0. '
               'Distance validity depends on luminaire dimensions and optics; the app cannot verify it. '
               'Widths are projections of half-intensity rays, not half-illuminance contours or a circular spot diameter. '
               'Reflections, obstructions and maintenance factors are not included.')
    curve_rows = []
    for section in result.sections:
        for plane, values in ((section.plane, section.positive), (section.plane + 180, section.negative)):
            curve_rows.extend({'File': item.filename, 'C [°]': plane, 'Gamma [°]': float(gamma),
                               'Intensity': float(value), 'Unit': result.unit,
                               'Algorithm': DIAGNOSTICS_VERSION}
                              for gamma, value in zip(section.gamma, values))
    for label, data, filename in (
        ('Download diagnostic curves CSV', curve_rows, 'diagnostic_curves.csv'),
        ('Download FWHM CSV', widths, 'diagnostic_fwhm.csv'),
        ('Download distance diagnostics CSV', rows, 'diagnostic_distances.csv'),
    ):
        frame = pd.DataFrame(data)
        frame['File'] = item.filename
        frame['Algorithm'] = DIAGNOSTICS_VERSION
        st.download_button(label, frame.to_csv(index=False, sep=';').encode('utf-8-sig'),
                           file_name=filename, mime='text/csv')
