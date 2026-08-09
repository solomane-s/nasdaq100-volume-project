# NASDAQ100 VOLUME

## Project Overview

A **100% cloud-based data pipeline** that tracks the **daily trading volume of the Nasdaq 100 index** (`^NDX`). The pipeline is fully automated, runs daily without any manual intervention.

### Technologies Used

| Technology | Purpose |
| :--- | :--- |
| **Git** | Version control and code hosting |
| **Python** | Data extraction script |
| **AWS S3** | Raw data storage (CSV files) |
| **Snowflake** | Data warehouse (storage and compute) |
| **dbt Cloud** | Data transformation and modeling |

---

## Pipeline Schedule (UTC)

The pipeline runs automatically every day at the following times:

| Time (UTC) | Step | Tool | Action |
| :--- | :--- | :--- | :--- |
| **20:00** | Extract | GitHub Actions | Fetch Nasdaq 100 volume via `yfinance` → Upload to S3 |
| **20:30** | Load | Snowflake Task | `COPY INTO` from S3 → Table `RAW.RAW_NASDAQ_VOLUME` |
| **21:00** | Transform | dbt Cloud Job | Execute models → Update `ANALYTICS.DAILY_VOLUME_MART` |

> ✅ **Pipeline Consistency**: Extraction (20:00) runs before Loading (20:30), which runs before Transformation (21:00). Data flows through the pipeline in chronological order with no day lag.

---

## 📁 Project Structure

```
nasdaq100-volume-project/
├── .github/
│   └── workflows/
│       └── daily_extract.yml          # GitHub Actions workflow (20:00 UTC)
│
├── extraction/
│   ├── script.py                      # Python extraction script
│   └── requirements.txt               # Python dependencies
│
├── models/                            # dbt models (at root level)
│   ├── sources.yml                    # RAW source declaration
│   ├── staging/
│   │   └── stg_nasdaq_volume.sql      # Data cleaning & typing
│   ├── dimensions/
│   │   └── dim_date.sql               # Calendar dimension
│   ├── facts/
│   │   └── fact_daily_volume.sql      # Daily volume fact table
│   └── marts/
│       └── daily_volume_mart.sql      # Final mart (volume + 7-day MA)
│
├── dbt_project.yml                    # dbt project configuration
├── packages.yml                       # (Optional) dbt package dependencies
└── README.md                          # Project documentation (this file)
```

---

## 🔧 Configuration Keys

| Element | Value |
| :--- | :--- |
| **GitHub Workflow** | `daily_extract.yml` – Runs at 20:00 UTC |
| **Snowflake Task** | `LOAD_NASDAQ_VOLUME` – Runs at 20:30 UTC |
| **dbt Cloud Job** | `Daily Nasdaq Transform` – Runs at 21:00 UTC |
| **S3 Bucket** | `nasdaq100-volume-data` |
| **GitHub Repository** | `nasdaq100-volume-project` |
| **Snowflake Database** | `NASDAQ_DB` |
| **Source Schema** | `RAW` |
| **Target Schema** | `ANALYTICS` |
| **Snowflake Warehouse** | `NASDAQ_WH` |
| **Snowflake User** | `DBT_USER` (RSA Key Pair authentication) |
| **Snowflake Role** | `DBT_ROLE` (read on `RAW`, write on `ANALYTICS`) |
| **RSA Public Key** | Set on `DBT_USER` in Snowflake |
| **RSA Private Key** | Stored in dbt Cloud credentials (Dev & Production) |

---

## Pipeline Steps

### Step 1 – Automated Extraction (GitHub Actions → S3)

- Python script (`extraction/script.py`) fetches daily Nasdaq 100 volume using `yfinance`
- Code is hosted on **GitHub**
- **GitHub Actions** runs the script daily at **20:00 UTC**
- CSV file is uploaded to **AWS S3** at:
  ```
  s3://nasdaq100-volume-data/raw/nasdaq100_volume/YYYY-MM-DD/volume.csv
  ```
- AWS credentials stored as GitHub Secrets
- **Status**: ✅ Tested and functional

### Step 2 – Automated Loading (Snowflake)

- Snowflake account created (free trial)
- Warehouse `NASDAQ_WH` configured
- Database `NASDAQ_DB` created with schemas:
  - `RAW` – Raw data storage
  - `ANALYTICS` – Transformed data
- **Storage Integration** (`nasdaq_s3_integration`) with IAM role `SnowflakeAccessRole`
- External stage `NASDAQ_VOLUME_STAGE` pointing to S3
- Table `RAW.RAW_NASDAQ_VOLUME` (columns: `DATE`, `VOLUME`)
- **Scheduled Task** `LOAD_NASDAQ_VOLUME` runs at **20:30 UTC** with:
  - `TRUNCATE` before loading (prevents duplicates)
  - `COPY INTO` to load new CSV files
- **Status**: ✅ Tested and functional

### Step 3 – Data Transformation (dbt Cloud)

- dbt Cloud project initialized and connected to GitHub
- Authentication uses **RSA Key Pair** (avoids MFA)
- Dedicated role `DBT_ROLE` with necessary permissions:
  - Read on `RAW.RAW_NASDAQ_VOLUME`
  - Create tables/views in `ANALYTICS`
- Models created and deployed:

| Model | Location | Materialization | Description |
| :--- | :--- | :--- | :--- |
| `stg_nasdaq_volume` | `models/staging/` | View | Data cleaning and typing |
| `dim_date` | `models/dimensions/` | Table | Calendar dimension (2010–present) |
| `fact_daily_volume` | `models/facts/` | Table | Daily volume fact table |
| `daily_volume_mart` | `models/marts/` | View | Final mart: volume + 7-day moving average |

- dbt Cloud job scheduled at **21:00 UTC** running `dbt run` and `dbt test`
- **Status**: ✅ Tested and functional

---

## 📦 Final Deliverables

- ✅ Daily CSV file in S3 (`raw/nasdaq100_volume/YYYY-MM-DD/volume.csv`)
- ✅ Raw table `RAW.RAW_NASDAQ_VOLUME` in Snowflake
- ✅ Modeled view `ANALYTICS.DAILY_VOLUME_MART` containing:
  - `DATE_KEY` – Trading date
  - `VOLUME` – Daily trading volume
  - `VOLUME_7D_AVG` – 7-day moving average
- ✅ Fully automated daily execution with no manual intervention
- ✅ Three pipeline steps execute in logical order without day lag

---

## 🚀 Getting Started

### Prerequisites

1. **AWS Account** with S3 bucket `nasdaq100-volume-data`
2. **Snowflake Account** (free trial)
3. **dbt Cloud Account** (Developer tier – free)
4. **GitHub Repository** `nasdaq100-volume-project`

### Setup Instructions

Detailed setup instructions are available in the project documentation:

- **Step 1**: GitHub Actions → AWS S3 (Extraction)
- **Step 2**: Snowflake Setup & Automated Loading
- **Step 3**: dbt Cloud Transformation & Modeling

---

## 📝 Notes

- All pipeline steps are **100% cloud-based**
- The pipeline runs **automatically every day**
- **RSA Key Pair** authentication is used for Snowflake to avoid MFA interruptions
- The table `RAW.RAW_NASDAQ_VOLUME` is **truncated** before each load to prevent duplicates

---

## 📄 License

This project is for educational and personal use.

---
