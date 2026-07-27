"""
Balochistan High Court - Cause List Analytics Dashboard
------------------------------------------------------------
Run with:  streamlit run app.py
"""

import itertools
import re
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

DATA_PATH = "data/BHC_Cause_List_Combined.xlsx"
GATE_IMAGE = "assets/bhc_gate.jpg"

st.set_page_config(
    page_title="BHC Cause List Analytics",
    page_icon="⚖️",
    layout="wide",
)

# ------------------------------------------------------------------
# COLOR SYSTEM (ported from the Peshawar High Court dashboard)
# ------------------------------------------------------------------
ACCENT = "#4F46E5"        # primary indigo - headline accents
ACCENT_LIGHT = "#818CF8"  # lighter indigo for gradients
BG = "#F6F7FB"             # soft neutral app background
CARD_BG = "#FFFFFF"        # card / chart surface
MUTED_BG = "#F8F9FF"       # very light tint used behind KPI-style chips
BORDER = "#E7E9F5"         # soft border color
TEXT_DARK = "#1E1B4B"      # near-black with a hint of indigo, for headings
TEXT_MUTED = "#6B7280"     # secondary text
GRAY = "#8A8F98"           # neutral - "Not Specified" / "Other"

KPI_ACCENTS = {
    "indigo": "#4F46E5",
    "teal": "#0EA5A4",
    "orange": "#F59E0B",
    "green": "#10B981",
    "red": "#EF4444",
    "purple": "#9333EA",
}

# What each accent means when it shows up on this dashboard (Balochistan's
# own dimensions, not PHC's) - referenced by the color-key expander.
COLOR_LEGEND = [
    ("indigo", "Case Volume (totals & filtered counts)"),
    ("purple", "Judges / Bench panels"),
    ("teal", "Courts, benches & date-based metrics"),
    ("orange", "Advocates"),
    ("green", "Institutions / Sections"),
    ("red", "Case Types / Categories"),
]

# Every categorical chart pulls category colors from this rotating master
# palette (Plotly's Bold + Set3 + Dark24 + Pastel qualitative sets, same
# as PHC) and, where a column repeats across tabs (Category, Section,
# etc.), the same VALUE always gets the same COLOR - "Civil" is the same
# color on Overview as it is on the Explorer tab, even after filtering.
MASTER_PALETTE = (
    px.colors.qualitative.Bold + px.colors.qualitative.Set3
    + px.colors.qualitative.Dark24 + px.colors.qualitative.Pastel
)

# Single-series charts (one line, one histogram, etc.) cycle through this
# fixed solid-color rotation instead of always reusing one brand color.
SOLID_COLORS = [
    "#3EA6D9", "#D9459B", "#FFA630", "#F25C4D", "#7BBF5E", "#F26B6B",
    "#4C7FC9", "#F2895C", "#5FA8D3", "#A64AD1", "#26C99E", "#F2D06B",
    "#6D8FE0", "#C084F5", "#F58BAA",
]
# Heatmaps / density charts cycle through named sequential colorscales
# instead of always reusing one gradient.
SEQUENTIAL_SCALES = [
    px.colors.sequential.Viridis, px.colors.sequential.Plasma, px.colors.sequential.Tealgrn,
    px.colors.sequential.Sunset, px.colors.sequential.Mint, px.colors.sequential.Burg,
    px.colors.sequential.Blues, px.colors.sequential.Purples, px.colors.sequential.Oranges,
]
_solid_cycle = itertools.cycle(SOLID_COLORS)
_seq_cycle = itertools.cycle(SEQUENTIAL_SCALES)

# Named colors used by the color-key legend and a few fixed single-series
# charts (navy/gold/teal correspond to the 1st/2nd/3rd MASTER_PALETTE slots).
COLORS = {
    "navy": "#4C7FC9",
    "gold": "#F2D06B",
    "teal": "#3ECFB2",
    "maroon": "#D9459B",
    "slate": "#5FA8D3",
    "sand": "#F5C77E",
    "gray": "#C4C4C4",
}


def next_solid():
    return next(_solid_cycle)


def next_sequential():
    return next(_seq_cycle)


# Columns whose category -> color mapping should stay fixed across every
# tab. Built once from the full dataset right after it loads (see below).
COLOR_MAP_COLUMNS = ["Category", "Section", "Case Type", "Institution",
                      "Bench Type", "Court Room", "Judges", "Advocate"]
COLOR_MAPS = {}  # populated after load_data(); referenced by column name


def build_color_map(series):
    """'Not Specified' / 'Other' always get neutral gray; every other
    value gets a MASTER_PALETTE color assigned in a fixed (alphabetical)
    order so the same category is always the same color everywhere it
    appears - matching PHC's color_map_for() behavior."""
    clean = series.fillna("Not Specified").astype(str)
    vals = sorted(v for v in clean.unique() if v not in ("Not Specified", "Other"))
    cmap = {v: MASTER_PALETTE[i % len(MASTER_PALETTE)] for i, v in enumerate(vals)}
    cmap["Not Specified"] = GRAY
    cmap["Other"] = GRAY
    return cmap

