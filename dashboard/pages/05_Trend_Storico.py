"""Trend Storico — Dal 1861 a oggi: debito, PIL, saldo, interessi."""

import streamlit as st
from sources import query_ocpi

st.title("📜 Trend Storico — Dal 1861")

# ── Serie disponibili ────────────────────────────────────────────
SERIE = {
    "D": ("Debito/PIL %", "% Pil"),
    "G": ("Saldo Primario %PIL", "% Pil"),
    "I": ("Spesa per Interessi %PIL", "% Pil"),
    "N": ("Crescita PIL Reale %", "variazione %"),
    "P": ("Inflazione %", "punti percentuali"),
}

selected_serie = st.multiselect(
    "Serie",
    list(SERIE.keys()),
    default=["D", "G", "I"],
    format_func=lambda x: SERIE[x][0],
)

# ── Filtro temporale ─────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    year_start = st.selectbox("Da", list(range(1861, 2026)), index=140)
with col2:
    year_end = st.selectbox("A", list(range(1861, 2026)), index=164)

# ── Grafico multi-series ─────────────────────────────────────────
if selected_serie:
    st.subheader("Serie Selezionate")

    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]
        for i, s in enumerate(selected_serie):
            df = query_ocpi(f"""
                SELECT anno, valore
                FROM clean_input
                WHERE serie = '{s}'
                    AND anno BETWEEN {year_start} AND {year_end}
                ORDER BY anno
            """)
            if not df.empty:
                fig.add_trace(go.Scatter(
                    x=df["anno"],
                    y=df["valore"],
                    name=SERIE[s][0],
                    line={"color": colors[i % len(colors)], "width": 2},
                ))
        fig.update_layout(
            yaxis_title="Valore",
            xaxis_title="Anno",
            height=500,
            margin={"t": 30},
        )
        st.plotly_chart(fig, width='stretch')
    except ImportError:
        for s in selected_serie:
            df = query_ocpi(f"""
                SELECT anno, valore FROM clean_input
                WHERE serie = '{s}' AND anno BETWEEN {year_start} AND {year_end}
                ORDER BY anno
            """)
            if not df.empty:
                st.subheader(SERIE[s][0])
                st.line_chart(df.set_index("anno")["valore"])

# ── Debito/PIL completo con eventi storici ───────────────────────
st.subheader("Debito/PIL con Eventi Storici")

df_dpil = query_ocpi(f"""
    SELECT anno, valore FROM clean_input
    WHERE serie = 'D' AND anno BETWEEN {year_start} AND {year_end}
    ORDER BY anno
""")

if not df_dpil.empty:
    try:
        import plotly.graph_objects as go

        EVENTI = [
            (1861, "Unità d'Italia"),
            (1915, "Prima Guerra Mondiale"),
            (1929, "Crac del '29"),
            (1940, "Seconda Guerra Mondiale"),
            (1981, "Divorzio Tesoro-Banca Italia"),
            (1992, "Crisi Lira / SME"),
            (2011, "Crisi Debito Euro"),
            (2020, "COVID-19"),
        ]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_dpil["anno"],
            y=df_dpil["valore"],
            name="Debito/PIL",
            line={"color": "#1f77b4", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(31,119,180,0.1)",
        ))
        fig.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="Maastricht")

        for anno, label in EVENTI:
            if year_start <= anno <= year_end:
                fig.add_vline(x=anno, line_dash="dot", line_color="gray", opacity=0.5)
                fig.add_annotation(x=anno, y=df_dpil["valore"].max() * 0.9, text=label, showarrow=False, textangle=-90, font={"size": 9})

        fig.update_layout(yaxis_title="Debito/PIL %", height=500, margin={"t": 30})
        st.plotly_chart(fig, width='stretch')
    except ImportError:
        st.line_chart(df_dpil.set_index("anno")["valore"])

# ── Tabella riepilogativa ────────────────────────────────────────
st.subheader("Valori Recenti")

df_tab = query_ocpi(f"""
    SELECT serie, nome, anno, valore
    FROM clean_input
    WHERE serie IN ('{"','".join(selected_serie if selected_serie else ["D"])}')
        AND anno >= {year_end - 5}
    ORDER BY anno, serie
""")

if not df_tab.empty:
    pivot = df_tab.pivot(index="anno", columns="nome", values="valore")
    st.dataframe(pivot, width='stretch')
