# Étape 2 – Chargement automatique dans Snowflake

---

## Objectif

Configurer Snowflake pour qu'il **charge automatiquement** chaque jour les fichiers CSV déposés dans S3 par GitHub Actions. L'objectif est d'avoir un pipeline entièrement automatisé où les données brutes sont disponibles dans Snowflake sans aucune intervention manuelle.

---

## Prérequis

- Un compte AWS avec le bucket `nasdaq100-volume-data` créé (Étape 1).
- Un compte Snowflake (essai gratuit).

---

## 2.1 Créer un compte d'essai Snowflake

1. Rendez-vous sur [https://signup.snowflake.com](https://signup.snowflake.com).
2. Remplissez le formulaire :
   - **Édition** : Standard (l'essai gratuit inclut 400$ de crédits).
   - **Cloud Provider** : AWS.
   - **Région** : choisissez la **même région** que votre bucket S3 (ex. `eu-west-3` pour Paris). Cela évite des frais de transfert et simplifie la configuration.
3. Activez votre compte via l'email de vérification.
4. Connectez-vous à la console Snowflake (Snowsight).

---

## 2.2 Configurer l'entrepôt, la base et les schémas

Dans Snowflake, ouvrez un **worksheet** et exécutez les commandes suivantes :

```sql
-- Créer un entrepôt (compute)
CREATE WAREHOUSE IF NOT EXISTS NASDAQ_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

-- Créer la base de données
CREATE DATABASE IF NOT EXISTS NASDAQ_DB;

-- Créer les schémas
CREATE SCHEMA IF NOT EXISTS NASDAQ_DB.RAW;
CREATE SCHEMA IF NOT EXISTS NASDAQ_DB.ANALYTICS;
```

---

## 2.3 Créer l'intégration de stockage (Storage Integration)

L'intégration de stockage permet à Snowflake de lire les fichiers dans votre bucket S3 de manière sécurisée, **sans exposer vos clés AWS permanentes**.

Exécutez ceci dans un worksheet :

```sql
CREATE STORAGE INTEGRATION IF NOT EXISTS nasdaq_s3_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<VOTRE_COMPTE_AWS>:role/SnowflakeAccessRole'
  STORAGE_ALLOWED_LOCATIONS = ('s3://nasdaq100-volume-data/raw/nasdaq100_volume/');
```

**Remplacez `<VOTRE_COMPTE_AWS>` par votre ID de compte AWS** (un nombre à 12 chiffres, visible dans le coin supérieur droit de la console AWS).

> **Important** : Ne créez pas encore le rôle IAM `SnowflakeAccessRole` dans AWS – nous allons le faire à l'étape suivante.

---

## 2.4 Récupérer l'utilisateur IAM Snowflake et l'ID externe

Exécutez la commande suivante pour obtenir les informations nécessaires à la configuration côté AWS :

```sql
DESC STORAGE INTEGRATION nasdaq_s3_integration;
```

Notez les **deux valeurs** suivantes dans le résultat :

| Propriété | Exemple |
| :--- | :--- |
| `STORAGE_AWS_IAM_USER_ARN` | `arn:aws:iam::123456789:user/abc...` |
| `STORAGE_AWS_EXTERNAL_ID` | `OKTA123...` |

---

## 2.5 Créer le rôle IAM dans AWS et attacher la politique de confiance

Nous allons maintenant autoriser Snowflake à accéder à votre bucket S3 via un **rôle IAM dédié**.

### Étape 1 : Créer la politique S3

1. Dans la console AWS, allez dans **IAM** → **Politiques** → **Créer une politique**.
2. Dans l'onglet **JSON**, collez ce contenu :

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectVersion"
            ],
            "Resource": "arn:aws:s3:::nasdaq100-volume-data/raw/nasdaq100_volume/*"
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::nasdaq100-volume-data",
            "Condition": {
                "StringLike": {
                    "s3:prefix": ["raw/nasdaq100_volume/*"]
                }
            }
        }
    ]
}
```

3. Nommez la politique **`S3GetObject-nasdaq100`** et créez-la.

### Étape 2 : Créer le rôle IAM

1. Dans la console AWS, allez dans **IAM** → **Rôles** → **Créer un rôle**.
2. **Type d'entité de confiance** : **Un compte AWS**.
3. Choisissez **Un autre compte AWS** et entrez l'ID du compte Snowflake (extrait du `STORAGE_AWS_IAM_USER_ARN`, la partie après `::`).
4. **Ne cochez pas** "Exiger un ID externe" pour l'instant.
5. Cliquez sur **Suivant**.
6. Attachez la politique **`S3GetObject-nasdaq100`**.
7. Cliquez sur **Suivant**.
8. Nommez le rôle : **`SnowflakeAccessRole`**.
9. Créez le rôle.

### Étape 3 : Modifier la relation de confiance

1. Ouvrez le rôle **`SnowflakeAccessRole`** dans IAM.
2. Allez dans l'onglet **Relations de confiance** (Trust relationships).
3. Cliquez sur **Modifier la politique de confiance**.
4. Remplacez le contenu par :

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "<STORAGE_AWS_IAM_USER_ARN>"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": "<STORAGE_AWS_EXTERNAL_ID>"
                }
            }
        }
    ]
}
```