# ------------------------------------------------------------------
# GLOBAL STYLE
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
        .block-container {padding-top: 4.5rem; padding-bottom: 1.5rem;}
        div[data-testid="stVerticalBlock"] {gap: 0.6rem;}
        div[data-testid="stHorizontalBlock"] {gap: 0.8rem;}
        .element-container {margin-bottom: 0.35rem;}
        div[data-testid="stMetric"] {
            background: #F5F6F8;
            border-left: 3px solid #1B2A4A;
            border-radius: 8px;
            padding: 10px 14px;
        }
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] > div {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            font-size: 1.35rem !important;
            line-height: 1.3;
            word-break: break-word;
            color: #1B2A4A;
        }
        button[data-baseweb="tab"] {padding-top:4px;padding-bottom:4px;}
        div[data-testid="stTabs"] div[data-baseweb="tab-list"] {
            position: relative;
            z-index: 999;
            background: white;
            border-bottom: 2px solid #EDEFF3;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #1B2A4A !important;
            border-bottom: 2px solid #B8863B !important;
        }
        div[data-testid="stTabs"] > div:last-child {padding-top: 0.25rem;}
        header[data-testid="stHeader"] {z-index: 1;}
        .chart-divider {margin: 10px 0 4px 0; border: none; border-top: 1px solid #ececec;}
        .color-key-swatch {
            display: inline-block; width: 12px; height: 12px; border-radius: 3px;
            margin-right: 6px; vertical-align: middle;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# GENERIC HELPERS
# ------------------------------------------------------------------
def style_fig(fig, height=None, legend_bottom=False, left_margin=10, zero_x=False, zero_y=False):
    """Consistent, presentation-quality styling: clear titles/axes/legends,
    automargin so nothing clips, and an optional zero baseline so bars never
    look like they're floating or missing."""
    fig.update_layout(
        font=dict(size=13),
        title=dict(font=dict(size=17), x=0.02, xanchor="left"),
        margin=dict(l=left_margin, r=20, t=55, b=35, pad=6),
        legend=dict(font=dict(size=11)),
        uniformtext_minsize=9,
        uniformtext_mode="hide",
        hoverlabel=dict(font_size=12),
        plot_bgcolor="white",
    )
    if height:
        fig.update_layout(height=height)
    if legend_bottom:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5))
    fig.update_xaxes(automargin=True, title_font=dict(size=12), tickfont=dict(size=10),
                      showgrid=True, gridcolor="#eee")
    fig.update_yaxes(automargin=True, title_font=dict(size=12), tickfont=dict(size=10))
    if zero_x:
        fig.update_xaxes(rangemode="tozero")
    if zero_y:
        fig.update_yaxes(rangemode="tozero")
    return fig


def bar_height(n_categories, per_row=24, base=110, min_h=300, max_h=780):
    """Slightly more compact bar heights - grows with category count so
    labels never overlap, but stays shorter overall than before."""
    return int(min(max_h, max(min_h, base + per_row * n_categories)))


def short_label(s, max_len=24):
    """Shorten long labels (e.g. long institution names) into a clean
    acronym, or trim with an ellipsis - the full text still shows on hover."""
    s = str(s)
    if len(s) <= max_len:
        return s
    words = [w for w in re.findall(r"[A-Za-z0-9]+", s) if len(w) >= 3]
    if len(words) >= 2:
        acronym = "".join(w[0].upper() for w in words)
        if 2 <= len(acronym) <= 8:
            return acronym
    return s[: max_len - 1].rstrip() + "…"


def short_labels(series, max_len=24):
    full = series.astype(str)
    return full, full.apply(lambda s: short_label(s, max_len))


def chart_or_table(fig, table_df, key, color_note=None):
    """Chart / Table toggle - lets a dense chart be read as a table instead.
    color_note (optional): one-line caption explaining what color encodes
    in this specific chart, shown under the chart only."""
    tab_chart, tab_table = st.tabs(["📊 Chart", "📋 Table"])
    with tab_chart:
        st.plotly_chart(fig, use_container_width=True, key=f"{key}_fig")
        if color_note:
            st.caption(color_note)
    with tab_table:
        st.dataframe(table_df, use_container_width=True,
                     height=min(360, 36 * (len(table_df) + 1)))


def top_n_selector(label, max_n, default_n=10, key=""):
    max_n = max(int(max_n), 1)
    default_n = min(default_n, max_n)
    if max_n <= 5:
        return max_n
    return st.slider(f"🔟 {label}", min_value=5, max_value=max_n, value=default_n, key=key)


def divider():
    st.markdown("<hr class='chart-divider'>", unsafe_allow_html=True)


def render_grid(builders):
    """Lay out chart-builder callables two per row, with a light divider
    between rows so charts stay visually separated."""
    for i in range(0, len(builders), 2):
        cols = st.columns(2)
        for col, build in zip(cols, builders[i:i + 2]):
            with col:
                build()
        divider()


def label_with_pct(counts_df, count_col="Cases"):
    """Adds a 'Pct' float column and a 'PctLabel' text column formatted
    as 'count (pct%)' - used to show percentage-of-total alongside raw
    counts on bar/pie/histogram charts."""
    total = counts_df[count_col].sum()
    counts_df["Pct"] = (counts_df[count_col] / total * 100) if total else 0
    counts_df["PctLabel"] = counts_df.apply(
        lambda r: f"{int(r[count_col])} ({r['Pct']:.1f}%)", axis=1)
    return counts_df


def top_pct_only_label(counts_df, count_col="Cases", max_labeled=8):
    """For charts with too many categories to label every bar without
    overlap: full 'count (pct%)' label on the top `max_labeled` bars by
    share, plain count on the rest."""
    counts_df = label_with_pct(counts_df, count_col)
    if len(counts_df) <= max_labeled:
        return counts_df
    ranked = counts_df.sort_values(count_col, ascending=False)
    top_idx = ranked.index[:max_labeled]
    counts_df["PctLabel"] = [
        counts_df.loc[i, "PctLabel"] if i in top_idx else str(int(counts_df.loc[i, count_col]))
        for i in counts_df.index
    ]
    return counts_df


# ------------------------------------------------------------------
# CHART-TYPE BUILDERS (used across every tab for a good mix of chart types)
# ------------------------------------------------------------------
def chart_bar_h(dframe, col, title, emoji, n=10, key=None, selector_label=None):
    if selector_label:
        n = top_n_selector(selector_label, dframe[col].nunique(), n, key=f"{key}_n")
    counts = dframe[col].value_counts().head(n).reset_index()
    counts.columns = [col, "Cases"]
    counts["Full"], counts["Label"] = short_labels(counts[col])
    counts = top_pct_only_label(counts, max_labeled=10)
    cmap = COLOR_MAPS.get(col, {})
    fig = px.bar(counts, x="Cases", y="Label", color=col, color_discrete_map=cmap,
                 orientation="h", title=f"{emoji} {title}", text="PctLabel", custom_data=["Full", "Pct"])
    fig.update_traces(textposition="outside", cliponaxis=False,
                       hovertemplate="%{customdata[0]}: %{x} cases (%{customdata[1]:.1f}%)<extra></extra>")
    fig.update_layout(yaxis={"categoryorder": "total ascending", "title": col},
                       xaxis_title="Number of Cases", showlegend=False)
    style_fig(fig, height=bar_height(len(counts)), left_margin=20, zero_x=True)
    chart_or_table(fig, counts[[col, "Cases", "Pct"]].rename(columns={"Pct": "% of Total"}),
                    key or col.lower().replace(" ", "_"),
                    color_note=f"🎨 Bar color follows **{col}** and stays the same for that "
                               f"value on every other tab. Percent labels show on the top bars only "
                               f"when there are many categories, to avoid overlapping text.")


