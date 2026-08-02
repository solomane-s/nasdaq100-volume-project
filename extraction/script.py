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
    # Date de la veille (le marché peut être fermé le weekend, on prend alors le dernier jour ouvré disponible)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')

    logger.info(f"Téléchargement des données de {yesterday} à {today} pour ^NDX")
    # On télécharge une plage de 5 jours pour être sûr d'avoir au moins la veille
    start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    data = yf.download('^NDX', start=start_date, end=today)

    if data.empty:
        raise ValueError("Aucune donnée téléchargée. Vérifiez la connexion ou le symbole.")

    # On récupère la dernière ligne disponible (le jour le plus récent)
    last_day = data.index[-1]
    volume = data.loc[last_day, 'Volume']

    # Si le volume est une Series (cas possible), on prend la première valeur
    if isinstance(volume, pd.Series):
        volume = volume.iloc[0]

    df = pd.DataFrame({
        'Date': [last_day.strftime('%Y-%m-%d')],
        'Volume': [int(volume)]
    })
    logger.info(f"Volume extrait : {volume} pour le {last_day.date()}")
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
    print("Extraction et upload terminés avec succès.")

if __name__ == '__main__':
    main()