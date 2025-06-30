 # py code beginning

import streamlit as st
from datetime import date
from typing import Dict

import pandas as pd
import plotly.express as px
from fredapi import Fred

# --- Page Config ---
st.set_page_config(page_title="Retail Market Dashboard(USA)", layout="wide")
sidebar = st.sidebar
sidebar.title("🔧 Configuration")

# Initialize session_state dates if not exists
if 'start_date' not in st.session_state:
    st.session_state['start_date'] = date(2015, 1, 1)
if 'end_date' not in st.session_state:
    st.session_state['end_date'] = date.today()

# --- Date Inputs (bind to session_state) ---------------------------
start_date = sidebar.date_input(
    "Start date", value=date(2015, 1, 1), key="start_date"
)
end_date = sidebar.date_input(
    "End date", value=date.today(), key="end_date"
)

# --- Other sidebar controls ----------------------------------------
fred_api_key = sidebar.text_input("FRED API key", type="password")
resample_monthly = sidebar.checkbox("Resample ECOMSA to Monthly", value=True)

SERIES_CODES: Dict[str, str] = {
    "Total Retail Sales (RSAFS, Monthly)": "RSAFS",
    "E-commerce Sales (ECOMSA, Quarterly)": "ECOMSA",
    "Retail Employment (CEU4200000001, Monthly)": "CEU4200000001",
    "Clothing & Accessories Sales": "MRTSSM448USS",
    "Consumer Sentiment (UM)": "UMCSENT",
    "PCE - Personal Consumption": "PCE",
    "Personal Savings Rate": "PSAVERT"
}


selected_series = sidebar.multiselect(
    "Select series to display",
    list(SERIES_CODES.keys()),
    default=list(SERIES_CODES.keys())
)

# --- Helper to load series from FRED -------------------------------
@st.cache_data(show_spinner=False)
def load_series(api_key: str, code: str, start: date, end: date) -> pd.Series:
    fred = Fred(api_key=api_key)
    s = fred.get_series(code, observation_start=start, observation_end=end)
    s.name = code
    return s

# --------------------------- Main ----------------------------------

if fred_api_key:
    series_list = []
    series_labels = []

    for label in selected_series:
        code = SERIES_CODES[label]
        try:
            s = load_series(
                fred_api_key, code,
                st.session_state["start_date"], st.session_state["end_date"]
            )
            if resample_monthly and code == "ECOMSA":
                s = s.resample("M").ffill()
                s.name = "E-commerce Sales (ECOMSA, Monthly)"
            else:
                s.name = label

            series_list.append(s)
        except Exception as e:
            st.error(f"❌ Failed to download {label} ({code}): {e}")
 # Debug info –‑ real date span
 #   st.write("✅ Loaded series count:", len(series_list))


 # --- Build dataframe & visuals ---------------------------------


    if series_list:
        data = pd.concat(series_list, axis=1).sort_index()

    # 補齊完整日期索引
        full_idx = pd.date_range(
        start=st.session_state['start_date'],
        end=st.session_state['end_date'],
        freq='D'
    )
        data = data.reindex(full_idx)
        plot_columns = list(data.columns)
 # Debug info –‑ real date span
 #       st.write(
 #           f"📅 **Data index range:** {data.index.min().date()} → {data.index.max().date()}"
 #       )

 # Optional: specific ECOMSA chart

        if "E-commerce Sales (ECOMSA, Quarterly)" in data.columns:
            st.subheader("🛒 E-commerce Sales (ECOMSA)")
            y_data = data["E-commerce Sales (ECOMSA, Quarterly)"].dropna()
            try:
                if y_data.empty:
                    st.warning("No ECOMSA data available to plot.")
                else:
                    fig_ec = px.line(
                        y_data,
                        x=y_data.index,
                        y=y_data.values,
                        labels={"y": "E-commerce Sales"},
                        title="E-commerce Sales Over Time"
                    )
                    st.plotly_chart(fig_ec, use_container_width=True)
            except Exception as e:
                st.error(f"Error plotting ECOMSA: {e}")



 # ---------------- Dashboard Header --------------------------
        st.title("📊 Retail Market Dashboard(USA)")
        st.write(f"FRED data from {st.session_state['start_date']} to {st.session_state['end_date']}")
        data_filled = data.ffill()

 # ---------------- KPI Cards ---------------------------------


        # 依日期範圍過濾
        filtered = data_filled.loc[
          (data_filled.index >= pd.to_datetime(st.session_state["start_date"])) &
          (data_filled.index <= pd.to_datetime(st.session_state["end_date"]))
        ]

        # ➡️ 若整段區間沒有任何數值，就略過
        valid = filtered.dropna(how="all")
        if not valid.empty:
          latest = valid.iloc[-1]
          first = valid.iloc[0]

          kpi_cols = st.columns(len(latest))
          for idx, (label, val) in enumerate(latest.items()):
            first_val = first.get(label, None)

            if pd.notna(val) and pd.notna(first_val) and isinstance(first_val, (int, float)) and first_val != 0:
              delta_pct = ((val - first_val) / first_val) * 100
              delta_str = f"{delta_pct:+.2f}% vs first"
            else:
              delta_str = "N/A"

            val_str = f"{val:,.2f}" if pd.notna(val) else "N/A"
            kpi_cols[idx].metric(label, val_str, delta_str)


 # ---------------- Combined Chart ----------------------------
        st.subheader("📈 Combined Time Series Chart")

        # 🔁 建立完整日期索引
        full_idx = pd.date_range(
          start=st.session_state['start_date'],
          end=st.session_state['end_date'],
          freq='D'
        )
        data = data.reindex(full_idx)