def chart_bar_v(dframe, col, title, emoji, key=None, max_len=16):
    counts = dframe[col].value_counts().reset_index()
    counts.columns = [col, "Cases"]
    counts["Full"], counts["Label"] = short_labels(counts[col], max_len=max_len)
    counts = top_pct_only_label(counts, max_labeled=8)
    cmap = COLOR_MAPS.get(col, {})
    fig = px.bar(counts, x="Label", y="Cases", color=col, color_discrete_map=cmap,
                 title=f"{emoji} {title}", text="PctLabel", custom_data=["Full", "Pct"])
    fig.update_traces(textposition="outside", cliponaxis=False,
                       hovertemplate="%{customdata[0]}: %{y} cases (%{customdata[1]:.1f}%)<extra></extra>")
    fig.update_layout(xaxis_title=col, yaxis_title="Number of Cases", showlegend=False)
    style_fig(fig, height=min(400, bar_height(len(counts), per_row=0, base=340, min_h=340)), zero_y=True)
    chart_or_table(fig, counts[[col, "Cases", "Pct"]].rename(columns={"Pct": "% of Total"}),
                    key or col.lower().replace(" ", "_") + "_v",
                    color_note=f"🎨 Bar color follows **{col}** and stays the same for that "
                               f"value on every other tab. Percent labels show on the top bars only "
                               f"when there are many categories, to avoid overlapping text.")


def chart_pie(dframe, col, title, emoji, n=8, key=None, selector_label=None):
    if selector_label:
        n = top_n_selector(selector_label, dframe[col].nunique(), n, key=f"{key}_n")
    counts = dframe[col].value_counts().reset_index()
    counts.columns = [col, "Cases"]
    if len(counts) > n:
        top = counts.head(n)
        other = pd.DataFrame({col: ["Other"], "Cases": [counts["Cases"][n:].sum()]})
        counts = pd.concat([top, other], ignore_index=True)
    counts["Full"], counts["Label"] = short_labels(counts[col], max_len=32)
    counts = label_with_pct(counts)
    cmap = {**COLOR_MAPS.get(col, {}), "Other": COLORS["gray"]}
    fig = px.pie(counts, names="Label", values="Cases", title=f"{emoji} {title}", hole=0.4,
                 custom_data=["Full"], color=col, color_discrete_map=cmap)
    # Only print the percent ON the slice for the bigger shares (>=4%) - smaller
    # slices still get the full number/percent on hover, just not crammed text.
    fig.update_traces(
        text=[f"{p:.1f}%" if p >= 4 else "" for p in counts["Pct"]],
        textposition="inside", insidetextorientation="radial",
        hovertemplate="%{customdata[0]}: %{value} cases (%{percent})<extra></extra>",
    )
    fig.update_layout(showlegend=True,
                       legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02,
                                   font=dict(size=10), title=dict(text=col, font=dict(size=12))),
                       margin=dict(l=10, r=260, t=55, b=20))
    style_fig(fig, height=max(340, 26 * len(counts)))
    chart_or_table(fig, counts[[col, "Cases", "Pct"]].rename(columns={"Pct": "% of Total"}),
                    key or col.lower().replace(" ", "_") + "_pie",
                    color_note=f"🎨 Slice color represents **{col}** (gray = grouped \"Other\") "
                               f"- see the legend for the exact mapping. Only slices ≥4% show an "
                               f"on-chart percent label; smaller slices' percentages are on hover, "
                               f"to keep tiny slices from overlapping their labels.")


def chart_treemap(dframe, path_cols, title, emoji, key):
    counts = dframe.groupby(path_cols).size().reset_index(name="Cases")
    top_col = path_cols[0]
    cmap = COLOR_MAPS.get(top_col, {})
    fig = px.treemap(counts, path=path_cols, values="Cases", title=f"{emoji} {title}",
                      color=top_col, color_discrete_map=cmap)
    fig.update_traces(texttemplate="%{label}<br>%{value} (%{percentRoot})",
                       hovertemplate="%{label}: %{value} cases (%{percentRoot})<extra></extra>",
                       textfont=dict(size=11), opacity=0.88)
    style_fig(fig, height=380)
    chart_or_table(fig, counts, key,
                    color_note=f"🎨 Top-level blocks are colored by **{top_col}**, matching that "
                               f"color everywhere else it appears; nested blocks shade the same color. "
                               f"Each block shows its % of the total; text auto-hides on blocks too "
                               f"small to fit it.")


def chart_sunburst(dframe, path_cols, title, emoji, key):
    counts = dframe.groupby(path_cols).size().reset_index(name="Cases")
    top_col = path_cols[0]
    cmap = COLOR_MAPS.get(top_col, {})
    fig = px.sunburst(counts, path=path_cols, values="Cases", title=f"{emoji} {title}",
                       color=top_col, color_discrete_map=cmap)
    fig.update_traces(texttemplate="%{label}<br>%{percentRoot}",
                       hovertemplate="%{label}: %{value} cases (%{percentRoot})<extra></extra>",
                       textfont=dict(size=10), opacity=0.88)
    style_fig(fig, height=380)
    chart_or_table(fig, counts, key,
                    color_note=f"🎨 Inner ring is colored by **{top_col}**, matching that color "
                               f"everywhere else it appears; outer ring shades the same color. Each "
                               f"segment shows its % of the total; text auto-hides on segments too "
                               f"small to fit it.")


def chart_box(dframe, group_col, value_col, title, emoji, n=8, key=None, max_len=16):
    top_groups = dframe[group_col].value_counts().head(n).index
    sub = dframe[dframe[group_col].isin(top_groups)].copy()
    sub["Full"], sub["Label"] = short_labels(sub[group_col], max_len=max_len)
    cmap = COLOR_MAPS.get(group_col, {})
    fig = px.box(sub, x="Label", y=value_col, color=group_col, color_discrete_map=cmap,
                 title=f"{emoji} {title}", custom_data=["Full"])
    fig.update_traces(opacity=0.85)
    fig.update_layout(xaxis_title=group_col, yaxis_title=value_col.replace("_", " "), showlegend=False)
    style_fig(fig, height=380, zero_y=True)
    summary = sub.groupby(group_col)[value_col].describe().reset_index()
    chart_or_table(fig, summary, key or group_col.lower().replace(" ", "_") + "_box",
                    color_note=f"🎨 Box color follows **{group_col}**, matching the bars/pies elsewhere.")


