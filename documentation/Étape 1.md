# Étape 1 – Extraction automatique avec GitHub Actions et stockage sur S3

---

## Objectif

Récupérer **chaque jour** le volume de l'indice Nasdaq 100 (symbole `^NDX`) via un script Python, et déposer un fichier CSV dans un bucket **AWS S3**.

L’exécution est **100 % cloud** :
- Le code est hébergé sur **GitHub**.
- Le script tourne dans **GitHub Actions**.
- Les données atterrissent dans **S3**.

Aucune dépendance à votre Mac, qui peut rester éteint.

---

## 1. Création du dépôt GitHub

Créez un dépôt vide sur GitHub (ex. `nasdaq100-volume-project`).

Structure du projet à obtenir :

```
nasdaq100-volume-project/
├── .github/
│   └── workflows/
│       └── daily_extract.yml
├── extraction/
│   ├── script.py
│   └── requirements.txt
└── README.md
```

---

## 2. Script Python d'extraction

### Fichier `extraction/script.py`

```python
import yfinance as yf
import pandas as pd
import boto3
from datetime import datetime, timedelta
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv('BUCKET_NAME', 'nasdaq100-volume-data')
PREFIX = 'raw/nasdaq100_volume'

def get_yesterday_volume():
    start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    logger.info(f"Téléchargement des données de {start_date} à {today} pour ^NDX")
    
    data = yf.download('^NDX', start=start_date, end=today)
    if data.empty:
        raise ValueError("Aucune donnée téléchargée.")
    
    last_day = data.index[-1]
    volume = data.loc[last_day, 'Volume']
    if isinstance(volume, pd.Series):
        volume = volume.iloc[0]
    
    df = pd.DataFrame({
        'Date': [last_day.strftime('%Y-%m-%d')],
        'Volume': [int(volume)]
    })
    return df, last_day.strftime('%Y-%m-%d')

def upload_to_s3(df, date_str):
    s3 = boto3.client('s3', region_name='eu-west-3')
    key = f"{PREFIX}/{date_str}/volume.csv"
    csv_buffer = df.to_csv(index=False)
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=csv_buffer)
    logger.info(f"Fichier uploadé : s3://{BUCKET_NAME}/{key}")

def main():
    df, date_str = get_yesterday_volume()
    upload_to_s3(df, date_str)

if __name__ == '__main__':
    main()
```

### Fichier `extraction/requirements.txt`

```
yfinance
pandas
boto3
```

---

## 3. Workflow GitHub Actions

### Fichier `.github/workflows/daily_extract.yml`

```yaml
name: Extract Nasdaq Volume Daily

on:
  schedule:
    - cron: '0 20 * * *'
  workflow_dispatch:

jobs:
  extract-and-upload:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-west-3

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r extraction/requirements.txt

      - name: Run extraction script
        run: python extraction/script.py
```

---

## 4. Création du bucket S3

1. Dans la console AWS, recherchez **S3**.
2. Créez un bucket nommé **`nasdaq100-volume-data`** (ou un autre nom, en le mettant à jour dans le script et le workflow).
3. Choisissez une région (ex. **`eu-west-3`** pour Paris) – **notez cette région**, elle sera utilisée partout.
4. Laissez les paramètres par défaut (blocage de l’accès public activé).

---

## 5. Création des clés d’accès AWS (IAM)

Cette étape génère les identifiants permettant au script GitHub Actions de se connecter à AWS.

### 5.1 Créer un utilisateur IAM

1. Allez dans **IAM** → **Utilisateurs** → **Ajouter un utilisateur**.
2. **Nom d’utilisateur** : `github-actions-s3-writer`.
3. **Accès à la console de gestion AWS** : décochez.
4. **Type d’accès** : cochez **Clé d’accès - Accès programmatique**.
5. Cliquez sur **Suivant**.

### 5.2 Attacher une politique restreinte

1. Sélectionnez **Attacher directement les politiques existantes**, puis cliquez sur **Créer une politique**.
2. Dans l’onglet **JSON**, collez ce contenu :

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:PutObject",
            "Resource": "arn:aws:s3:::nasdaq100-volume-data/*"
        }
    ]
}
```

3. Cliquez sur **Suivant** → **Suivant** → Nommez la politique **`S3PutObject-nasdaq100`** → **Créer la politique**.
4. Revenez à l’onglet de création de l’utilisateur, rafraîchissez la liste des politiques, cochez `S3PutObject-nasdaq100`, puis **Suivant** jusqu’à **Créer l’utilisateur**.

### 5.3 Récupérer les clés d’accès

- Une fois l’utilisateur créé, vous arrivez sur une page de confirmation avec les clés.
- Cliquez sur **Afficher** à côté de la **Clé d’accès secrète**.
- **Téléchargez le fichier CSV** (c’est le seul moment où la clé secrète est visible).

Le CSV contient :
- **Access key ID** : exemple `AKIA...`
- **Secret access key** : une chaîne de 40 caractères.

> **Important** : Ces clés sont **programmatiques** – il n’y a pas de mot de passe console. Conservez-les précieusement.

---

## 6. Ajouter les secrets dans GitHub

1. Dans votre dépôt GitHub, allez dans **Settings** → **Secrets and variables** → **Actions**.
2. Créez un **New repository secret** :
   - **Name** : `AWS_ACCESS_KEY_ID`
   - **Value** : collez l’`Access key ID` du CSV.
3. Créez un second secret :
   - **Name** : `AWS_SECRET_ACCESS_KEY`
   - **Value** : collez la `Secret access key`.

> **Vérification** : Assurez-vous qu’il n’y a aucun espace ou retour à la ligne avant/après les valeurs.

---

## 7. Tester le workflow

1. Dans GitHub, allez dans l’onglet **Actions**.
2. Cliquez sur le workflow **Extract Nasdaq Volume Daily**.
3. Cliquez sur **Run workflow** → **Run workflow**.
4. Suivez les logs – le job doit se terminer avec succès (coches vertes).
5. Vérifiez le bucket S3 : un dossier `raw/nasdaq100_volume/YYYY-MM-DD/volume.csv` doit être apparu.

---

## 8. Exécution automatique quotidienne

Le workflow est planifié via la ligne :

```yaml
cron: '0 20 * * *'
```

Chaque jour à **20h00 UTC**, GitHub Actions exécutera automatiquement le script, sans aucune intervention. Vous pouvez suivre les exécutions dans l’onglet **Actions**.

---

## Résumé de l’étape 1

| Élément | Statut |
| :--- | :--- |
| Script Python d’extraction | ✅ Créé (`extraction/script.py`) |
| Dépendances Python | ✅ Déclarées (`extraction/requirements.txt`) |
| Workflow GitHub Actions | ✅ Créé et planifié (`daily_extract.yml`) |
| Bucket S3 | ✅ Créé (`nasdaq100-volume-data`) |
| Utilisateur IAM | ✅ Créé (`github-actions-s3-writer`) |
| Secrets GitHub | ✅ Configurés (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) |
| Exécution automatique | ✅ Testée et fonctionnelle (tous les jours à 20h UTC) |

---

**Une fois cette étape validée, vous disposez d’un flux d’extraction entièrement automatisé et cloud.**
