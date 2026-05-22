import plotly.graph_objects as go
import streamlit as st

COLORS = {
    "bg":         "#09090B",
    "surface":    "#18181B",
    "border":     "#27272A",
    "primary":    "#2563EB",
    "success":    "#22C55E",
    "error":      "#EF4444",
    "warning":    "#F59E0B",
    "neutral":    "#71717A",
    "text":       "#FAFAFA",
    "text_muted": "#A1A1AA",
}


def inject_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');

    html, body, .stApp {
        background-color: #09090B !important;
        color: #FAFAFA !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
    }
    .main .block-container { padding-top: 1rem !important; }

    [data-testid="stSidebar"] {
        background-color: #18181B !important;
        border-right: 1px solid #27272A !important;
        font-size: 13px !important;
    }

    h1, h2, h3 {
        font-family: 'IBM Plex Mono', monospace !important;
        font-weight: 700 !important;
        color: #FAFAFA !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1.3rem !important;
        font-weight: 700 !important;
        color: #FAFAFA !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif !important;
        color: #A1A1AA !important;
        font-size: 0.68rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }
    [data-testid="stMetricDelta"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.78rem !important;
    }
    div[data-testid="stMetric"] {
        background: #18181B !important;
        border: 1px solid #27272A !important;
        border-radius: 8px !important;
        padding: 8px 12px !important;
    }

    .coin-card {
        background: #18181B;
        border: 1px solid #27272A;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 10px;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .coin-card:hover {
        border-color: #2563EB;
        box-shadow: 0 0 0 1px #2563EB, 0 4px 20px rgba(37,99,235,0.15);
    }
    .nav-card {
        background: #18181B;
        border: 1px solid #27272A;
        border-radius: 12px;
        padding: 28px 16px 20px;
        text-align: center;
        margin-bottom: 8px;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .nav-card:hover {
        border-color: #2563EB;
        box-shadow: 0 0 20px rgba(37,99,235,0.25);
    }

    .badge-long    { background:rgba(34,197,94,0.12);   color:#22C55E; border:1px solid rgba(34,197,94,0.4);   padding:2px 10px; border-radius:4px; font-family:'Space Mono'; font-size:11px; font-weight:700; letter-spacing:0.04em; }
    .badge-short   { background:rgba(239,68,68,0.12);   color:#EF4444; border:1px solid rgba(239,68,68,0.4);   padding:2px 10px; border-radius:4px; font-family:'Space Mono'; font-size:11px; font-weight:700; }
    .badge-neutro  { background:rgba(113,113,122,0.12); color:#71717A; border:1px solid rgba(113,113,122,0.4); padding:2px 10px; border-radius:4px; font-family:'Space Mono'; font-size:11px; }
    .badge-pullback    { background:rgba(37,99,235,0.12);  color:#2563EB; border:1px solid rgba(37,99,235,0.3);  padding:2px 8px; border-radius:4px; font-family:'Space Mono'; font-size:10px; }
    .badge-rompimento  { background:rgba(245,158,11,0.12); color:#F59E0B; border:1px solid rgba(245,158,11,0.3); padding:2px 8px; border-radius:4px; font-family:'Space Mono'; font-size:10px; }
    .badge-reversao    { background:rgba(168,85,247,0.12); color:#A855F7; border:1px solid rgba(168,85,247,0.3); padding:2px 8px; border-radius:4px; font-family:'Space Mono'; font-size:10px; }
    .badge-cruzamento  { background:rgba(20,184,166,0.12); color:#14B8A6; border:1px solid rgba(20,184,166,0.3); padding:2px 8px; border-radius:4px; font-family:'Space Mono'; font-size:10px; }

    [data-testid="stDataFrame"] {
        border: 1px solid #27272A !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: #18181B !important;
        border: 1px solid #27272A !important;
        border-radius: 6px !important;
        color: #FAFAFA !important;
    }
    .stNumberInput input, .stTextInput input {
        background-color: #18181B !important;
        border: 1px solid #27272A !important;
        color: #FAFAFA !important;
        border-radius: 6px !important;
    }

    .stButton > button {
        background: #2563EB !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 12px !important;
        padding: 0px 14px !important;
        height: 32px !important;
        line-height: 32px !important;
        min-height: 32px !important;
        transition: background 0.15s, box-shadow 0.15s !important;
    }
    .stButton > button:hover {
        background: #1d4ed8 !important;
        box-shadow: 0 0 16px rgba(37,99,235,0.4) !important;
    }
    .stPageLink > a {
        background: transparent !important;
        border: 1px solid #27272A !important;
        color: #A1A1AA !important;
        border-radius: 6px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 13px !important;
        text-align: center !important;
        display: block !important;
        padding: 8px !important;
        text-decoration: none !important;
        transition: border-color 0.15s, color 0.15s !important;
    }
    .stPageLink > a:hover {
        border-color: #2563EB !important;
        color: #2563EB !important;
    }

    .stProgress > div > div { background-color: #2563EB !important; border-radius: 4px !important; }
    .stProgress { background-color: #27272A !important; border-radius: 4px !important; }

    .pos   { color: #22C55E !important; font-family: 'IBM Plex Mono', monospace; }
    .neg   { color: #EF4444 !important; font-family: 'IBM Plex Mono', monospace; }
    .muted { color: #71717A !important; }
    .mono  { font-family: 'IBM Plex Mono', monospace !important; }
    .label { font-size: 0.68rem; color: #A1A1AA; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 2px; }

    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: #09090B; }
    ::-webkit-scrollbar-thumb { background: #27272A; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #3F3F46; }

    #MainMenu                  { visibility: hidden !important; }
    footer                     { visibility: hidden !important; }
    [data-testid="stStatusWidget"],
    [data-testid="stToolbarActions"],
    [data-testid="stMainMenu"],
    [data-testid="stAppDeployButton"] {
        display: none !important;
    }
    [data-testid="stToolbar"] {
        pointer-events: none !important;
        background: transparent !important;
        width: 56px !important;
        height: 48px !important;
        min-height: 48px !important;
        right: auto !important;
        bottom: auto !important;
    }
    [data-testid="stExpandSidebarButton"] {
        pointer-events: auto !important;
    }
    [data-testid="stHeader"] {
        width: 56px !important;
        height: 48px !important;
        min-height: 48px !important;
        background: transparent !important;
    }

    .stat-bar {
        display: flex; gap: 24px; background: #18181B;
        border: 1px solid #27272A; border-radius: 8px;
        padding: 14px 20px; margin-bottom: 20px; flex-wrap: wrap;
    }
    .stat-item  { text-align: center; min-width: 60px; }
    .stat-label { color: #71717A; font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; display: block; margin-bottom: 3px; }
    .stat-value { font-family: 'IBM Plex Mono', monospace; font-size: 1rem; font-weight: 700; color: #FAFAFA; display: block; }
    .stat-value.green { color: #22C55E; }
    .stat-value.red   { color: #EF4444; }
    .stat-value.blue  { color: #2563EB; }
    </style>
    """, unsafe_allow_html=True)


PLOTLY_BASE = dict(
    paper_bgcolor="#09090B",
    plot_bgcolor="#09090B",
    font=dict(color="#FAFAFA", family="DM Sans"),
    margin=dict(l=0, r=0, t=36, b=0),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, orientation="h", yanchor="bottom", y=1.02),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#18181B", bordercolor="#27272A", font_color="#FAFAFA"),
)


def apply_plotly_template(fig: go.Figure, height: int = 480) -> go.Figure:
    fig.update_layout(height=height, **PLOTLY_BASE)
    fig.update_xaxes(gridcolor="#1F1F23", showgrid=True, zeroline=False, rangeslider_visible=False)
    fig.update_yaxes(gridcolor="#1F1F23", showgrid=True, zeroline=False)
    return fig