def chart_area(dframe, title, emoji, key):
    trend = dframe.dropna(subset=["ParsedDate"]).groupby("ParsedDate").size().reset_index(name="Cases")
    trend = trend.sort_values("ParsedDate")
    trend["Cumulative Cases"] = trend["Cases"].cumsum()
    total = trend["Cases"].sum()
    trend["Pct"] = (trend["Cumulative Cases"] / total * 100) if total else 0
    fig = px.area(trend, x="ParsedDate", y="Cumulative Cases", title=f"{emoji} {title}",
                  color_discrete_sequence=[COLORS["navy"]], custom_data=["Pct"])
    fig.update_traces(hovertemplate="%{x}: %{y} cases (%{customdata[0]:.1f}% of total)<extra></extra>")
    fig.update_layout(xaxis_title="Date", yaxis_title="Cumulative Cases")
    style_fig(fig, height=360, zero_y=True)
    chart_or_table(fig, trend[["ParsedDate", "Cases", "Cumulative Cases"]], key,
                    color_note="🎨 Single navy tone - this tracks one running total over time, "
                               "not separate categories. Hover a point for its % of the total.")


def chart_line_single(dframe, title, emoji, key):
    trend = dframe.dropna(subset=["ParsedDate"]).groupby("ParsedDate").size().reset_index(name="Cases")
    total = trend["Cases"].sum()
    trend["Pct"] = (trend["Cases"] / total * 100) if total else 0
    fig = px.line(trend, x="ParsedDate", y="Cases", markers=True, title=f"{emoji} {title}", text="Cases",
                  color_discrete_sequence=[COLORS["gold"]], custom_data=["Pct"])
    fig.update_traces(textposition="top center",
                       hovertemplate="%{x}: %{y} cases (%{customdata[0]:.1f}%)<extra></extra>")
    fig.update_layout(xaxis_title="Cause List Date", yaxis_title="Number of Cases")
    style_fig(fig, height=360, zero_y=True)
    chart_or_table(fig, trend, key,
                    color_note="🎨 Single gold tone - this tracks one measure over time, "
                               "not separate categories. Hover a point for its % of the total.")


def chart_line_multi(dframe, group_col, title, emoji, n=5, key=None):
    top_groups = dframe[group_col].value_counts().head(n).index
    sub = dframe[dframe[group_col].isin(top_groups) & dframe["ParsedDate"].notna()].copy()
    sub["Full"], sub["Label"] = short_labels(sub[group_col], max_len=18)
    trend = sub.groupby(["ParsedDate", group_col]).size().reset_index(name="Cases")
    total = trend["Cases"].sum()
    trend["Pct"] = (trend["Cases"] / total * 100) if total else 0
    cmap = COLOR_MAPS.get(group_col, {})
    fig = px.line(trend, x="ParsedDate", y="Cases", color=group_col, color_discrete_map=cmap,
                  markers=True, title=f"{emoji} {title}", custom_data=["Pct"])
    fig.update_traces(hovertemplate="%{x}: %{y} cases (%{customdata[0]:.1f}%)<extra></extra>")
    fig.update_layout(xaxis_title="Date", yaxis_title="Number of Cases", legend_title=group_col)
    style_fig(fig, height=400, legend_bottom=True, zero_y=True)
    chart_or_table(fig, trend, key or group_col.lower().replace(" ", "_") + "_line",
                    color_note=f"🎨 Each line is one **{group_col}**, colored the same as it is "
                               f"on bar/pie charts elsewhere. Hover a point for its % of the total.")


def chart_bubble(dframe, group_col, title, emoji, n=10, key=None, max_len=16):
    g = dframe.groupby(group_col).agg(Cases=("CMA_Count", "size"), Avg_CMA=("CMA_Count", "mean")).reset_index()
    g = g.sort_values("Cases", ascending=False).head(n)
    total = len(dframe)
    g["Pct"] = (g["Cases"] / total * 100) if total else 0
    g["Full"], g["Label"] = short_labels(g[group_col], max_len=max_len)
    cmap = COLOR_MAPS.get(group_col, {})
    fig = px.scatter(g, x="Cases", y="Avg_CMA", size="Cases", color=group_col, color_discrete_map=cmap,
                      title=f"{emoji} {title}", custom_data=["Full", "Pct"])
    fig.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>Cases: %{x} (%{customdata[1]:.1f}%)"
                                     "<br>Avg CMAs: %{y:.1f}<extra></extra>")
    fig.update_layout(xaxis_title="Number of Cases", yaxis_title="Average CMAs per Case", showlegend=False)
    style_fig(fig, height=380, zero_x=True, zero_y=True)
    chart_or_table(fig, g.rename(columns={"Avg_CMA": "Avg CMAs per Case", "Pct": "% of Total"}),
                    key or group_col.lower().replace(" ", "_") + "_bubble",
                    color_note=f"🎨 Bubble color follows **{group_col}** (same mapping as elsewhere); "
                               f"bubble size = number of cases. Hover a bubble to see its name, exact "
                               f"numbers, and % of total - labels aren't shown on the chart itself "
                               f"since they overlap when bubbles sit close together.")


def chart_heatmap(dframe, row_col, col_col, title, emoji, n_row=8, key=None):
    top_rows = dframe[row_col].value_counts().head(n_row).index
    sub = dframe[dframe[row_col].isin(top_rows)]
    cross = pd.crosstab(sub[row_col], sub[col_col])
    cross.index = short_labels(pd.Series(cross.index), max_len=26)[1]
    cross.columns = short_labels(pd.Series(cross.columns), max_len=14)[1]
    fig = px.imshow(cross, text_auto=True, aspect="auto", title=f"{emoji} {title}",
                     labels=dict(color="Cases", x=col_col, y=row_col),
                     color_continuous_scale=["#f4fbff", "#bfe6fb", "#7fd0f7", "#42b6ee", "#1a9ade"])
    grand_total = cross.values.sum()
    fig.update_traces(textfont=dict(color="#0B2942", size=12),
                       hovertemplate=f"%{{y}} × %{{x}}: %{{z}} cases (%{{customdata:.1f}}% of total)<extra></extra>",
                       customdata=(cross.values / grand_total * 100) if grand_total else cross.values)
    fig.update_xaxes(side="bottom", tickangle=-30)
    style_fig(fig, height=bar_height(n_row, per_row=26, base=130), left_margin=20)
    chart_or_table(fig, cross.reset_index(), key or f"{row_col}_{col_col}_heat".lower().replace(" ", "_"),
                    color_note="🎨 Cell shade is an intensity scale (pale → deep blue = fewer → "
                               "more cases), not a category color.")


