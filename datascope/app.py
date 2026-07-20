import streamlit as st
import pandas as pd
import numpy as np
import os

# ----------------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------------
st.set_page_config(page_title="DataScope", layout="wide", page_icon="🔷")

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ----------------------------------------------------------------------------
# Theme: black and blue, with distinct default / hover / press / selected states
# ----------------------------------------------------------------------------
st.markdown("""
    <style>
    :root {
        --ds-bg: #0b0f19;
        --ds-panel: #131a2a;
        --ds-blue: #2f6fed;
        --ds-blue-light: #5b8dff;
        --ds-blue-dark: #1c4bb8;
        --ds-text: #e6ebf5;
        --ds-muted: #8b93a7;
    }

    .stApp {
        background-color: var(--ds-bg);
        color: var(--ds-text);
    }

    section[data-testid="stSidebar"] {
        background-color: var(--ds-panel);
        border-right: 1px solid #1f2940;
    }

    /* Buttons: default / hover / active(press) states */
    .stButton > button, .stDownloadButton > button {
        background-color: var(--ds-panel);
        color: var(--ds-text);
        border: 1px solid var(--ds-blue-dark);
        border-radius: 6px;
        transition: all 0.15s ease-in-out;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: var(--ds-blue);
        border-color: var(--ds-blue-light);
        color: #ffffff;
    }
    .stButton > button:active, .stDownloadButton > button:active {
        background-color: var(--ds-blue-dark);
        border-color: var(--ds-blue-dark);
        color: #ffffff;
    }

    /* Reset button, styled distinctly */
    div[data-testid="stButton"] button[kind="secondary"] {
        border-color: #ef4444;
    }

    /* Checkboxes / radios / multiselect: selected state */
    .stCheckbox label span, .stRadio label span {
        color: var(--ds-text);
    }
    div[data-baseweb="tag"] {
        background-color: var(--ds-blue) !important;
    }

    /* Dataframe container */
    div[data-testid="stDataFrame"] {
        border: 1px solid #1f2940;
        border-radius: 6px;
    }

    h1, h2, h3 {
        color: var(--ds-blue-light);
    }

    hr {
        border-color: #1f2940;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Header row: title + reset button (top right)
# ----------------------------------------------------------------------------
header_col1, header_col2 = st.columns([9, 1])
with header_col1:
    st.title("🔷 DataScope")
    st.caption("Upload a dataset and get a structured exploratory report.")
with header_col2:
    st.write("")
    if st.button("↺ Reset", type="secondary", use_container_width=True):
        st.session_state.uploader_key += 1
        st.rerun()

st.markdown("---")

# ----------------------------------------------------------------------------
# File upload
# ----------------------------------------------------------------------------
st.sidebar.header("📂 Data Input")
file = st.sidebar.file_uploader(
    "Upload a CSV or Excel file",
    type=["csv", "xlsx"],
    key=f"uploader_{st.session_state.uploader_key}",
)

sheets = {}  # sheet_name -> dataframe, only for sheets the user selects

if file:
    filename = file.name
    ext = os.path.splitext(filename)[-1].lower()

    if ext not in [".csv", ".xlsx"]:
        st.sidebar.error("❌ Unsupported file type. Please upload a .csv or .xlsx file.")
    elif ext == ".csv":
        sheets["Sheet1"] = pd.read_csv(file)
    else:
        xls = pd.ExcelFile(file)
        st.sidebar.markdown("---")
        st.sidebar.header("📑 Sheet Selection")
        selected_sheet_names = st.sidebar.multiselect(
            "Choose sheet(s) to include in the report",
            options=xls.sheet_names,
            default=xls.sheet_names[:1],
        )
        for name in selected_sheet_names:
            sheets[name] = pd.read_excel(xls, sheet_name=name)

# ----------------------------------------------------------------------------
# Column classification and profiling
# ----------------------------------------------------------------------------
UNIQUE_DISPLAY_LIMIT = 15


def classify_column(series: pd.Series):
    """Return (column_type, composition_string) for a single column."""
    non_null = series.dropna()

    # Try datetime first, but only trust it if it's not already a plain number
    if pd.api.types.is_datetime64_any_dtype(series):
        is_time = True
    elif pd.api.types.is_numeric_dtype(series):
        is_time = False
    else:
        try:
            converted = pd.to_datetime(non_null, errors="raise")
            is_time = len(converted) > 0
        except (ValueError, TypeError):
            is_time = False

    if is_time:
        try:
            dt_series = pd.to_datetime(non_null)
            oldest = dt_series.min()
            latest = dt_series.max()
            composition = f"Oldest: {oldest.date()} | Latest: {latest.date()}"
        except (ValueError, TypeError):
            composition = "Could not parse dates"
        return "Time-based", composition

    if pd.api.types.is_numeric_dtype(series):
        if non_null.empty:
            return "Numerical", "No non-null values"
        composition = (
            f"Min: {non_null.min():.2f} | Max: {non_null.max():.2f} | "
            f"Avg: {non_null.mean():.2f} | Median: {non_null.median():.2f}"
        )
        return "Numerical", composition

    # Everything else (including location-type columns like country/region) is categorical
    unique_vals = sorted(non_null.astype(str).unique())
    if len(unique_vals) <= UNIQUE_DISPLAY_LIMIT:
        composition = ", ".join(unique_vals) if unique_vals else "No non-null values"
    else:
        shown = ", ".join(unique_vals[:UNIQUE_DISPLAY_LIMIT])
        composition = f"{shown} ... (+{len(unique_vals) - UNIQUE_DISPLAY_LIMIT} more, explore column directly)"
    return "Categorical", composition


def build_profile_df(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i, col in enumerate(df.columns, start=1):
        col_type, composition = classify_column(df[col])
        rows.append({
            "S.No": i,
            "Column": col,
            "Null Values": int(df[col].isnull().sum()),
            "Unique Values": int(df[col].nunique(dropna=True)),
            "Type": col_type,
            "Values Composition": composition,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
if sheets:
    # Sheet summary table
    st.subheader("📑 Sheet Summary")
    summary_rows = [
        {"Sheet Name": name, "Rows": df.shape[0], "Columns": df.shape[1]}
        for name, df in sheets.items()
    ]
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True)
    st.markdown("---")

    # Per-sheet profile
    all_profiles = []
    for name, df in sheets.items():
        st.subheader(f"📋 Column Profile — {name}")
        profile_df = build_profile_df(df)
        st.dataframe(profile_df, use_container_width=True)

        profile_for_download = profile_df.copy()
        st.download_button(
            label=f"⬇️ Download '{name}' report as CSV",
            data=profile_for_download.to_csv(index=False).encode("utf-8"),
            file_name=f"{name}_profile.csv",
            mime="text/csv",
            key=f"download_{name}",
        )

        profile_with_sheet = profile_df.copy()
        profile_with_sheet.insert(0, "Sheet", name)
        all_profiles.append(profile_with_sheet)
        st.markdown("---")

    # Combined download across all selected sheets
    if len(all_profiles) > 0:
        combined_df = pd.concat(all_profiles, ignore_index=True)
        st.download_button(
            label="⬇️ Download combined report (all selected sheets) as CSV",
            data=combined_df.to_csv(index=False).encode("utf-8"),
            file_name="combined_profile_report.csv",
            mime="text/csv",
        )
elif file:
    st.info("👈 Select at least one sheet from the sidebar to generate the report.")
else:
    st.info("👈 Please upload a dataset to get started.")
