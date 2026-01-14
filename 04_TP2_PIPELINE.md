# TP2 — Pipeline d'acquisition et transformation de données

## Informations

| | |
|---|---|
| **Durée** | 14h30-17h45 (3h15) (réparties sur la journée) |
| **Format** | TP noté (autonomie avec support) |
| **Livrable** | Script Python + données Parquet + README |
| **Évaluation** | Note de TD (individuelle) |

---

## Objectifs pédagogiques

À l'issue de ce TP, vous serez capables de :

1. ✅ Interroger une API REST Open Data
2. ✅ Gérer la pagination et les erreurs
3. ✅ Transformer et nettoyer des données avec l'aide de l'IA
4. ✅ Stocker des données au format Parquet
5. ✅ Construire un pipeline reproductible

---

## Contexte

Vous travaillez pour une startup d'analyse de données. Votre mission : construire un pipeline automatisé qui récupère des données Open Data via API, les nettoie, et les stocke dans un format optimisé pour l'analyse.

---

## Partie 1 : Choix de l'API et exploration (45 min)

### 1.1 APIs suggérées

Choisissez UNE API parmi les suivantes :

| API | Thème | Documentation | Difficulté |
|-----|-------|---------------|------------|
| **OpenFoodFacts** | Alimentation | [Lien](https://openfoodfacts.github.io/openfoodfacts-server/api/) | ⭐⭐ |
| **data.gouv.fr** | Catalogue national | [Lien](https://doc.data.gouv.fr/api/reference/) | ⭐ |
| **Adresse (BAN)** | Géocodage | [Lien](https://adresse.data.gouv.fr/api-doc/adresse) | ⭐ |
| **OpenMeteo** | Météo | [Lien](https://open-meteo.com/en/docs) | ⭐⭐ |
| **SIRENE** | Entreprises | [Lien](https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee) | ⭐⭐⭐ |

### 1.2 Configuration du projet

```bash
# Si vous continuez depuis le TP1
cd tp1-exploration
uv add httpx tenacity tqdm

# OU nouveau projet
uv init tp2-pipeline
cd tp2-pipeline
uv add pandas duckdb httpx litellm python-dotenv tenacity tqdm pyarrow
```

> ⚠️ **Note** : `httpx` est un **package Python** (comme `requests`), pas le protocole web HTTPS ! C'est une alternative moderne à `requests` avec support async natif.

### 1.3 Explorer l'API avec l'IA

Créez `exploration_api.py` :

```python
"""Exploration de l'API avec l'assistant IA."""
import httpx
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

def ask_api_assistant(question: str, api_doc: str = "") -> str:
    """Assistant spécialisé dans les APIs."""
    response = completion(
        model="gemini/gemini-2.0-flash-exp",
        messages=[
            {
                "role": "system", 
                "content": """Tu es un expert en APIs REST et en data engineering.
                Tu aides à comprendre et utiliser des APIs Open Data.
                Génère du code Python avec httpx quand on te le demande."""
            },
            {"role": "user", "content": f"{api_doc}\n\nQuestion: {question}"}
        ]
    )
    return response.choices[0].message.content


# Exemple avec OpenFoodFacts
API_DOC = """
API OpenFoodFacts :
- Base URL: https://world.openfoodfacts.org/api/v2
- Endpoint produits: /product/{barcode}.json
- Endpoint recherche: /search.json?categories_tags={category}&page_size={n}
- Pas d'authentification requise
- Rate limit: soyez raisonnables (1 req/sec)
"""

# Demander à l'IA comment utiliser l'API
print(ask_api_assistant(
    "Comment récupérer les 100 premiers produits de la catégorie 'chocolats' ?",
    API_DOC
))
```

### 1.4 Premier appel API

```python
"""Test de l'API."""
import httpx

# Exemple OpenFoodFacts - adapter selon votre API
BASE_URL = "https://world.openfoodfacts.org/api/v2"

def test_api():
    """Test un appel simple à l'API."""
    response = httpx.get(
        f"{BASE_URL}/search",
        params={
            "categories_tags": "chocolats",
            "page_size": 5,
            "fields": "code,product_name,brands,nutriscore_grade"
        },
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    
    print(f"Nombre de produits : {data.get('count', 'N/A')}")
    for product in data.get("products", []):
        print(f"- {product.get('product_name', 'N/A')} ({product.get('brands', 'N/A')})")
    
    return data

if __name__ == "__main__":
    test_api()
```

---

## Partie 2 : Construction du pipeline d'acquisition (1h30)

### 2.1 Structure du pipeline

```
pipeline/
├── __init__.py
├── config.py          # Configuration (URLs, paramètres)
├── fetcher.py         # Récupération des données
├── transformer.py     # Nettoyage et transformation
├── storage.py         # Stockage Parquet
└── main.py            # Orchestration
```

### 2.2 Module de configuration

Créez `pipeline/config.py` :

```python
"""Configuration du pipeline."""
from pathlib import Path

# Chemins
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Créer les dossiers
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# API Configuration (adapter selon votre API)
API_BASE_URL = "https://world.openfoodfacts.org/api/v2"
API_TIMEOUT = 30
API_RATE_LIMIT = 1.0  # secondes entre chaque requête

# Paramètres d'acquisition
PAGE_SIZE = 100
MAX_PAGES = 10  # Limiter pour le TP
```

### 2.3 Module de récupération

Créez `pipeline/fetcher.py` :

```python
"""Module de récupération des données via API."""
import time
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

from .config import API_BASE_URL, API_TIMEOUT, API_RATE_LIMIT, PAGE_SIZE, MAX_PAGES


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_page(endpoint: str, params: dict) -> dict:
    """
    Récupère une page de données avec retry automatique.
    
    Args:
        endpoint: Chemin de l'API (ex: "/search")
        params: Paramètres de la requête
    
    Returns:
        Données JSON de la réponse
    """
    url = f"{API_BASE_URL}{endpoint}"
    
    with httpx.Client(timeout=API_TIMEOUT) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def fetch_all_data(category: str) -> list[dict]:
    """
    Récupère toutes les données d'une catégorie avec pagination.
    
    Args:
        category: Catégorie à récupérer (ex: "chocolats")
    
    Returns:
        Liste de tous les produits
    """
    all_products = []
    
    for page in tqdm(range(1, MAX_PAGES + 1), desc="Récupération"):
        params = {
            "categories_tags": category,
            "page": page,
            "page_size": PAGE_SIZE,
            "fields": "code,product_name,brands,categories,nutriscore_grade,nova_group,"
                      "energy_100g,fat_100g,sugars_100g,salt_100g,proteins_100g"
        }
        
        try:
            data = fetch_page("/search", params)
            products = data.get("products", [])
            
            if not products:
                print(f"Plus de données à la page {page}")
                break
                
            all_products.extend(products)
            
            # Respecter le rate limit
            time.sleep(API_RATE_LIMIT)
            
        except Exception as e:
            print(f"Erreur page {page}: {e}")
            continue
    
    print(f"Total récupéré : {len(all_products)} produits")
    return all_products


if __name__ == "__main__":
    # Test
    products = fetch_all_data("chocolats")
    print(f"Premier produit : {products[0] if products else 'Aucun'}")
```

### 2.4 Exercice : Adapter à votre API

**À vous de jouer !** Modifiez le code ci-dessus pour l'adapter à l'API que vous avez choisie.

Utilisez l'assistant IA pour vous aider :

```python
# Dans votre notebook ou script
prompt = f"""
J'ai cette API : [VOTRE API]
Documentation : [LIEN]

Adapte le code de fetcher.py pour récupérer [CE QUE VOUS VOULEZ].
Garde la même structure avec retry et pagination.
"""

print(ask_api_assistant(prompt))
```

---

## Partie 3 : Transformation et nettoyage (1h15)

### 3.1 Module de transformation

Créez `pipeline/transformer.py` :

```python
"""Module de transformation et nettoyage des données."""
import pandas as pd
from litellm import completion
from dotenv import load_dotenv

load_dotenv()


def raw_to_dataframe(raw_data: list[dict]) -> pd.DataFrame:
    """Convertit les données brutes en DataFrame."""
    df = pd.DataFrame(raw_data)
    print(f"DataFrame créé : {df.shape}")
    return df


def generate_cleaning_code(df: pd.DataFrame) -> str:
    """
    Utilise l'IA pour générer du code de nettoyage adapté.
    
    Args:
        df: DataFrame à nettoyer
    
    Returns:
        Code Python de nettoyage
    """
    context = f"""
    DataFrame à nettoyer :
    - Colonnes : {list(df.columns)}
    - Types : {df.dtypes.to_dict()}
    - Valeurs manquantes : {df.isnull().sum().to_dict()}
    - Échantillon : {df.head(3).to_dict()}
    """
    
    response = completion(
        model="gemini/gemini-2.0-flash-exp",
        messages=[
            {
                "role": "system",
                "content": """Tu es un expert en data cleaning.
                Génère du code Python/Pandas pour nettoyer ce DataFrame.
                Le code doit être exécutable directement.
                Inclus : gestion des valeurs manquantes, types, normalisation."""
            },
            {"role": "user", "content": f"{context}\n\nGénère le code de nettoyage complet."}
        ]
    )
    
    return response.choices[0].message.content


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie le DataFrame.
    
    Cette fonction implémente le nettoyage standard.
    Adaptez-la selon le code généré par l'IA.
    """
    df_clean = df.copy()
    
    # --- Nettoyage standard (à adapter) ---
    
    # 1. Supprimer les doublons
    initial_count = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    print(f"Doublons supprimés : {initial_count - len(df_clean)}")
    
    # 2. Gérer les valeurs manquantes
    # Colonnes texte : remplacer par "Non renseigné"
    text_cols = df_clean.select_dtypes(include=['object']).columns
    df_clean[text_cols] = df_clean[text_cols].fillna("Non renseigné")
    
    # Colonnes numériques : remplacer par la médiane
    num_cols = df_clean.select_dtypes(include=['number']).columns
    for col in num_cols:
        median_val = df_clean[col].median()
        df_clean[col] = df_clean[col].fillna(median_val)
    
    # 3. Normaliser les textes
    for col in text_cols:
        df_clean[col] = df_clean[col].str.strip().str.lower()
    
    # 4. Supprimer les outliers extrêmes (optionnel)
    # for col in num_cols:
    #     q1, q3 = df_clean[col].quantile([0.01, 0.99])
    #     df_clean = df_clean[(df_clean[col] >= q1) & (df_clean[col] <= q3)]
    
    print(f"DataFrame nettoyé : {df_clean.shape}")
    return df_clean


if __name__ == "__main__":
    # Test avec des données fictives
    test_data = [
        {"name": "  Test  ", "value": 10, "category": None},
        {"name": "Test", "value": None, "category": "A"},
        {"name": "Other", "value": 20, "category": "B"},
    ]
    
    df = raw_to_dataframe(test_data)
    print("\n--- Code de nettoyage suggéré par l'IA ---")
    print(generate_cleaning_code(df))
    print("\n--- Résultat du nettoyage ---")
    df_clean = clean_dataframe(df)
    print(df_clean)
```

### 3.2 Exercice : Personnaliser le nettoyage

1. Exécutez `generate_cleaning_code()` avec vos données réelles
2. Analysez le code proposé par l'IA
3. Intégrez les transformations pertinentes dans `clean_dataframe()`
4. Testez et ajustez

---

## Partie 4 : Stockage et orchestration (45 min)

### 4.1 Module de stockage

Créez `pipeline/storage.py` :

```python
"""Module de stockage des données."""
import pandas as pd
from datetime import datetime
from .config import RAW_DIR, PROCESSED_DIR


def save_raw_json(data: list[dict], name: str) -> str:
    """Sauvegarde les données brutes en JSON."""
    import json
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = RAW_DIR / f"{name}_{timestamp}.json"
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Données brutes sauvegardées : {filepath}")
    return str(filepath)


def save_parquet(df: pd.DataFrame, name: str) -> str:
    """
    Sauvegarde le DataFrame en Parquet.
    
    Pourquoi Parquet ?
    - Compression efficace (5-10x plus petit que CSV)
    - Types de données préservés
    - Lecture ultra-rapide (colonnar)
    - Compatible DuckDB, Spark, etc.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = PROCESSED_DIR / f"{name}_{timestamp}.parquet"
    
    df.to_parquet(filepath, index=False, compression="snappy")
    
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"Données sauvegardées : {filepath} ({size_mb:.2f} MB)")
    return str(filepath)


def load_parquet(filepath: str) -> pd.DataFrame:
    """Charge un fichier Parquet."""
    return pd.read_parquet(filepath)


if __name__ == "__main__":
    # Test
    test_df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    path = save_parquet(test_df, "test")
    loaded = load_parquet(path)
    print(loaded)
```

### 4.2 Script principal

Créez `pipeline/main.py` :

```python
"""Script principal du pipeline."""
import argparse
from .fetcher import fetch_all_data
from .transformer import raw_to_dataframe, clean_dataframe
from .storage import save_raw_json, save_parquet


def run_pipeline(category: str, name: str):
    """
    Exécute le pipeline complet.
    
    Args:
        category: Catégorie à récupérer
        name: Nom pour les fichiers de sortie
    """
    print("=" * 50)
    print(f"PIPELINE : {name}")
    print("=" * 50)
    
    # Étape 1 : Acquisition
    print("\n📥 Étape 1 : Acquisition des données")
    raw_data = fetch_all_data(category)
    save_raw_json(raw_data, name)
    
    # Étape 2 : Transformation
    print("\n🔧 Étape 2 : Transformation")
    df = raw_to_dataframe(raw_data)
    df_clean = clean_dataframe(df)
    
    # Étape 3 : Stockage
    print("\n💾 Étape 3 : Stockage")
    output_path = save_parquet(df_clean, name)
    
    print("\n" + "=" * 50)
    print("✅ Pipeline terminé avec succès !")
    print(f"📁 Fichier : {output_path}")
    print("=" * 50)
    
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Open Data")
    parser.add_argument("--category", default="chocolats", help="Catégorie à récupérer")
    parser.add_argument("--name", default="products", help="Nom du dataset")
    
    args = parser.parse_args()
    run_pipeline(args.category, args.name)
```

### 4.3 Exécution

```bash
# Créer le package
touch pipeline/__init__.py

# Exécuter
uv run python -m pipeline.main --category chocolats --name chocolats_fr
```

---

## Partie 5 : Vérification avec DuckDB (15 min)

```python
"""Vérification des données avec DuckDB."""
import duckdb

# Charger le Parquet
con = duckdb.connect()
df = con.execute("""
    SELECT * 
    FROM read_parquet('data/processed/chocolats_fr_*.parquet')
""").df()

# Statistiques
print(con.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT brands) as unique_brands,
        AVG(sugars_100g) as avg_sugar
    FROM read_parquet('data/processed/chocolats_fr_*.parquet')
""").df())

# Vérifier la qualité
print("\nValeurs manquantes :")
print(df.isnull().sum())
```

---

## Livrables attendus

📁 **Structure du rendu :**
```
tp2-pipeline/
├── .env
├── .gitignore
├── pyproject.toml
├── pipeline/
│   ├── __init__.py
│   ├── config.py
│   ├── fetcher.py
│   ├── transformer.py
│   ├── storage.py
│   └── main.py
├── data/
│   ├── raw/
│   │   └── *.json
│   └── processed/
│       └── *.parquet
├── notebooks/
│   └── exploration.ipynb
└── README.md
```

---

## Critères d'évaluation

| Critère | Points | Description |
|---------|--------|-------------|
| **Pipeline fonctionnel** | /5 | Exécution de bout en bout sans erreur |
| **Gestion des erreurs** | /3 | Retry, rate limiting, messages clairs |
| **Qualité du nettoyage** | /3 | Transformations pertinentes, données propres |
| **Format Parquet** | /2 | Stockage correct, vérifiable |
| **Documentation** | /2 | README clair, code commenté |
| **Total** | /15 | |

---

## Bonus

- **+2** : Ajouter des tests unitaires
- **+1** : Ajouter des logs (module `logging`)
- **+1** : Dockeriser le pipeline