def chart_histogram(dframe, col, title, emoji, key, nbins=15):
    fig = px.histogram(dframe, x=col, nbins=nbins, title=f"{emoji} {title}",
                        color_discrete_sequence=[COLORS["teal"]])
    total = len(dframe)
    counts, edges = np.histogram(dframe[col].dropna(), bins=nbins)
    pct = (counts / total * 100) if total else counts * 0
    fig.data[0].text = [f"{c} ({p:.1f}%)" for c, p in zip(counts, pct)]
    fig.data[0].textposition = "outside"
    fig.update_layout(xaxis_title=col.replace("_", " "), yaxis_title="Number of Cases", bargap=0.05)
    style_fig(fig, height=360, zero_y=True)
    table = dframe[col].value_counts().sort_index().reset_index()
    table.columns = [col.replace("_", " "), "Number of Cases"]
    table["% of Total"] = (table["Number of Cases"] / total * 100).round(1) if total else 0
    chart_or_table(fig, table, key,
                    color_note="🎨 Single green tone - this shows a distribution of one measure, "
                               "not separate categories. Each bar is labeled with its count and "
                               "% of total.")


# ------------------------------------------------------------------
# DATA LOADING
# ------------------------------------------------------------------
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, sheet_name="Cause List")
    df = df[df["Source File"].notna()].copy()

    df["ParsedDate"] = df["Date"].astype(str).str.extract(r"(\d{1,2}\s+\w{3}\s+\d{4})")[0]
    df["ParsedDate"] = pd.to_datetime(df["ParsedDate"], format="%d %b %Y", errors="coerce")

    def cma_count(x):
        if not isinstance(x, str) or not x.strip():
            return 0
        items = [i for part in x.split("|") for i in part.split(",") if i.strip()]
        return len(items)
    df["CMA_Count"] = df["CMAs"].apply(cma_count)

    for col in ["Category", "Judges", "Case Type", "Advocate", "Section",
                "Institution", "Bench Type", "Court Room"]:
        df[col] = df[col].fillna("Not Specified").astype(str).str.strip()

    return df


try:
    df = load_data(DATA_PATH)
except FileNotFoundError:
    st.error(f"⚠️ Couldn't find the data file at `{DATA_PATH}`. Check that it's been uploaded "
             f"to the app's `data/` folder and try again.")
    st.stop()

COLOR_MAPS = {c: build_color_map(df[c]) for c in COLOR_MAP_COLUMNS if c in df.columns}


def render_color_key():
    swatch_cols = st.columns(6)
    swatch_meaning = [
        ("navy", "Primary category color (assigned first, alphabetically, per field)"),
        ("gold", "Second category color, also the accent used for trend lines & data-density shading"),
        ("teal", "Third category color, also used for single-measure histograms"),
        ("maroon", "Fourth category color"),
        ("slate", "Fifth category color"),
        ("sand", "Sixth category color, then the sequence repeats"),
    ]
    for c, (key, meaning) in zip(swatch_cols, swatch_meaning):
        with c:
            st.markdown(
                f"<span class='color-key-swatch' style='background:{COLORS[key]}'></span>"
                f"<span style='font-size:12px'>{meaning}</span>",
                unsafe_allow_html=True,
            )
    st.caption(
        "Every bar, slice, or line is colored by its own category (e.g. a Judge panel, a Section, "
        "an Institution) and that color is fixed everywhere the same value appears — across tabs and "
        "after filtering. **Gray** always means \"Not Specified\" or a grouped \"Other\". Charts that "
        "track a single measure over time or density (trend lines, the cumulative-cases chart, "
        "heatmaps, histograms) intentionally use **one** color, since there's nothing categorical "
        "to distinguish. Each chart has its own 🎨 caption underneath spelling this out."
    )


# ------------------------------------------------------------------
# GLOBAL FILTERS (sidebar - persist across every tab; Explorer's own
# filters stack on top of these)
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔎 Global Filters")
    st.caption("Applied across every tab below.")

    if df["ParsedDate"].notna().any():
        min_d, max_d = df["ParsedDate"].min().date(), df["ParsedDate"].max().date()
        date_range = st.date_input("📅 Date Range", value=(min_d, max_d),
                                    min_value=min_d, max_value=max_d)
    else:
        date_range = None

    inst_f = st.multiselect("🏛️ Institution", sorted(df["Institution"].unique()))
    judge_f = st.multiselect("👨‍⚖️ Judges", sorted(df["Judges"].unique()))

    gdf = df.copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
        gdf = gdf[gdf["ParsedDate"].isna()
                  | ((gdf["ParsedDate"].dt.date >= start_d) & (gdf["ParsedDate"].dt.date <= end_d))]
    if inst_f:
        gdf = gdf[gdf["Institution"].isin(inst_f)]
    if judge_f:
        gdf = gdf[gdf["Judges"].isin(judge_f)]

    st.caption(f"📋 {len(gdf):,} of {len(df):,} cases match")
    st.download_button(
        "⬇️ Export current view (CSV)",
        gdf.to_csv(index=False).encode("utf-8"),
        "bhc_global_filtered.csv",
        "text/csv",
    )

# ------------------------------------------------------------------
# TOP NAV
# ------------------------------------------------------------------
tab_home, tab_overview, tab_judges, tab_types, tab_pendency, tab_explorer = st.tabs(
    ["🏠 Home", "📊 Overview", "👨‍⚖️ Judges & Workload", "📁 Case Types & Trends",
     "⏳ Pendency & Aging", "🔍 Case Explorer"]
)

latest_date = df["ParsedDate"].max()
latest_date_str = latest_date.strftime("%d %B, %Y") if pd.notna(latest_date) else "N/A"