# 選擇要畫的欄位
        plot_columns = list(data.columns)

# 移除重複欄位：如果有月度 ECOMSA 就移除季度版
        if "E-commerce Sales (ECOMSA, Monthly)" in plot_columns and "E-commerce Sales (ECOMSA, Quarterly)" in plot_columns:
          plot_columns.remove("E-commerce Sales (ECOMSA, Quarterly)")

# 確保至少有欄位要畫
        if not plot_columns:
          st.warning("No valid data series to plot.")
        else:
        # 🔄 將 DataFrame 轉為 long format：Date, Series, Value
          df_plot = data[plot_columns].copy()
          df_plot["Date"] = df_plot.index
          df_long = df_plot.melt(id_vars="Date", var_name="Series", value_name="Value")

    # 丟掉沒有值的列（這樣不會整圖被 NaN 搞壞）
          df_long = df_long.dropna()

          fig_combined = px.line(
            df_long,
            x="Date",
            y="Value",
            color="Series",
            title="📈 Combined Time Series Data",
          )
          fig_combined.update_layout(
            xaxis=dict(range=[st.session_state['start_date'], st.session_state['end_date']])
          )
          st.plotly_chart(fig_combined, use_container_width=True)



# --- Individual Charts ---
#        st.subheader("📈 Time Series Charts")
#        plot_columns = list(data.columns)
#        # 只有當存在月度 ECOMSA 時，才移除季度版避免重複顯示
#        if "E-commerce Sales (ECOMSA, Monthly)" in plot_columns and "E-commerce Sales (ECOMSA, Quarterly)" in plot_columns:
#           plot_columns.remove("E-commerce Sales (ECOMSA, Quarterly)")
#
#        # 繪製各欄位個別圖表
#
#        for col in plot_columns:
#            y_data = data[col].dropna()
#            if y_data.empty:
#              st.warning(f"No data available for {col}")
#              continue
#            fig = px.line(x=y_data.index, y=y_data.values, title=col)
#            st.plotly_chart(fig, use_container_width=True)


 # ---------------- Correlation Heatmap -----------------------

        st.subheader("🔍 Correlation (Pct Change)")
        corr = data.pct_change().dropna().corr()
        fig_corr = px.imshow(corr, text_auto=True, aspect="auto")
        st.plotly_chart(fig_corr, use_container_width=True)

    else:
        st.warning("⚠️ No data loaded. Please check API key or series selection.")
else:
    st.info("🔑 Please enter your FRED API key in the sidebar.")

 # --- Sidebar footer ------------------------------------------------
sidebar.markdown("---")
sidebar.markdown("""
ℹ️ **Tips**

• ECOMSA is quarterly; check "Resample to Monthly" to smooth it.

• Data from FRED: https://fred.stlouisfed.org

• Add your own series in `SERIES_CODES`.
""")

