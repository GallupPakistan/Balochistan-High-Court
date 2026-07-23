# ⚖️ BHC Cause List Analytics Dashboard

An interactive Streamlit dashboard for analyzing publicly published cause lists from the **Balochistan High Court** (Principal Seat Quetta, its benches, and tribunals) — hearing schedules, bench composition, judge workload, case types, and case aging.

## Features

- **🏠 Home** — project overview and a KPI snapshot (total cases, judge panels, avg CMAs/case, date range, month-over-month case volume change)
- **📊 Overview** — case distribution by category, section, bench type, and institution
- **👨‍⚖️ Judges & Workload** — judge panel caseloads, court room utilization, judge × section workload heatmaps
- **📁 Case Types & Trends** — case type breakdowns, filing trends over time, advocate activity
- **⏳ Pendency & Aging** — re-listing frequency and hearing-gap analysis per judge panel and section (a proxy for case aging, since the source data has no filing/disposal date)
- **🔍 Case Explorer** — full-text search and filtering across the case list, with CSV export
- **Global sidebar filters** (date range, institution, judges) apply across every tab, with a one-click CSV export of the filtered view
- Every chart offers a **Chart / Table** toggle, and category colors stay consistent for the same value across every tab

## Tech Stack

- [Streamlit](https://streamlit.io/) — app framework
- [Plotly Express](https://plotly.com/python/plotly-express/) — charts
- [Pandas](https://pandas.pydata.org/) — data processing
- [OpenPyXL](https://openpyxl.readthedocs.io/) — Excel file reading (via pandas)

## Getting Started

### Prerequisites

- Python 3.9+

### Installation

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
pip install -r requirements.txt
```

### Data Setup

Place the source Excel file at:

```
data/BHC_Cause_List_Combined.xlsx
```

It must contain a sheet named `Cause List` with (at minimum) these columns: `Source File`, `Date`, `Category`, `Judges`, `Case Type`, `Advocate`, `Section`, `Institution`, `Bench Type`, `Court Room`, `Case No`, `Petitioner`, `Respondent`, `CMAs`.

Optionally, add a court image at:

```
assets/bhc_gate.jpg
```

### Run

```bash
streamlit run app1.py
```

The app opens at `http://localhost:8501`.

## Project Structure

```
.
├── app1.py                          # Main Streamlit app
├── data/
│   └── BHC_Cause_List_Combined.xlsx # Source cause list data (not included)
├── assets/
│   └── bhc_gate.jpg                 # Court image for the Home tab (optional)
├── requirements.txt
└── README.md
```

## Disclaimer

The data presented in this dashboard is sourced from publicly available cause lists published by the Balochistan High Court. The information has been compiled and parsed for improved understanding and accessibility.

## License

MIT — feel free to fork and adapt for other courts or jurisdictions.