# ------------------------------------------------------------------
# HOME
# ------------------------------------------------------------------
with tab_home:
    title_col, badge_col = st.columns([3, 1])
    with title_col:
        st.markdown("<h1 style='margin-bottom:0'>⚖️ Balochistan High Court</h1>", unsafe_allow_html=True)
    with badge_col:
        st.markdown(
            f"<div style='text-align:right;padding-top:20px'>"
            f"<span style='background:#1B2A4A;color:white;padding:8px 16px;border-radius:20px;"
            f"font-size:14px'>🕐 Data last updated: <b>{latest_date_str}</b></span></div>",
            unsafe_allow_html=True,
        )

    st.write("")
    left, right = st.columns([2, 1])
    with left:
        st.markdown("### 🎯 The primary objective of this dashboard is to:")
        st.markdown(
            """
1. Provide clear visibility into **hearing schedules, bench compositions, and courtroom
   activity** across the Balochistan High Court (Principal Seat Quetta, its benches, and
   its tribunals).
2. Analyze case distribution across **sections, case types, and institutions**, helping surface
   litigation trends and judicial workload patterns.
3. Track **judge and courtroom workload** to understand how cases are distributed across the
   bench.
4. Facilitate evidence-based analysis of judicial processes through modern data visualization.
            """
        )
        st.info(
            "**Disclaimer:** The data presented in this dashboard is sourced from publicly "
            "available cause lists published by the Balochistan High Court. The information "
            "has been compiled and parsed for improved understanding and accessibility."
        )
    with right:
        try:
            st.image(GATE_IMAGE, caption="Balochistan High Court, Quetta", use_container_width=True)
        except Exception:
            st.info("🏛️ (Gate image not found - add it at `assets/bhc_gate.jpg`.)")

    st.markdown("---")
    st.markdown("### 📌 Snapshot")
    k1, k2, k3 = st.columns(3)
    k1.metric("📁 Total Cases", f"{len(gdf):,}")
    k2.metric("👨‍⚖️ Judge Panels", gdf["Judges"].nunique())
    k3.metric("📎 Avg CMAs / Case", f"{gdf['CMA_Count'].mean():.1f}" if len(gdf) else "N/A")

    if gdf["ParsedDate"].notna().any():
        start, end = gdf["ParsedDate"].min(), gdf["ParsedDate"].max()
        span = f"{start:%d %b} – {end:%d %b %Y}" if start.year == end.year else f"{start:%d %b %Y} – {end:%d %b %Y}"
    else:
        span = "N/A"

    k4, k5 = st.columns(2)
    k4.metric("📅 Date Range", span)

    monthly = gdf.dropna(subset=["ParsedDate"]).copy()
    if not monthly.empty:
        monthly["Month"] = monthly["ParsedDate"].dt.to_period("M")
        months_present = sorted(monthly["Month"].unique())
        if len(months_present) >= 2:
            cur_month, prev_month = months_present[-1], months_present[-2]
            cur_data = monthly[monthly["Month"] == cur_month]
            prev_data = monthly[monthly["Month"] == prev_month]

            # The current month is very likely still in progress (data only
            # goes up to "today"), so comparing it whole against a FULL
            # previous month wildly inflates the delta. Instead, compare the
            # same day-of-month window in both months - e.g. "1-23 Jul" vs
            # "1-23 Jun" - so it's an apples-to-apples comparison.
            days_elapsed = cur_data["ParsedDate"].dt.day.max()
            cur_count = int((cur_data["ParsedDate"].dt.day <= days_elapsed).sum())
            prev_count = int((prev_data["ParsedDate"].dt.day <= days_elapsed).sum())

            is_partial = days_elapsed < cur_month.days_in_month
            delta = cur_count - prev_count
            pct = (delta / prev_count * 100) if prev_count else 0
            label_suffix = f" (first {days_elapsed}d)" if is_partial else ""
            k5.metric(f"📈 {cur_month.strftime('%b %Y')} vs {prev_month.strftime('%b %Y')}{label_suffix}",
                      f"{cur_count:,}", f"{delta:+,} ({pct:+.0f}%)")
            if is_partial:
                k5.caption(f"⚠️ {cur_month.strftime('%b')} is still in progress - comparing the "
                           f"first {days_elapsed} days of both months, not full-month totals.")
        else:
            k5.metric("📈 Month-over-Month", f"{len(monthly):,}", "Only 1 month in range")
    else:
        k5.metric("📈 Month-over-Month", "N/A")

# ------------------------------------------------------------------
# OVERVIEW  (10 charts)
# ------------------------------------------------------------------
with tab_overview:
    st.subheader("📊 Overview")

    with st.expander("🎨 How to read the colors in these charts", expanded=False):
        render_color_key()

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
    c1.metric("📁 Total Cases", f"{len(gdf):,}")
    c2.metric("🗂️ Source Files", gdf["Source File"].nunique())
    c3.metric("🏛️ Institutions / Tribunals", gdf["Institution"].nunique())
    date_span = ""
    if gdf["ParsedDate"].notna().any():
        start, end = gdf["ParsedDate"].min(), gdf["ParsedDate"].max()
        if start.year == end.year:
            date_span = f"{start:%d %b} – {end:%d %b %Y}"
        else:
            date_span = f"{start:%d %b %Y} – {end:%d %b %Y}"
    c4.metric("📅 Date Range Covered", date_span or "N/A")
    st.write("")

    render_grid([
        lambda: chart_bar_h(gdf, "Category", "Cases by Category", "📁", key="ov_category",
                             selector_label="Categories to show"),
        lambda: chart_pie(gdf, "Section", "Cases by Section", "🧩", key="ov_section",
                           selector_label="Sections to show"),
        lambda: chart_bar_v(gdf, "Bench Type", "Cases by Bench Type", "⚖️", key="ov_bench"),
        lambda: chart_bar_h(gdf, "Institution", "Cases by Institution", "🏛️", key="ov_institution",
                             selector_label="Institutions to show"),
        lambda: chart_treemap(gdf, ["Category", "Section"], "Category → Section Breakdown", "🌳", "ov_treemap"),
        lambda: chart_sunburst(gdf, ["Institution", "Bench Type"], "Institution → Bench Type", "☀️", "ov_sunburst"),
        lambda: chart_box(gdf, "Category", "CMA_Count", "CMA Load by Category", "📦", key="ov_box"),
        lambda: chart_area(gdf, "Cumulative Cases Over Time", "📈", "ov_area"),
        lambda: chart_bubble(gdf, "Institution", "Institution Caseload vs CMA Load", "🔵", key="ov_bubble", max_len=14),
        lambda: chart_heatmap(gdf, "Bench Type", "Section", "Bench Type × Section Workload", "🔥", n_row=8,
                               key="ov_heatmap"),
    ])

