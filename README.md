
# Pipeline de Données Chocolat

Ce projet implémente un **pipeline complet de traitement de données** pour les produits chocolat en France. Il inclut :

* Collecte des données brutes
* Nettoyage et transformation
* Sauvegarde en formats JSON et Parquet
* Vérification et analyse via DuckDB
* Visualisation et préparation pour l’analyse

---

## Structure du projet

```
tp2-PIPELINE/
│
├─ data/
│  ├─ raw/             # Données brutes JSON
│  └─ processed/       # Données nettoyées Parquet
│
├─ pipeline/
│  ├─ _init_.py
│  ├─ transformer.py   # Nettoyage et transformation des données
│  ├─ storage.py       # Sauvegarde et chargement des fichiers
│  └─ config.py        # Répertoires de stockage
│  ├─ fetcher.py
│  ├─ main.py
│
├─ notebooks/
│  └─ exploration.ipynb   # Vérification et statistiques des données
│
├─ .env            # Variables d’environnement
├─ .gitignore
├─ pyproject.toml   # Dépendances Python
└─ README.md
```

---

## Installation

1. Cloner le projet

```bash
git clone https://github.com/Ousow/tp2-PIPELINE
cd tp2-PIPELINE
```

2. Créer un environnement virtuel Python

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

3. Installer les dépendances

```bash
pip install -r requirements.txt
```

4. Créer le fichier `.env` et ajouter les clés nécessaires pour l’IA (si applicable).

---

## Utilisation

### 1. Collecte et sauvegarde des données brutes

```python
from pipeline.storage import save_raw_json

data = [
    {"name": "Chocolat A", "energy_100g": 500, "brands": "Brand1"},
    {"name": "Chocolat B", "energy_100g": 450, "brands": "Brand2"}
]

save_raw_json(data, name="chocolats_fr")
```

### 2. Nettoyage des données

```python
from pipeline.transformer import raw_to_dataframe, clean_dataframe

df_raw = raw_to_dataframe(data)
df_clean = clean_dataframe(df_raw)
```

### 3. Sauvegarde des données nettoyées

```python
from pipeline.storage import save_parquet

save_parquet(df_clean, name="chocolats_clean")
```

### 4. Vérification et statistiques avec DuckDB

```python
import duckdb

con = duckdb.connect()
df = con.execute("SELECT * FROM read_parquet('data/processed/chocolats_clean_*.parquet')").df()

print(df.describe())   # Statistiques numériques
print(df['brands'].value_counts().head(10))  # Top 10 des marques
```

---

## Fonctionnalités

* Nettoyage automatique des valeurs manquantes
* Normalisation des colonnes numériques
* Standardisation et encodage des colonnes catégoriques (marques)
* Suppression des doublons et des outliers (optionnel)
* Sauvegarde en JSON et Parquet pour compatibilité et performance

---

## Technologies utilisées

* **Python 3.11+**
* **Pandas** pour le traitement des données
* **DuckDB** pour requêtes et vérification rapide
* **Scikit-learn** pour normalisation et encodage
* **LiteLLM / Ollama** pour génération de code de nettoyage 


## Auteur : 
Oumou SOW
