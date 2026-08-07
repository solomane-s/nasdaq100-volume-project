```
nasdaq100-volume-project/
├── .github/
│   └── workflows/
│       └── daily_extract.yml          # Workflow GitHub Actions (20h00 UTC)
│
├── extraction/
│   ├── script.py                      # Script d'extraction Python
│   └── requirements.txt               # Dépendances (yfinance, pandas, boto3)
│
├── models/                            # Projet dbt (à la racine)
│   ├── sources.yml                    # Déclaration de la source RAW
│   ├── staging/
│   │   └── stg_nasdaq_volume.sql      # Nettoyage et typage
│   ├── dimensions/
│   │   └── dim_date.sql               # Dimension calendaire
│   ├── facts/
│   │   └── fact_daily_volume.sql      # Table de faits
│   └── marts/
│       └── daily_volume_mart.sql      # Vue finale (volume + moyenne mobile)
│
├── dbt_project.yml                    # Configuration du projet dbt
├── packages.yml                       # (Optionnel) Dépendances dbt
└── README.md                          # Documentation du projet
```# nasdaq100-volume-project
