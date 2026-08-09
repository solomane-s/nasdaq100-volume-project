## Contexte - NASDAQ100-VOLUME-PROJECT

### Objectif

Construire un pipeline de données **100 % cloud** pour suivre quotidiennement le **volume de l’indice Nasdaq 100** (symbole `^NDX`). L’objectif est de disposer d’un flux de données automatisé, sans aucune intervention manuelle – même votre Mac éteint.

L’architecture suit un **schéma en étoile** (Staging → Dimensions, Faits → Marts) et s’appuie sur les technologies suivantes :

- **Git** – Versionnement du code
- **Python** – Script d’extraction
- **AWS S3** – Stockage des fichiers bruts
- **Snowflake** – Entrepôt de données
- **dbt Cloud** – Transformation et modélisation

---

### État d’avancement

#### Étape 1 – Extraction automatique et stockage

- Un script Python (`extraction/script.py`) récupère chaque jour le volume quotidien du Nasdaq 100 via la bibliothèque `yfinance`.
- Le code est hébergé sur **GitHub**.
- **GitHub Actions** exécute le script chaque jour à **20h00 UTC** via un workflow planifié.
- Le fichier CSV résultant est déposé dans un bucket **AWS S3** à l’emplacement :
  ```
  s3://nasdaq100-volume-data/raw/nasdaq100_volume/YYYY-MM-DD/volume.csv
  ```
- Les secrets AWS (clés d’accès) sont stockés dans GitHub et utilisés par l’action officielle `configure-aws-credentials`.
- **Testé et fonctionnel** : le fichier arrive bien dans S3 chaque jour automatiquement.

#### Étape 2 – Chargement automatique dans Snowflake

- Compte Snowflake créé (essai gratuit).
- Entrepôt `NASDAQ_WH` configuré.
- Base `NASDAQ_DB` créée avec les schémas :
  - `RAW` – Données brutes
  - `ANALYTICS` – Données transformées
- **Intégration de stockage** (`nasdaq_s3_integration`) créée avec les droits IAM nécessaires :
  - Rôle AWS `SnowflakeAccessRole`
  - Politique autorisant `s3:ListBucket` et `s3:GetObject` sur le dossier S3.
- Stage externe `NASDAQ_VOLUME_STAGE` pointant vers `s3://nasdaq100-volume-data/raw/nasdaq100_volume/`.
- Table `RAW.RAW_NASDAQ_VOLUME` (colonnes `DATE` et `VOLUME`).
- **Tâche planifiée** `LOAD_NASDAQ_VOLUME` exécutée chaque jour à **20h30 UTC** pour charger automatiquement les nouveaux fichiers CSV via `COPY INTO`.
- **Testé et fonctionnel** : la commande `LIST` voit les fichiers, la tâche charge les données.

#### Étape 3 – Transformation avec dbt Cloud

- Un projet dbt Cloud a été initialisé et connecté au dépôt GitHub.
- La connexion à Snowflake utilise l’authentification par **clé RSA** (Key Pair) pour éviter la MFA.
- Un rôle dédié `DBT_ROLE` a été créé avec les permissions nécessaires :
  - Lecture sur `RAW.RAW_NASDAQ_VOLUME`
  - Création de tables/vues dans `ANALYTICS`
- Les modèles suivants ont été créés et déployés avec succès :

| Modèle | Emplacement | Matérialisation | Description |
| :--- | :--- | :--- | :--- |
| `stg_nasdaq_volume` | `models/staging/` | Vue | Nettoyage et typage des données brutes |
| `dim_date` | `models/dimensions/` | Table | Dimension calendaire (dates de 2010 à aujourd’hui) |
| `fact_daily_volume` | `models/facts/` | Table | Table de faits : volume quotidien par date |
| `daily_volume_mart` | `models/marts/` | Vue | Vue finale : volume + moyenne mobile 7 jours |

- Un job dbt Cloud a été configuré et planifié à **21h00 UTC** pour exécuter `dbt run` et `dbt test` chaque jour.
- **Testé et fonctionnel** : les transformations s’exécutent automatiquement et la vue `ANALYTICS.DAILY_VOLUME_MART` est mise à jour quotidiennement.

---

### Horaires du pipeline (UTC)

| Heure (UTC) | Étape | Outil | Action |
| :--- | :--- | :--- | :--- |
| **20h00** | Extraction | GitHub Actions | Récupération du volume Nasdaq 100 via `yfinance` → Dépôt dans S3 |
| **20h30** | Chargement | Snowflake (tâche) | `COPY INTO` depuis S3 → Table `RAW.RAW_NASDAQ_VOLUME` |
| **21h00** | Transformation | dbt Cloud (job) | Exécution des modèles → Mise à jour de `ANALYTICS.DAILY_VOLUME_MART` |

> **Cohérence du pipeline** : L’extraction (20h00) s’exécute avant le chargement (20h30), lui‑même suivi de la transformation (21h00). Les données sont donc traitées dans le même ordre chronologique, sans décalage d’un jour.

---

### Points de configuration clés

| Élément | Valeur |
| :--- | :--- |
| **Workflow GitHub Actions** | `daily_extract.yml` – Exécution à 20h00 UTC |
| **Tâche Snowflake** | `LOAD_NASDAQ_VOLUME` – Exécution à 20h30 UTC |
| **Job dbt Cloud** | `Daily Nasdaq Transform` – Exécution à 21h00 UTC |
| **Bucket S3** | `nasdaq100-volume-data` |
| **Dépôt GitHub** | `nasdaq100-volume-project` |
| **Base Snowflake** | `NASDAQ_DB` |
| **Schéma source** | `RAW` |
| **Schéma cible** | `ANALYTICS` |
| **Entrepôt Snowflake** | `NASDAQ_WH` |
| **Utilisateur Snowflake** | `DBT_USER` (authentification par clé RSA) |
| **Rôle Snowflake** | `DBT_ROLE` (lecture sur `RAW`, écriture sur `ANALYTICS`) |
| **Clé publique RSA** | Définie sur `DBT_USER` dans Snowflake |
| **Clé privée RSA** | Stockée dans les credentials dbt Cloud (Dev et Production) |

---

### Livrables finaux du pipeline

- ✅ Un fichier CSV quotidien dans S3 (`raw/nasdaq100_volume/YYYY-MM-DD/volume.csv`).
- ✅ Une table brute `RAW.RAW_NASDAQ_VOLUME` dans Snowflake.
- ✅ Une vue modélisée `ANALYTICS.DAILY_VOLUME_MART` contenant :
  - `DATE_KEY` – La date de trading
  - `VOLUME` – Le volume quotidien
  - `VOLUME_7D_AVG` – La moyenne mobile sur 7 jours
- ✅ Une exécution automatisée et fiable chaque jour, sans intervention humaine.
- ✅ Les trois étapes s’enchaînent dans un ordre logique et sans décalage.

---

### 📁 Structure GitHub

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
```

---