**Remplacez** les deux valeurs entre `<>` par celles notées à l'étape 2.4.

5. Cliquez sur **Mettre à jour la politique**.

---

## 2.6 Créer le stage externe dans Snowflake

De retour dans Snowflake, créez un **stage** qui pointe vers le dossier de votre bucket :

```sql
CREATE STAGE IF NOT EXISTS NASDAQ_DB.RAW.NASDAQ_VOLUME_STAGE
  STORAGE_INTEGRATION = nasdaq_s3_integration
  URL = 's3://nasdaq100-volume-data/raw/nasdaq100_volume/';
```

Testez que Snowflake voit bien les fichiers (vous devez avoir le fichier CSV du test de l'étape 1) :

```sql
LIST @NASDAQ_DB.RAW.NASDAQ_VOLUME_STAGE;
```

Vous devriez voir apparaître le dossier de date et le fichier `volume.csv`.

---

## 2.7 Créer la table de destination

```sql
USE SCHEMA NASDAQ_DB.RAW;

CREATE TABLE IF NOT EXISTS RAW_NASDAQ_VOLUME (
    DATE TEXT,
    VOLUME NUMBER
);
```

---

## 2.8 Mettre en place le chargement automatique quotidien avec une tâche

Nous allons créer une **tâche planifiée** qui exécute un `COPY INTO` tous les jours à **20h30 UTC** (30 minutes après l'arrivée du fichier via GitHub Actions à 20h00 UTC).

### Créer la tâche

```sql
CREATE OR REPLACE TASK LOAD_NASDAQ_VOLUME
  WAREHOUSE = NASDAQ_WH
  SCHEDULE = 'USING CRON 30 20 * * * UTC'
AS
  BEGIN
    TRUNCATE TABLE NASDAQ_DB.RAW.RAW_NASDAQ_VOLUME;
    
    COPY INTO NASDAQ_DB.RAW.RAW_NASDAQ_VOLUME
    FROM @NASDAQ_DB.RAW.NASDAQ_VOLUME_STAGE
    FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1)
    PATTERN = '.*/volume.csv';
  END;
```

### Activer la tâche

```sql
ALTER TASK LOAD_NASDAQ_VOLUME RESUME;
```

### Tester manuellement (charger les données existantes)

```sql
EXECUTE TASK LOAD_NASDAQ_VOLUME;
```

### Vérifier le contenu de la table

```sql
SELECT * FROM NASDAQ_DB.RAW.RAW_NASDAQ_VOLUME;
```

---

## Résumé de l'étape 2

| Élément | Statut | Détails |
| :--- | :--- | :--- |
| **Compte Snowflake** | ✅ Créé | Essai gratuit, région `eu-west-3` |
| **Entrepôt** | ✅ Créé | `NASDAQ_WH` (XSMALL, auto-suspend) |
| **Base de données** | ✅ Créée | `NASDAQ_DB` |
| **Schémas** | ✅ Créés | `RAW` et `ANALYTICS` |
| **Intégration de stockage** | ✅ Créée | `nasdaq_s3_integration` |
| **Stage externe** | ✅ Créé | `NASDAQ_VOLUME_STAGE` pointant vers S3 |
| **Table RAW** | ✅ Créée | `RAW.RAW_NASDAQ_VOLUME` (DATE, VOLUME) |
| **Tâche planifiée** | ✅ Créée | `LOAD_NASDAQ_VOLUME` à 20h30 UTC |
| **Chargement automatique** | ✅ Testé | `COPY INTO` fonctionnel |

---