# ------------------------------------------------------------------
# JUDGES & WORKLOAD  (10 charts)
# ------------------------------------------------------------------
with tab_judges:
    st.subheader("👨‍⚖️ Judges & Workload")

    render_grid([
        lambda: chart_bar_h(gdf, "Judges", "Top Judge Panels by Case Volume", "👨‍⚖️", key="jw_judges",
                             selector_label="Judge panels to show"),
        lambda: chart_bar_v(gdf, "Court Room", "Court Room Utilization", "🏢", key="jw_room", max_len=14),
        lambda: chart_heatmap(gdf, "Judges", "Section", "Judge × Section Workload", "🔥", n_row=8, key="jw_heat1"),
        lambda: chart_pie(gdf, "Judges", "Judge Panel Case Share", "🥧", key="jw_pie"),
        lambda: chart_treemap(gdf, ["Court Room", "Bench Type"], "Court Room → Bench Type", "🌳", "jw_treemap"),
        lambda: chart_sunburst(gdf, ["Judges", "Section"], "Judges → Section Breakdown", "☀️", "jw_sunburst"),
        lambda: chart_box(gdf, "Judges", "CMA_Count", "CMA Load by Judge Panel", "📦", n=8, key="jw_box", max_len=14),
        lambda: chart_line_multi(gdf, "Judges", "Caseload Over Time (Top 5 Judge Panels)", "📈", n=5, key="jw_line"),
        lambda: chart_bubble(gdf, "Judges", "Judge Caseload vs CMA Load", "🔵", n=10, key="jw_bubble", max_len=14),
        lambda: chart_heatmap(gdf, "Court Room", "Bench Type", "Court Room × Bench Type", "🧮", n_row=8,
                               key="jw_heat2"),
    ])

# ------------------------------------------------------------------
# CASE TYPES & TRENDS  (10 charts)
# ------------------------------------------------------------------
with tab_types:
    st.subheader("📁 Case Types & Trends")

    render_grid([
        lambda: chart_bar_h(gdf, "Case Type", "Top Case Types", "📁", key="ct_types",
                             selector_label="Case types to show"),
        lambda: chart_line_single(gdf, "Cases per Cause List Date", "📈", "ct_trend"),
        lambda: chart_histogram(gdf, "CMA_Count", "Distribution of CMAs per Case", "📊", "ct_hist"),
        lambda: chart_bar_h(gdf, "Advocate", "Top Advocates", "🧑‍💼", key="ct_advocates",
                             selector_label="Advocates to show"),
        lambda: chart_pie(gdf, "Case Type", "Case Type Share", "🥧", key="ct_pie"),
        lambda: chart_treemap(gdf, ["Category", "Case Type"], "Category → Case Type", "🌳", "ct_treemap"),
        lambda: chart_box(gdf, "Case Type", "CMA_Count", "CMA Load by Case Type", "📦", n=8, key="ct_box", max_len=16),
        lambda: chart_heatmap(gdf, "Case Type", "Section", "Case Type × Section", "🔥", n_row=8, key="ct_heat"),
        lambda: chart_area(gdf, "Cumulative Case Trend", "📈", "ct_area"),
        lambda: chart_bubble(gdf, "Advocate", "Advocate Caseload vs CMA Load", "🔵", n=10, key="ct_bubble", max_len=14),
    ])

with tab_pendency:
    st.subheader("⏳ Pendency & Aging")
    st.caption(
        "This cause-list data has no filing/disposal date, so true case age can't be "
        "computed directly. The closest available proxy: how many times a case is "
        "re-listed, and the gap between those listings - frequent re-listing with wide "
        "gaps is a signal of a slow-moving or repeatedly adjourned case."
    )

    case_col = "Case No"
    valid = gdf[gdf[case_col].notna() & (gdf[case_col].astype(str).str.strip() != "")].copy()
    stats = valid.groupby(case_col).agg(
        Appearances=(case_col, "size"),
        First_Seen=("ParsedDate", "min"),
        Last_Seen=("ParsedDate", "max"),
        Judges=("Judges", "first"),
        Section=("Section", "first"),
        Category=("Category", "first"),
    ).reset_index()
    stats["Span_Days"] = (stats["Last_Seen"] - stats["First_Seen"]).dt.days
    repeat_rate = (stats["Appearances"] > 1).mean() * 100 if len(stats) else 0
    gap_basis = stats[stats["Appearances"] > 1].copy()
    gap_basis["Avg_Gap"] = gap_basis["Span_Days"] / (gap_basis["Appearances"] - 1)
    avg_gap = gap_basis["Avg_Gap"].mean()

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("🗂️ Unique Cases", f"{len(stats):,}")
    p2.metric("🔁 Repeat Rate", f"{repeat_rate:.0f}%",
              help="Share of cases appearing on more than one cause list date")
    p3.metric("📊 Avg Appearances / Case", f"{stats['Appearances'].mean():.1f}" if len(stats) else "N/A")
    p4.metric("⏱️ Avg Gap Between Hearings", f"{avg_gap:.0f} days" if pd.notna(avg_gap) else "N/A")
    st.write("")

    def chart_appearance_dist():
        dist = stats["Appearances"].value_counts().sort_index().reset_index()
        dist.columns = ["Appearances", "Cases"]
        dist["Appearances"] = dist["Appearances"].astype(str)
        fig = px.bar(dist, x="Appearances", y="Cases", title="🔁 How Many Times Does a Case Reappear?",
                     text="Cases", color_discrete_sequence=[COLORS["navy"]])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(xaxis_title="Number of Appearances on Cause Lists", yaxis_title="Number of Cases",
                           showlegend=False)
        style_fig(fig, height=380, zero_y=True)
        chart_or_table(fig, dist, "pend_dist",
                        color_note="🎨 Single navy tone - tracks one measure, not categories.")

    def chart_gap_by_judge():
        top = gap_basis["Judges"].value_counts().head(8).index
        sub = gap_basis[gap_basis["Judges"].isin(top)].copy()
        if sub.empty:
            st.info("Not enough repeat cases to break this down by judge panel yet.")
            return
        sub["Full"], sub["Label"] = short_labels(sub["Judges"], max_len=16)
        cmap = COLOR_MAPS.get("Judges", {})
        fig = px.box(sub, x="Label", y="Avg_Gap", color="Judges", color_discrete_map=cmap,
                     title="⏱️ Hearing-Gap Spread by Judge Panel", custom_data=["Full"])
        fig.update_layout(xaxis_title="Judges", yaxis_title="Avg Days Between Hearings", showlegend=False)
        style_fig(fig, height=380, zero_y=True)
        chart_or_table(fig, sub.groupby("Judges")["Avg_Gap"].describe().reset_index(), "pend_gap_judge",
                        color_note="🎨 Box color follows **Judges**, matching bars/pies elsewhere.")

    def chart_gap_by_section():
        top = gap_basis["Section"].value_counts().head(8).index
        sub = gap_basis[gap_basis["Section"].isin(top)].copy()
        if sub.empty:
            st.info("Not enough repeat cases to break this down by section yet.")
            return
        sub["Full"], sub["Label"] = short_labels(sub["Section"], max_len=16)
        cmap = COLOR_MAPS.get("Section", {})
        fig = px.box(sub, x="Label", y="Avg_Gap", color="Section", color_discrete_map=cmap,
                     title="⏱️ Hearing-Gap Spread by Section", custom_data=["Full"])
        fig.update_layout(xaxis_title="Section", yaxis_title="Avg Days Between Hearings", showlegend=False)
        style_fig(fig, height=380, zero_y=True)
        chart_or_table(fig, sub.groupby("Section")["Avg_Gap"].describe().reset_index(), "pend_gap_section",
                        color_note="🎨 Box color follows **Section**, matching bars/pies elsewhere.")

    def chart_most_repeated():
        top_repeat = stats.sort_values("Appearances", ascending=False).head(10).copy()
        top_repeat["Full"], top_repeat["Label"] = short_labels(top_repeat[case_col], max_len=18)
        fig = px.bar(top_repeat, x="Appearances", y="Label", orientation="h",
                     title="🔥 Most Frequently Re-listed Cases", text="Appearances",
                     custom_data=["Full"], color_discrete_sequence=[COLORS["maroon"]])
        fig.update_traces(textposition="outside", cliponaxis=False,
                           hovertemplate="%{customdata[0]}: %{x} appearances<extra></extra>")
        fig.update_layout(yaxis={"categoryorder": "total ascending", "title": "Case No"},
                           xaxis_title="Appearances", showlegend=False)
        style_fig(fig, height=bar_height(len(top_repeat)), left_margin=20, zero_x=True)
        chart_or_table(fig, top_repeat[[case_col, "Appearances", "Category", "Section", "Judges"]],
                        "pend_top_repeat",
                        color_note="🎨 Single maroon tone - ranks individual cases, not categories.")

    render_grid([chart_appearance_dist, chart_gap_by_judge, chart_gap_by_section, chart_most_repeated])

