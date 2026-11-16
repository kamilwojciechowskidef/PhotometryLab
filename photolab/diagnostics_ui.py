"""Plotly views of one photometry model; rendering does not write catalogue data."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .diagnostics import DIAGNOSTICS_VERSION, diagnose, distance_rows
from .product_labels import product_label

COLORS = ('#0284c7', '#ea580c')


def _readable_layout(figure):
    """Keep chart text legible in either application theme."""
    figure.update_layout(
        template='plotly_white', paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
        font=dict(color='#172b4d', size=13),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.15,
                    yanchor='top', font=dict(size=13, color='#172b4d')),
        margin=dict(t=65, b=95, l=65, r=45),
    )


def _display_table(rows, numeric_columns):
    """Round presentation only; preserve numbers and nulls, not 'None' strings."""
    frame = pd.DataFrame(rows).copy()
    for column in numeric_columns:
        frame[column] = frame[column].astype('Float64').round(2)
    return frame


def polar_figure(result):
    figure = go.Figure()
    for section, color in zip(result.sections, COLORS):
        label = f'C{section.plane}-C{section.plane + 180}'
        # Separate traces preserve gaps where gamma=0/180 was not measured.
        for positive, values in ((True, section.positive), (False, section.negative)):
            figure.add_trace(go.Scatterpolar(
                theta=section.gamma if positive else -section.gamma, r=values,
                mode='lines', name=label, legendgroup=label, showlegend=positive,
                line=dict(color=color, width=2.5, dash='solid' if section.plane == 0 else 'dash'),
                customdata=np.column_stack((section.gamma, np.full(len(section.gamma),
                    section.plane if positive else section.plane + 180))),
                hovertemplate='C=%{customdata[1]}° · γ=%{customdata[0]}°<br>I=%{r:.4g}<extra>%{fullData.name}</extra>',
            ))
    figure.update_layout(
        title=f'Polar luminous intensity · {result.unit}', height=540,
        polar=dict(bgcolor='#ffffff',
                   radialaxis=dict(rangemode='tozero', angle=90, nticks=6,
                                   tickformat='.3~g', color='#334155',
                                   gridcolor='#cbd5e1', tickfont=dict(size=12, color='#334155')),
                   angularaxis=dict(rotation=270, direction='counterclockwise',
                                    color='#334155', gridcolor='#cbd5e1',
                                    tickfont=dict(size=12, color='#334155'),
                                    tickmode='array', tickvals=list(range(0, 360, 30)),
                                    ticktext=[f'{min(a, 360-a)}°' for a in range(0, 360, 30)])),
        legend=dict(orientation='h'), margin=dict(t=60, b=40, l=55, r=55),
    )
    _readable_layout(figure)
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
                                   legendgroup=label, line=dict(color=color, width=2.5),
                                   hovertemplate='Distance: %{x:.2f} m<br>Position: %{y:.2f} m<extra>%{fullData.name}</extra>'))
        figure.add_trace(go.Scatter(x=distances, y=right, mode='lines', name=label,
                                   legendgroup=label, showlegend=False, line=dict(color=color, width=2.5),
                                   hovertemplate='Distance: %{x:.2f} m<br>Position: %{y:.2f} m<extra>%{fullData.name}</extra>'))
        xs, ys = [], []
        for row in rows:
            xs.extend([row['Distance [m]'], row['Distance [m]'], None])
            ys.extend([row[f'{label} left [m]'], row[f'{label} right [m]'], None])
        figure.add_trace(go.Scatter(x=xs, y=ys, mode='lines', name=f'{label} widths',
                                   showlegend=False, line=dict(color=color, dash='dot')))
    figure.update_layout(title='Half-intensity beam projection',
                         xaxis_title='Axial distance [m]', yaxis_title='Signed transverse position [m]',
                         xaxis=dict(range=[0, max(row['Distance [m]'] for row in rows) * 1.05],
                                    autorange=False, tickformat='.3~g'),
                         yaxis=dict(tickformat='.3~g'), height=460,
                         legend=dict(orientation='h'))
    _readable_layout(figure)
    return figure


def beam_schematic_figure(rows, plane, radial=False):
    """Illustrate measured-section projections and independent on-axis estimates."""
    figure = go.Figure()
    label = f'C{plane}-C{plane + 180}' if plane is not None else None
    available = label is not None and all(row[f'{label} width [m]'] is not None for row in rows)
    distances = [row['Distance [m]'] for row in rows]
    extent = 1.0
    if available:
        left = [row[f'{label} left [m]'] for row in rows]
        right = [row[f'{label} right [m]'] for row in rows]
        extent = max(max(abs(value) for value in left + right), 0.01)
        figure.add_trace(go.Scatter(
            x=[0] + distances + distances[::-1] + [0],
            y=[0] + right + left[::-1] + [0], mode='lines',
            line=dict(color='#0284c7', width=2), fill='toself',
            fillcolor='rgba(125, 190, 220, 0.30)', name=label,
            hoverinfo='skip'))
        centered = radial and all(np.isclose(a, -b, rtol=1e-6, atol=1e-9)
                                  for a, b in zip(left, right))
        for distance, lo, hi, row in zip(distances, left, right, rows):
            if centered:
                radius = distances[0] * 0.13
                figure.add_shape(type='circle', x0=distance-radius, x1=distance+radius,
                                 y0=lo, y1=hi, line=dict(color='#0284c7', width=1),
                                 fillcolor='rgba(255,255,255,0.3)')
            else:
                figure.add_shape(type='line', x0=distance, x1=distance, y0=lo, y1=hi,
                                 line=dict(color='#0284c7', width=2))
            description = 'Diameter' if centered else 'Section width'
            figure.add_annotation(x=distance, y=hi + extent * .12, showarrow=False,
                                  text=f"{description}<br>{row[f'{label} width [m]']:.2f} m",
                                  font=dict(size=11, color='#172b4d'))
    figure.add_trace(go.Scatter(
        x=distances, y=[0] * len(rows), mode='lines+markers', name='Optical axis',
        line=dict(color='#475569', dash='dot'), marker=dict(size=6),
        customdata=[[row['Axial illuminance [lx]']] for row in rows],
        hovertemplate='Distance: %{x:.2f} m<extra>Optical axis</extra>'))
    for row in rows:
        lux = row['Axial illuminance [lx]']
        value = 'unavailable' if lux is None else f'{lux:.2f} lx'
        figure.add_annotation(x=row['Distance [m]'], y=-extent * 1.25,
                              text=f'On axis<br>{value}', showarrow=False,
                              font=dict(size=11, color='#172b4d'))
    _readable_layout(figure)
    figure.update_layout(title='Beam at selected distances', height=440, showlegend=False,
                         xaxis=dict(title='Axial distance [m]', tickvals=distances,
                                    range=[-distances[0] * .25, distances[-1] + distances[0] * .35]),
                         yaxis=dict(title='Transverse position [m]', range=[-extent * 1.55, extent * 1.55]))
    return figure


def render_diagnostics(st, items):
    st.subheader('Single-luminaire photometric diagnostics')
    if not items:
        st.info('Upload one readable IES/LDT file or select a saved luminaire in the sidebar.')
        return
    by_filename = {item.filename: item for item in items}
    selected = st.selectbox('Diagnostic luminaire', list(by_filename), key='diagnostic_file',
                            format_func=lambda name: product_label(by_filename[name]))
    item = next(item for item in items if item.filename == selected)
    st.caption(f"Brand: {item.manufacturer or 'unavailable'} · Catalogue number: {item.catalogue_number or 'unavailable'}")
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
    cols[0].metric('Sampled maximum', f'{result.peak:.4g}')
    cols[1].metric('Peak direction', f'{result.peak_c:g}° / {result.peak_gamma:g}°')
    cols[2].metric('On-axis [cd]', '—' if result.axis_cd is None else f'{result.axis_cd:.4g}')
    st.caption(f'Maximum unit: {result.unit}. Peak direction: C / γ. On-axis intensity always uses cd.')
    st.plotly_chart(polar_figure(result), width='stretch', theme=None)
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
    width_columns = ['Left boundary [°]', 'Right boundary [°]', 'FWHM [°]']
    st.dataframe(_display_table(widths, width_columns).drop(columns='Status'), hide_index=True, width='stretch')
    for section in result.sections:
        if section.beam.reason:
            st.info(f'C{section.plane}–C{section.plane + 180}: {section.beam.reason}')
    st.caption('Half of each section\'s own lower-hemisphere maximum; crossings are linearly interpolated '
               'on native angular knots. A coarse grid limits angular accuracy. '
               'Several separated lobes or missing crossings do not receive a single FWHM.')
    st.subheader('Beam projection and axial illuminance')
    maximum = st.slider('Maximum axial distance [m]', min_value=1.0, max_value=50.0,
                        value=10.0, step=1.0, key='diagnostic_distance')
    rows = distance_rows(result, np.linspace(maximum / 5, maximum, 5))
    available_planes = [section.plane for section in result.sections
                        if rows[0][f'C{section.plane}-C{section.plane + 180} width [m]'] is not None]
    if available_planes or result.axis_cd is not None:
        plane = None
        if available_planes:
            plane = st.selectbox('Section for beam diagram', available_planes,
                                 format_func=lambda p: f'C{p}-C{p + 180}', key='diagnostic_diagram_plane')
        st.plotly_chart(beam_schematic_figure(rows, plane, item.symmetry == 'radial'),
                        width='stretch', theme=None)
        st.caption('The diagram is schematic; axis scales are independent. Widths project the '
                   'half-intensity boundaries in the selected section, not a half-illuminance '
                   'contour. Circular symbols are illustrative and used only for radial symmetry. '
                   'Illuminance is estimated on the axis, not necessarily at the brightest point.')
        if not available_planes:
            st.info('Beam width is unavailable; only the axial illuminance is shown.')
    if any(row[key] is not None for row in rows[:1] for key in row if 'width' in key):
        st.plotly_chart(beam_figure(result, rows), width='stretch', theme=None)
        st.caption('Two plane sections, not a circular footprint. Axis scales are independent; '
                   'read distances from the axes, not the apparent slope of the lines.')
    else:
        st.info('No finite beam projection: half-maximum boundaries are unavailable or reach the horizon.')
    if result.axis_reason:
        st.warning(result.axis_reason)
    display_rows = _display_table(rows, list(rows[0]))
    summary_columns = ['Distance [m]', 'Axial illuminance [lx]',
                       'C0-C180 width [m]', 'C90-C270 width [m]']
    st.dataframe(display_rows[summary_columns], hide_index=True, width='stretch')
    st.caption('Tables show up to two decimal places. Empty cells mean unavailable data, not zero. '
               'CSV exports retain full numerical precision; displayed precision is not measurement accuracy.')
    with st.expander('Boundary positions — detailed table'):
        st.dataframe(display_rows, hide_index=True, width='stretch')
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
