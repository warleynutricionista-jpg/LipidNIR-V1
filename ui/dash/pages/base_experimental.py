"""Tela: Base Experimental (seção 19.3). Só layout; a lógica está nos serviços."""

from __future__ import annotations

from dash import dash_table, dcc, html

from lipidence_modular.ui.dash.components.page_frame import page_frame

SLUG = "base-experimental"
TITLE = "Base Experimental"
SUMMARY = "Amostras, espectros, análises laboratoriais e treinamento."

KIND_OPTIONS = [
    {"label": "Espectros", "value": "spectra"},
    {"label": "Análises laboratoriais (cromatográficas e oxidativas)", "value": "reference"},
    {"label": "Arquivo combinado (identidade + espectro + referências)", "value": "combined"},
]
SIGNAL_OPTIONS = [
    {"label": "Absorbância", "value": "absorbance"},
    {"label": "Reflectância", "value": "reflectance"},
    {"label": "Transmitância", "value": "transmittance"},
]
AXIS_OPTIONS = [{"label": "nm", "value": "nm"}, {"label": "cm⁻¹", "value": "cm-1"}]
SCALE_OPTIONS = [{"label": "fração (0 a 1)", "value": "fraction"},
                 {"label": "percentual (0 a 100)", "value": "percent"}]
COMPLETENESS_OPTIONS = [
    {"label": "Completas (espectro + referência)", "value": "complete"},
    {"label": "Incompletas", "value": "incomplete"},
    {"label": "Sem espectro", "value": "no_spectrum"},
    {"label": "Sem referência", "value": "no_reference"},
]
SAMPLE_COLUMNS = [
    ("study_id", "Estudo"), ("sample_id", "Sample ID"), ("genotype", "Genótipo"),
    ("batch", "Batch"), ("lot", "Lote"), ("matrix", "Matriz"), ("n_spectra", "Espectros"),
    ("parameters", "Referências"), ("complete", "Completa"),
]


def field(label: str, control, hint: str | None = None) -> html.Div:
    children = [html.Label(label), control]
    if hint:
        children.append(html.Span(hint, className="hint"))
    return html.Div(children, className="field")


def _import_tab() -> html.Div:
    return html.Div([
        html.H3("1. Arquivo"),
        html.Div([
            field("Estudo (study_id)", dcc.Input(id="import-study", type="text",
                                                 placeholder="ex.: SORGO-2026")),
            field("Tipo de importação", dcc.Dropdown(
                id="import-kind", options=KIND_OPTIONS, value="spectra", clearable=False)),
        ], className="row"),
        dcc.Upload(id="import-upload", className="upload", multiple=False, children=html.Div(
            ["Arraste um arquivo CSV, TSV, TXT ou XLSX, ou ", html.A("selecione")])),
        dcc.Store(id="import-batch-id"),
        html.Div(id="import-staged"),

        html.H3("2. Mapeamento e declarações"),
        html.Div(id="import-mapping-box", children=[
            html.P("Papel de cada coluna. Edite a coluna “papel” para corrigir; “ignore” não "
                   "importa a coluna.", className="hint"),
            dash_table.DataTable(
                id="import-mapping",
                columns=[{"name": "coluna do arquivo", "id": "column", "editable": False},
                         {"name": "papel", "id": "role", "editable": True}],
                data=[], page_size=12,
                style_cell={"textAlign": "left", "fontFamily": "inherit", "padding": "4px 8px"},
                style_header={"fontWeight": "600"},
            ),
        ]),
        html.Div([
            field("Tipo de sinal", dcc.Dropdown(id="import-signal-type",
                                                options=SIGNAL_OPTIONS),
                  "Obrigatório para espectros; nunca é adivinhado."),
            field("Unidade do eixo", dcc.Dropdown(id="import-axis-unit", options=AXIS_OPTIONS),
                  "Obrigatória para espectros."),
            field("Escala do sinal (só para conversão)", dcc.Dropdown(
                id="import-scale", options=SCALE_OPTIONS)),
        ], className="row"),
        html.Div([
            field("Sample ID informado", dcc.Input(id="import-user-sample-id", type="text"),
                  "Para arquivo de uma única amostra."),
            field("Unidades das referências", dcc.Input(
                id="import-reference-units", type="text",
                placeholder="C18:2=%; TBARS=mg MDA/kg"),
                  "Só para colunas sem unidade no cabeçalho."),
            field("Matriz", dcc.Input(id="import-matrix", type="text")),
            field("Instrumento", dcc.Input(id="import-instrument", type="text")),
        ], className="row"),
        dcc.Checklist(id="import-flags", value=[], options=[
            {"label": " Converter reflectância/transmitância para absorbância (log 1/R)",
             "value": "convert"},
            {"label": " Linhas repetidas da mesma amostra são replicatas", "value": "replicates"},
            {"label": " Confirmo o sample_id informado (resolve conflito de identificação)",
             "value": "conflict_confirmed"},
        ], className="checks"),

        html.H3("3. Pré-visualização e confirmação"),
        html.Div([
            html.Button("Pré-visualizar", id="import-preview-btn", n_clicks=0),
            html.Button("Confirmar importação", id="import-confirm-btn", n_clicks=0,
                        className="primary"),
        ], className="buttons"),
        dcc.Loading(html.Div(id="import-result")),
    ])


