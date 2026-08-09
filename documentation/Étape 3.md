# Étape 3 – Transformation avec dbt Cloud

---

## Objectif

Mettre en place un pipeline de transformation de données avec **dbt Cloud** pour :

1. **Nettoyer et typer** les données brutes chargées dans `RAW.RAW_NASDAQ_VOLUME`.
2. Créer une **dimension date** (calendrier) pour faciliter les analyses temporelles.
3. Construire une **table de faits** (volume quotidien) et un **mart** final avec une moyenne mobile sur 7 jours.
4. **Automatiser** l'exécution quotidienne via un job planifié dans dbt Cloud, après le chargement des données (21h00 UTC).

---

## Prérequis

Avant de commencer, assurez-vous d'avoir :

| Élément | Statut | Description |
| :--- | :--- | :--- |
| **Compte dbt Cloud** | ✅ Requis | Essai gratuit ou licence Developer |
| **Dépôt GitHub** | ✅ Requis | `nasdaq100-volume-project` (créé à l'étape 1) |
| **Compte Snowflake** | ✅ Requis | Compte avec `NASDAQ_WH`, `NASDAQ_DB`, schémas `RAW` et `ANALYTICS` |
| **Utilisateur Snowflake** | ✅ Requis | `DBT_USER` avec authentification par clé RSA |
| **Rôle Snowflake** | ✅ Requis | `DBT_ROLE` avec permissions sur `RAW` (lecture) et `ANALYTICS` (écriture) |

---

## 1. Gestion des permissions Snowflake (rôle `DBT_ROLE`)

Pour que dbt puisse lire `RAW` et écrire dans `ANALYTICS`, exécutez ce script dans Snowflake (avec `ACCOUNTADMIN`) **avant toute exécution dbt** :

```sql
USE ROLE ACCOUNTADMIN;

-- Créer le rôle s'il n'existe pas
CREATE ROLE IF NOT EXISTS DBT_ROLE;

-- Droits sur l'entrepôt
GRANT USAGE ON WAREHOUSE NASDAQ_WH TO ROLE DBT_ROLE;

-- Droits sur la base
GRANT USAGE ON DATABASE NASDAQ_DB TO ROLE DBT_ROLE;

-- Droits sur RAW (lecture)
GRANT USAGE ON SCHEMA NASDAQ_DB.RAW TO ROLE DBT_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA NASDAQ_DB.RAW TO ROLE DBT_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA NASDAQ_DB.RAW TO ROLE DBT_ROLE;

-- Droits sur ANALYTICS (écriture)
GRANT USAGE ON SCHEMA NASDAQ_DB.ANALYTICS TO ROLE DBT_ROLE;
-- Donner tous les droits pour simplifier (CREATE TABLE, CREATE VIEW, etc.)
GRANT ALL ON SCHEMA NASDAQ_DB.ANALYTICS TO ROLE DBT_ROLE;

-- Attribuer le rôle à DBT_USER
GRANT ROLE DBT_ROLE TO USER DBT_USER;
ALTER USER DBT_USER SET DEFAULT_ROLE = DBT_ROLE;

-- Définir le warehouse par défaut (recommandé)
ALTER USER DBT_USER SET DEFAULT_WAREHOUSE = NASDAQ_WH;
```

---

## 2. Génération de la clé RSA (authentification Key Pair)

> **Pourquoi une clé RSA ?** L'authentification par mot de passe déclenche la MFA. Pour un pipeline 100 % automatisé, utilisez **Key Pair**.

### 2.1 Générer les clés (via GitHub Codespaces)

Depuis votre dépôt GitHub `nasdaq100-volume-project`, créez un **Codespace** (ou utilisez AWS CloudShell) :

```bash
# Générer la clé privée RSA de 2048 bits (sans phrase de passe)
openssl genrsa -out snowflake_key.pem 2048

# Extraire la clé publique au format accepté par Snowflake (une seule ligne)
openssl rsa -in snowflake_key.pem -pubout -outform PEM | tail -n +2 | head -n -1 | tr -d '\n' > snowflake_key.pub
```

### 2.2 Installer la clé publique dans Snowflake

1. Affichez la clé publique :
   ```bash
   cat snowflake_key.pub
   ```
2. Copiez la **longue chaîne de caractères** (sans les marqueurs `-----BEGIN/END PUBLIC KEY-----`).
3. Dans Snowflake (avec `ACCOUNTADMIN`), exécutez :
   ```sql
   ALTER USER DBT_USER SET RSA_PUBLIC_KEY = '<clé_publique>';
   ```

### 2.3 Conserver la clé privée

- La clé privée (`snowflake_key.pem`) servira à configurer dbt Cloud.
- **Ne la commitez jamais sur GitHub** – conservez-la dans un gestionnaire de mots de passe sécurisé.

---

## 3. Configuration des environnements dbt Cloud

dbt Cloud distingue deux environnements : **Développement** (IDE) et **Déploiement** (Production). **Les identifiants sont indépendants** : il faut les configurer séparément.

### 3.1 Environnement de développement (IDE)

1. Dans dbt Cloud, allez dans **Develop** → **Settings** (⚙️) → **Development Credentials**.
2. Remplissez les champs :

| Champ | Valeur |
| :--- | :--- |
| **Account** | `xy12345.eu-west-3.aws` (votre identifiant Snowflake) |
| **User** | `DBT_USER` |
| **Authentication** | `Key Pair` |
| **Private Key** | Coller l'intégralité du fichier `snowflake_key.pem` |
| **Private Key Passphrase** | Laisser vide |
| **Role** | `DBT_ROLE` (ou laisser vide) |
| **Warehouse** | `NASDAQ_WH` **Ne pas confondre avec Database** |
| **Database** | `NASDAQ_DB` |
| **Schema** | `ANALYTICS` |

3. Cliquez sur **Save**.
4. Testez la connexion dans l'IDE :
   ```bash
   dbt debug
   ```
   Vous devez voir `All checks passed!`.

### 3.2 Environnement de déploiement (Production)

1. Allez dans **Deploy** → **Environments**.
2. Sélectionnez votre environnement (par défaut `Production`).
3. **Remplissez exactement les mêmes paramètres** que pour le développement :

| Champ | Valeur |
| :--- | :--- |
| **Account** | `xy12345.eu-west-3.aws` |
| **User** | `DBT_USER` |
| **Authentication** | `Key Pair` |
| **Private Key** | Coller la clé privée complète |
| **Private Key Passphrase** | Laisser vide |
| **Role** | `DBT_ROLE` |
| **Warehouse** | `NASDAQ_WH` **C'est le warehouse, pas la database** |
| **Database** | `NASDAQ_DB` |
| **Schema** | `ANALYTICS` |

4. Sauvegardez.

---

## 4. Initialisation du projet dbt et connexion au dépôt GitHub

1. Dans dbt Cloud, créez un **nouveau projet** :
   - **Nom** : `nasdaq_volume`
   - **Dépôt** : connectez-le à `nasdaq100-volume-project`
   - **Branche par défaut** : `main`

2. Une fois le projet créé, ouvrez l'IDE (Develop).

3. La structure du projet doit correspondre à celle de votre dépôt :

```
nasdaq100-volume-project/
├── models/
│   ├── sources.yml
│   ├── staging/
│   │   └── stg_nasdaq_volume.sql
│   ├── dimensions/
│   │   └── dim_date.sql
│   ├── facts/
│   │   └── fact_daily_volume.sql
│   └── marts/
│       └── daily_volume_mart.sql
├── dbt_project.yml
└── README.md
```

---

## 5. Création des modèles (modélisation en étoile)

Nous allons créer **4 modèles** : staging, dimension date, table de faits et mart final.

### 5.1 Fichier `dbt_project.yml` (à la racine)

```yaml
name: 'nasdaq_volume'
version: '1.0.0'
config-version: 2

profile: 'default'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  nasdaq_volume:
    staging:
      +materialized: view
    dimensions:
      +materialized: table
    facts:
      +materialized: table
    marts:
      +materialized: view
```

> 💡 **Remarque** : Les `+schema` ont été volontairement retirés pour garder tous les objets dans `ANALYTICS`. Cela simplifie la gestion des permissions.

### 5.2 Déclaration de la source : `models/sources.yml`

```yaml
version: 2

sources:
  - name: raw
    database: NASDAQ_DB
    schema: RAW
    tables:
      - name: RAW_NASDAQ_VOLUME
        description: "Volume quotidien du Nasdaq 100 chargé depuis S3"
```

### 5.3 Modèle Staging : `models/staging/stg_nasdaq_volume.sql`

```sql
with source as (
    select * from {{ source('raw', 'RAW_NASDAQ_VOLUME') }}
),

cleaned as (
    select
        try_to_date(date) as trading_date,
        volume
    from source
    where volume is not null
)

select * from cleaned
```

### 5.4 Dimension Date : `models/dimensions/dim_date.sql`

```sql
{{ config(materialized='table') }}

with date_spine as (
    select
        dateadd(day, seq4(), '2010-01-01') as date_day
    from table(generator(rowcount => 10000))
    where date_day <= current_date()
)

select
    date_day,
    year(date_day) as year,
    month(date_day) as month,
    monthname(date_day) as month_name,
    day(date_day) as day_of_month,
    dayofweek(date_day) as day_of_week,
    dayname(date_day) as day_name,
    quarter(date_day) as quarter,
    weekofyear(date_day) as week_of_year
from date_spine
```

### 5.5 Table de Faits : `models/facts/fact_daily_volume.sql`

```sql
{{ config(materialized='table') }}

select
    d.date_day as date_key,
    coalesce(v.volume, 0) as volume
from {{ ref('dim_date') }} d
left join {{ ref('stg_nasdaq_volume') }} v
    on d.date_day = v.trading_date
where d.date_day <= current_date()
```

### 5.6 Mart final : `models/marts/daily_volume_mart.sql`

```sql
select
    date_key,
    volume,
    avg(volume) over (order by date_key rows between 6 preceding and current row) as volume_7d_avg
from {{ ref('fact_daily_volume') }}
order by date_key
```

---

## 6. Exécution manuelle et validation dans l'IDE

### 6.1 Exécuter les modèles

Dans l'IDE dbt Cloud, ouvrez un terminal et lancez :

```bash
dbt run
```

Cela va créer tous les modèles dans l'ordre (staging → dim_date → fact → mart).

### 6.2 Vérifier dans Snowflake

```sql
-- Voir les objets créés
SHOW OBJECTS IN SCHEMA NASDAQ_DB.ANALYTICS;

-- Vérifier les données du mart
SELECT * FROM NASDAQ_DB.ANALYTICS.DAILY_VOLUME_MART 
ORDER BY DATE_KEY DESC 
LIMIT 10;
```

### 6.3 (Optionnel) Ajouter des tests

Créez un fichier `models/schema.yml` :

```yaml
version: 2

models:
  - name: stg_nasdaq_volume
    columns:
      - name: trading_date
        tests:
          - not_null
          - unique
      - name: volume
        tests:
          - not_null

  - name: fact_daily_volume
    columns:
      - name: date_key
        tests:
          - not_null
          - unique
```

Puis exécutez :

```bash
dbt test
```

---

## 7. Mise en place du job planifié (production)

### 7.1 Créer le job

1. Dans dbt Cloud, allez dans **Deploy** → **Jobs**.
2. Cliquez sur **+ New Job**.
3. Remplissez les champs :

| Champ | Valeur |
| :--- | :--- |
| **Job name** | `Daily Nasdaq Transform` |
| **Environment** | Environnement de production |
| **Commands** | `dbt run` et `dbt test` |
| **Schedule** | `0 21 * * *` (21h00 UTC) |

4. Cliquez sur **Save**.

### 7.2 Tester le job

- Cliquez sur **Run now** pour exécuter le job manuellement.
- Vérifiez que tous les modèles passent en vert.

> **Erreur fréquente** : Si le job échoue avec `No active warehouse selected`, vérifiez que l'environnement de production a bien **Warehouse = NASDAQ_WH** (et non `NASDAQ_DB`).

---

## 8. Gestion du versionnement (Git)

- **Branche de développement** : créez une branche `feature/dbt-models` dans l'IDE (en haut à gauche, à côté de `main`).
- **Commits** : effectuez des commits réguliers (bouton **Commit** en bas à gauche).
- **Pull Request** : poussez la branche vers GitHub et créez une PR vers `main`.

> 💡 **Recommandation** : Ne commitez jamais les fichiers contenant des clés privées ou secrets. Utilisez les **secrets GitHub** et les variables d'environnement dbt Cloud.

---

## 9. Synthèse des points d'attention (checklist finale)

| Élément | Statut | Détails |
| :--- | :--- | :--- |
| [ ] Clé publique RSA | ✅ Installée | Sur `DBT_USER` dans Snowflake |
| [ ] Clé privée RSA | ✅ Copiée | Dans les credentials dbt (Dev et Prod) |
| [ ] Rôle `DBT_ROLE` | ✅ Configuré | Droits sur `RAW` (lecture) et `ANALYTICS` (écriture) |
| [ ] Warehouse | ✅ Renseigné | `NASDAQ_WH` dans l'environnement de production |
| [ ] `dbt debug` | ✅ Validé | Connexion OK en développement |
| [ ] `dbt run` | ✅ Validé | Modèles créés dans `ANALYTICS` |
| [ ] Job planifié | ✅ Créé | Planifié à 21h00 UTC |
| [ ] Données du mart | ✅ Vérifiées | `DAILY_VOLUME_MART` accessible et cohérente |

---

## 10. Résumé de l'étape 3

| Élément | Statut | Description |
| :--- | :--- | :--- |
| **Authentification** | ✅ Key Pair | Clé RSA générée et installée sur `DBT_USER` |
| **Projet dbt** | ✅ Créé | `nasdaq_volume` connecté au dépôt GitHub |
| **Environnements** | ✅ Configurés | Dev et Production avec clé RSA |
| **Modèles dbt** | ✅ Créés | Staging, dimension, fait, mart |
| **Permissions** | ✅ Configurées | Rôle `DBT_ROLE` avec droits nécessaires |
| **Job planifié** | ✅ Créé | Exécution quotidienne à 21h00 UTC |
| **Tests** | ✅ (Optionnel) | Intégrité des données vérifiée |

---