# ------------------------------------------------------------------
# CASE EXPLORER  (filters + 10 charts driven by the filtered data + table)
# ------------------------------------------------------------------
with tab_explorer:
    st.subheader("🔍 Case Explorer")

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        cat_f = st.multiselect("🏷️ Category", sorted(gdf["Category"].unique()))
    with f2:
        sec_f = st.multiselect("📂 Section", sorted(gdf["Section"].unique()))
    with f3:
        type_f = st.multiselect("📁 Case Type", sorted(gdf["Case Type"].unique()))
    with f4:
        search = st.text_input("🔎 Search (Case No / Petitioner / Respondent / Advocate)")

    filtered = gdf.copy()  # starts from the global sidebar filters, then narrows further
    if cat_f:
        filtered = filtered[filtered["Category"].isin(cat_f)]
    if sec_f:
        filtered = filtered[filtered["Section"].isin(sec_f)]
    if type_f:
        filtered = filtered[filtered["Case Type"].isin(type_f)]
    if search:
        s = search.lower()
        mask = (
            filtered["Case No"].astype(str).str.lower().str.contains(s, na=False)
            | filtered["Petitioner"].astype(str).str.lower().str.contains(s, na=False)
            | filtered["Respondent"].astype(str).str.lower().str.contains(s, na=False)
            | filtered["Advocate"].astype(str).str.lower().str.contains(s, na=False)
        )
        filtered = filtered[mask]

    st.caption(f"📋 Showing {len(filtered):,} of {len(gdf):,} globally-filtered cases "
               f"({len(df):,} total in the full dataset)")

    if filtered.empty:
        st.warning("⚠️ No cases match the current filters - adjust them to see charts and results.")
    else:
        render_grid([
            lambda: chart_bar_h(filtered, "Category", "Filtered: Cases by Category", "📁", n=10, key="ex_category"),
            lambda: chart_pie(filtered, "Section", "Filtered: Cases by Section", "🧩", n=8, key="ex_section"),
            lambda: chart_bar_h(filtered, "Case Type", "Filtered: Top Case Types", "📁", n=10, key="ex_type"),
            lambda: chart_bar_h(filtered, "Institution", "Filtered: Cases by Institution", "🏛️", n=10, key="ex_inst"),
            lambda: chart_bar_h(filtered, "Judges", "Filtered: Top Judge Panels", "👨‍⚖️", n=10, key="ex_judges"),
            lambda: chart_bar_h(filtered, "Advocate", "Filtered: Top Advocates", "🧑‍💼", n=10, key="ex_advocates"),
            lambda: chart_line_single(filtered, "Filtered: Cases per Cause List Date", "📈", "ex_trend"),
            lambda: chart_histogram(filtered, "CMA_Count", "Filtered: CMA Distribution", "📊", "ex_hist"),
            lambda: chart_bar_v(filtered, "Court Room", "Filtered: Court Room Utilization", "🏢", key="ex_room"),
            lambda: chart_treemap(filtered, ["Category", "Case Type"], "Filtered: Category → Case Type", "🌳",
                                   "ex_treemap"),
        ])

    show_cols = ["Category", "Source File", "Date", "Court Room", "Judges", "Section",
                 "Case No", "Case Type", "Petitioner", "Respondent", "Advocate", "CMAs"]
    show_cols = [c for c in show_cols if c in filtered.columns]
    st.markdown("#### 🗒️ Filtered Case List")
    st.dataframe(filtered[show_cols], use_container_width=True, height=500)

    st.download_button(
        "⬇️ Download filtered results (CSV)",
        filtered[show_cols].to_csv(index=False).encode("utf-8"),
        "bhc_filtered_cases.csv",
        "text/csv",
    )