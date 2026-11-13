"""Figuras Plotly montadas com dados já calculados pelos serviços (seção 19.2)."""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

SIGNAL_LABELS = {"absorbance": "Absorbância", "reflectance": "Reflectância",
                 "transmittance": "Transmitância"}


def spectra_figure(spectra: Sequence) -> go.Figure:
    """Espectros do preview. Cada item tem ``sample_id``, ``axis_nm``, ``values``."""
    figure = go.Figure()
    for spectrum in spectra:
        figure.add_trace(go.Scatter(
            x=spectrum.axis_nm, y=spectrum.values, mode="lines", name=spectrum.sample_id,
            line={"width": 1.5},
        ))
    signal = SIGNAL_LABELS.get(spectra[0].signal_type, "Sinal") if spectra else "Sinal"
    figure.update_layout(
        xaxis_title="Comprimento de onda (nm)", yaxis_title=signal, template="plotly_white",
        margin={"l": 60, "r": 20, "t": 20, "b": 50}, height=320,
        legend={"orientation": "h", "y": -0.25},
    )
    return figure