def _query_tab() -> html.Div:
    return html.Div([
        html.Div([
            field("Estudo", dcc.Dropdown(id="query-study", options=[])),
            field("Genótipo", dcc.Dropdown(id="query-genotype", options=[])),
            field("Lote", dcc.Dropdown(id="query-lot", options=[])),
            field("Completude", dcc.Dropdown(id="query-completeness",
                                             options=COMPLETENESS_OPTIONS)),
        ], className="row"),
        html.Div(html.Button("Consultar", id="query-btn", n_clicks=0), className="buttons"),
        html.Div(id="query-result"),
    ])


def _manual_tab() -> html.Div:
    return html.Div([
        html.H3("Amostra"),
        html.Div([
            field("Estudo (study_id)", dcc.Input(id="manual-study", type="text")),
            field("Sample ID", dcc.Input(id="manual-sample-id", type="text")),
            field("Genótipo", dcc.Input(id="manual-genotype", type="text")),
            field("Lote", dcc.Input(id="manual-lot", type="text")),
            field("Matriz", dcc.Input(id="manual-matrix", type="text")),
        ], className="row"),
        html.Div(html.Button("Cadastrar amostra", id="manual-sample-btn", n_clicks=0),
                 className="buttons"),
        html.Div(id="manual-sample-result"),
        html.H3("Valor de referência"),
        html.P("Usa o estudo e o Sample ID acima.", className="hint"),
        html.Div([
            field("Parâmetro", dcc.Dropdown(id="manual-parameter", options=[])),
            field("Valor", dcc.Input(id="manual-value", type="number")),
            field("Unidade", dcc.Input(id="manual-unit", type="text")),
            field("Replicata", dcc.Input(id="manual-replicate", type="number", min=1, step=1)),
            field("Método", dcc.Input(id="manual-method", type="text")),
        ], className="row"),
        html.Div(html.Button("Registrar valor", id="manual-reference-btn", n_clicks=0),
                 className="buttons"),
        html.Div(id="manual-reference-result"),
    ])


def layout() -> html.Div:
    return page_frame(TITLE, SUMMARY, [
        dcc.Store(id="base-refresh", data=0),
        html.Div(id="base-summary", className="counts"),
        dcc.Tabs(id="base-tabs", value="import", children=[
            dcc.Tab(label="Importar dados", value="import", children=_import_tab()),
            dcc.Tab(label="Consultar base", value="query", children=_query_tab()),
            dcc.Tab(label="Cadastro manual", value="manual", children=_manual_tab()),
        ]),
        html.P("Treinamento de modelos: ainda não implementado (Fase 3).", className="note"),
    ])
