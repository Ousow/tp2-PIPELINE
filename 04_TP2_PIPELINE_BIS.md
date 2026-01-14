# TP2 — Pipeline d'acquisition et transformation de données

## Informations

| | |
|---|---|
| **Durée** | 5h (J2 après-midi complet + J3 matin si nécessaire) |
| **Format** | TP noté (autonomie avec support) |
| **Livrable** | Pipeline Python complet + données enrichies + rapport de qualité |
| **Évaluation** | Note de TD (individuelle) |

---

## Objectifs pédagogiques

À l'issue de ce TP, vous serez capables de :

1. ✅ Interroger **plusieurs APIs** REST Open Data
2. ✅ **Enrichir** des données en croisant plusieurs sources
3. ✅ Gérer la pagination, les erreurs et le rate limiting
4. ✅ Implémenter un **scoring de qualité** des données
5. ✅ Transformer et nettoyer des données avec l'aide de l'IA
6. ✅ Stocker des données au format Parquet avec **partitionnement**
7. ✅ Générer un **rapport de qualité** automatique
8. ✅ Construire un pipeline **reproductible et testé**

---

## Contexte

Vous êtes Data Engineer dans une startup d'analyse de données. Votre mission : construire un pipeline **de qualité production** qui :

1. Récupère des données depuis une API principale
2. **Enrichit** ces données avec une source secondaire
3. Valide et score la qualité des données
4. Génère un rapport de qualité pour le Data Analyst

Le pipeline doit être **robuste**, **documenté** et **testable**.

---

## Partie 1 : Choix des APIs et architecture (45 min)

### 1.1 Combinaisons d'APIs suggérées

Choisissez UNE combinaison parmi les suivantes :

| Combinaison | API Principale | API Enrichissement | Cas d'usage |
|-------------|----------------|-------------------|-------------|
| **A - Alimentaire + Géo** | OpenFoodFacts (produits) | API Adresse (géocodage magasins) | Cartographie des points de vente |
| **B - Entreprises + Géo** | SIRENE (entreprises) | API Adresse (géocodage sièges) | Analyse territoriale |
| **C - Météo + Géo** | OpenMeteo (prévisions) | API Adresse (villes françaises) | Dashboard météo enrichi |
| **D - Libre** | Votre choix | Votre choix | Justifier la pertinence |

### 1.2 Détails des APIs

#### API Adresse (Base Adresse Nationale) — ⭐ Recommandée pour l'enrichissement

**URL** : `https://api-adresse.data.gouv.fr`

| Avantages | Caractéristiques |
|-----------|------------------|
| ✅ Ultra-rapide (< 100ms) | Format GeoJSON |
| ✅ Très fiable | Coordonnées GPS + codes INSEE |
| ✅ Pas d'authentification | Score de confiance (0-1) |

```python
# Exemple de géocodage
import httpx

response = httpx.get(
    "https://api-adresse.data.gouv.fr/search/",
    params={"q": "20 avenue de ségur paris", "limit": 1},
    timeout=10
)
result = response.json()["features"][0]
print(f"Coordonnées: {result['geometry']['coordinates']}")
print(f"Score: {result['properties']['score']}")
```

#### OpenFoodFacts (Produits alimentaires)

**URL** : `https://world.openfoodfacts.org/api/v2`

| Avantages | ⚠️ Précautions |
|-----------|----------------|
| Données nutritionnelles riches | Timeout fréquents → **timeout=60** |
| Millions de produits | **User-Agent obligatoire** |
| Pas d'authentification | Réduire page_size à **50 max** |

```python
# Configuration recommandée pour OpenFoodFacts
headers = {"User-Agent": "IPSSI-TP/1.0 (contact@ipssi.fr)"}
response = httpx.get(
    "https://world.openfoodfacts.org/api/v2/search",
    params={"categories_tags": "chocolats", "page_size": 50},
    headers=headers,
    timeout=60  # Important !
)
```

### 1.3 Architecture du pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                         PIPELINE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   API    │    │   API    │    │  Trans-  │    │ Storage  │  │
│  │ Principale│───▶│Enrichiss.│───▶│ former   │───▶│ Parquet  │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │         │
│       ▼               ▼               ▼               ▼         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    QUALITY MONITOR                        │  │
│  │  • Métriques d'acquisition  • Scoring qualité            │  │
│  │  • Rapport automatique      • Alertes                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Configuration du projet

```bash
uv init tp2-pipeline
cd tp2-pipeline
uv add httpx pandas duckdb litellm python-dotenv tenacity tqdm pyarrow pydantic pytest
```

> ⚠️ **Note** : `httpx` est un **package Python** (comme `requests`), pas le protocole HTTPS !

---

## Partie 2 : Module d'acquisition multi-sources (1h30)

### 2.1 Structure du projet

```
tp2-pipeline/
├── .env
├── pyproject.toml
├── pipeline/
│   ├── __init__.py
│   ├── config.py           # Configuration centralisée
│   ├── models.py           # Modèles de données (Pydantic)
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py         # Classe abstraite
│   │   ├── openfoodfacts.py
│   │   └── adresse.py
│   ├── enricher.py         # Enrichissement croisé
│   ├── transformer.py      # Nettoyage et validation
│   ├── quality.py          # Scoring et rapport
│   ├── storage.py          # Stockage Parquet
│   └── main.py             # Orchestration
├── tests/
│   ├── __init__.py
│   ├── test_fetchers.py
│   └── test_transformer.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── reports/
└── README.md
```

### 2.2 Configuration centralisée

Créez `pipeline/config.py` :

```python
"""Configuration centralisée du pipeline."""
from pathlib import Path
from dataclasses import dataclass

# === Chemins ===
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

for dir_path in [RAW_DIR, PROCESSED_DIR, REPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class APIConfig:
    """Configuration d'une API."""
    name: str
    base_url: str
    timeout: int
    rate_limit: float  # secondes entre requêtes
    headers: dict = None
    
    def __post_init__(self):
        self.headers = self.headers or {}


# === Configurations des APIs ===
OPENFOODFACTS_CONFIG = APIConfig(
    name="OpenFoodFacts",
    base_url="https://world.openfoodfacts.org/api/v2",
    timeout=60,
    rate_limit=1.5,
    headers={"User-Agent": "IPSSI-TP-Pipeline/1.0 (contact@ipssi.fr)"}
)

ADRESSE_CONFIG = APIConfig(
    name="API Adresse",
    base_url="https://api-adresse.data.gouv.fr",
    timeout=10,
    rate_limit=0.1,  # Très rapide, peu de limite
)

# === Paramètres d'acquisition ===
MAX_ITEMS = 500  # Limite pour le TP
BATCH_SIZE = 50  # Taille des lots

# === Seuils de qualité ===
QUALITY_THRESHOLDS = {
    "completeness_min": 0.7,      # 70% des champs remplis
    "geocoding_score_min": 0.5,   # Score géocodage minimum
    "duplicates_max_pct": 5.0,    # Max 5% de doublons
}
```

### 2.3 Modèles de données avec Pydantic

Créez `pipeline/models.py` :

```python
"""Modèles de données avec validation."""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class Product(BaseModel):
    """Modèle d'un produit alimentaire."""
    code: str
    product_name: Optional[str] = None
    brands: Optional[str] = None
    categories: Optional[str] = None
    nutriscore_grade: Optional[str] = None
    nova_group: Optional[int] = None
    energy_100g: Optional[float] = None
    sugars_100g: Optional[float] = None
    fat_100g: Optional[float] = None
    salt_100g: Optional[float] = None
    
    # Champs d'enrichissement (ajoutés après géocodage)
    store_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    geocoding_score: Optional[float] = None
    
    # Métadonnées
    fetched_at: datetime = Field(default_factory=datetime.now)
    quality_score: Optional[float] = None
    
    @validator('nutriscore_grade')
    def validate_nutriscore(cls, v):
        if v and v.lower() not in ['a', 'b', 'c', 'd', 'e']:
            return None
        return v.lower() if v else None
    
    @validator('energy_100g', 'sugars_100g', 'fat_100g', 'salt_100g')
    def validate_positive(cls, v):
        if v is not None and v < 0:
            return None
        return v


class GeocodingResult(BaseModel):
    """Résultat de géocodage."""
    original_address: str
    label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    score: float = 0.0
    postal_code: Optional[str] = None
    city_code: Optional[str] = None
    city: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        return self.score >= 0.5 and self.latitude is not None


class QualityMetrics(BaseModel):
    """Métriques de qualité du dataset."""
    total_records: int
    valid_records: int
    completeness_score: float
    duplicates_count: int
    duplicates_pct: float
    geocoding_success_rate: float
    avg_geocoding_score: float
    null_counts: dict
    quality_grade: str  # A, B, C, D, F
    
    @property
    def is_acceptable(self) -> bool:
        return self.quality_grade in ['A', 'B', 'C']
```

### 2.4 Fetcher abstrait avec retry

Créez `pipeline/fetchers/base.py` :

```python
"""Classe de base pour les fetchers."""
import time
from abc import ABC, abstractmethod
from typing import Generator
import httpx
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging
from tqdm import tqdm

from ..config import APIConfig

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """Classe abstraite pour les fetchers d'API."""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.stats = {
            "requests_made": 0,
            "requests_failed": 0,
            "items_fetched": 0,
            "start_time": None,
            "end_time": None,
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Effectue une requête avec retry automatique."""
        url = f"{self.config.base_url}{endpoint}"
        
        with httpx.Client(
            timeout=self.config.timeout,
            headers=self.config.headers
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            self.stats["requests_made"] += 1
            return response.json()
    
    def _rate_limit(self):
        """Applique le rate limiting."""
        time.sleep(self.config.rate_limit)
    
    @abstractmethod
    def fetch_batch(self, **kwargs) -> list[dict]:
        """Récupère un lot de données. À implémenter."""
        pass
    
    @abstractmethod
    def fetch_all(self, **kwargs) -> Generator[dict, None, None]:
        """Récupère toutes les données avec pagination. À implémenter."""
        pass
    
    def get_stats(self) -> dict:
        """Retourne les statistiques d'acquisition."""
        return self.stats.copy()
```

### 2.5 Implémentation des fetchers

Créez `pipeline/fetchers/openfoodfacts.py` :

```python
"""Fetcher pour l'API OpenFoodFacts."""
from typing import Generator
from tqdm import tqdm

from .base import BaseFetcher
from ..config import OPENFOODFACTS_CONFIG, MAX_ITEMS, BATCH_SIZE
from ..models import Product


class OpenFoodFactsFetcher(BaseFetcher):
    """Fetcher pour OpenFoodFacts."""
    
    def __init__(self):
        super().__init__(OPENFOODFACTS_CONFIG)
        self.fields = [
            "code", "product_name", "brands", "categories",
            "nutriscore_grade", "nova_group", "energy_100g",
            "sugars_100g", "fat_100g", "salt_100g", "stores"
        ]
    
    def fetch_batch(self, category: str, page: int = 1, page_size: int = BATCH_SIZE) -> list[dict]:
        """Récupère une page de produits."""
        params = {
            "categories_tags": category,
            "page": page,
            "page_size": page_size,
            "fields": ",".join(self.fields)
        }
        
        try:
            data = self._make_request("/search", params)
            products = data.get("products", [])
            self.stats["items_fetched"] += len(products)
            return products
        except Exception as e:
            self.stats["requests_failed"] += 1
            print(f"⚠️ Erreur page {page}: {e}")
            return []
    
    def fetch_all(
        self, 
        category: str, 
        max_items: int = MAX_ITEMS,
        verbose: bool = True
    ) -> Generator[dict, None, None]:
        """Récupère tous les produits avec pagination."""
        from datetime import datetime
        
        self.stats["start_time"] = datetime.now()
        page = 1
        total_fetched = 0
        
        pbar = tqdm(total=max_items, desc=f"OpenFoodFacts [{category}]", disable=not verbose)
        
        while total_fetched < max_items:
            remaining = max_items - total_fetched
            page_size = min(BATCH_SIZE, remaining)
            
            products = self.fetch_batch(category, page, page_size)
            
            if not products:
                break
            
            for product in products:
                yield product
                total_fetched += 1
                pbar.update(1)
                
                if total_fetched >= max_items:
                    break
            
            page += 1
            self._rate_limit()
        
        pbar.close()
        self.stats["end_time"] = datetime.now()
        
        if verbose:
            duration = (self.stats["end_time"] - self.stats["start_time"]).seconds
            print(f"✅ {total_fetched} produits récupérés en {duration}s")
```

Créez `pipeline/fetchers/adresse.py` :

```python
"""Fetcher pour l'API Adresse (géocodage)."""
from typing import Generator
from tqdm import tqdm

from .base import BaseFetcher
from ..config import ADRESSE_CONFIG
from ..models import GeocodingResult


class AdresseFetcher(BaseFetcher):
    """Fetcher pour l'API Adresse (géocodage)."""
    
    def __init__(self):
        super().__init__(ADRESSE_CONFIG)
    
    def geocode_single(self, address: str) -> GeocodingResult:
        """Géocode une adresse unique."""
        if not address or address.strip() == "":
            return GeocodingResult(original_address=address or "", score=0)
        
        try:
            data = self._make_request("/search/", params={"q": address, "limit": 1})
            
            if not data.get("features"):
                return GeocodingResult(original_address=address, score=0)
            
            feature = data["features"][0]
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [None, None])
            
            self.stats["items_fetched"] += 1
            
            return GeocodingResult(
                original_address=address,
                label=props.get("label"),
                latitude=coords[1] if len(coords) > 1 else None,
                longitude=coords[0] if len(coords) > 0 else None,
                score=props.get("score", 0),
                postal_code=props.get("postcode"),
                city_code=props.get("citycode"),
                city=props.get("city"),
            )
        
        except Exception as e:
            self.stats["requests_failed"] += 1
            return GeocodingResult(original_address=address, score=0)
    
    def fetch_batch(self, addresses: list[str]) -> list[GeocodingResult]:
        """Géocode un lot d'adresses."""
        results = []
        for address in addresses:
            result = self.geocode_single(address)
            results.append(result)
            self._rate_limit()
        return results
    
    def fetch_all(
        self, 
        addresses: list[str], 
        verbose: bool = True
    ) -> Generator[GeocodingResult, None, None]:
        """Géocode toutes les adresses."""
        from datetime import datetime
        
        self.stats["start_time"] = datetime.now()
        
        iterator = tqdm(addresses, desc="Géocodage", disable=not verbose)
        
        for address in iterator:
            result = self.geocode_single(address)
            yield result
            self._rate_limit()
        
        self.stats["end_time"] = datetime.now()
        
        if verbose:
            success = sum(1 for _ in range(self.stats["items_fetched"]))
            print(f"✅ {self.stats['items_fetched']} adresses géocodées")
```

---

## Partie 3 : Enrichissement croisé (1h)

### 3.1 Module d'enrichissement

Créez `pipeline/enricher.py` :

```python
"""Module d'enrichissement des données."""
import pandas as pd
from typing import Optional
from tqdm import tqdm

from .fetchers.adresse import AdresseFetcher
from .models import Product, GeocodingResult


class DataEnricher:
    """Enrichit les données en croisant plusieurs sources."""
    
    def __init__(self):
        self.geocoder = AdresseFetcher()
        self.enrichment_stats = {
            "total_processed": 0,
            "successfully_enriched": 0,
            "failed_enrichment": 0,
        }
    
    def extract_addresses(self, products: list[dict], address_field: str = "stores") -> list[str]:
        """
        Extrait les adresses uniques des produits.
        
        Args:
            products: Liste des produits
            address_field: Champ contenant l'adresse/magasin
        
        Returns:
            Liste d'adresses uniques
        """
        addresses = set()
        
        for product in products:
            addr = product.get(address_field, "")
            if addr and isinstance(addr, str) and addr.strip():
                # Nettoyer et extraire les adresses (peuvent être séparées par virgules)
                for part in addr.split(","):
                    cleaned = part.strip()
                    if len(cleaned) > 3:  # Ignorer les trop courts
                        addresses.add(cleaned)
        
        return list(addresses)
    
    def build_geocoding_cache(self, addresses: list[str]) -> dict[str, GeocodingResult]:
        """
        Construit un cache de géocodage pour éviter les requêtes en double.
        
        Args:
            addresses: Liste d'adresses à géocoder
        
        Returns:
            Dictionnaire adresse -> résultat
        """
        cache = {}
        
        print(f"🌍 Géocodage de {len(addresses)} adresses uniques...")
        
        for result in self.geocoder.fetch_all(addresses):
            cache[result.original_address] = result
        
        success_rate = sum(1 for r in cache.values() if r.is_valid) / len(cache) * 100 if cache else 0
        print(f"✅ Taux de succès: {success_rate:.1f}%")
        
        return cache
    
    def enrich_products(
        self, 
        products: list[dict], 
        geocoding_cache: dict[str, GeocodingResult],
        address_field: str = "stores"
    ) -> list[dict]:
        """
        Enrichit les produits avec les données de géocodage.
        
        Args:
            products: Liste des produits
            geocoding_cache: Cache de géocodage
            address_field: Champ contenant l'adresse
        
        Returns:
            Liste des produits enrichis
        """
        enriched = []
        
        for product in tqdm(products, desc="Enrichissement"):
            self.enrichment_stats["total_processed"] += 1
            
            # Copier le produit
            enriched_product = product.copy()
            
            # Chercher l'adresse
            addr = product.get(address_field, "")
            if addr and isinstance(addr, str):
                # Prendre la première adresse si plusieurs
                first_addr = addr.split(",")[0].strip()
                
                if first_addr in geocoding_cache:
                    geo = geocoding_cache[first_addr]
                    
                    enriched_product["store_address"] = geo.label
                    enriched_product["latitude"] = geo.latitude
                    enriched_product["longitude"] = geo.longitude
                    enriched_product["city"] = geo.city
                    enriched_product["postal_code"] = geo.postal_code
                    enriched_product["geocoding_score"] = geo.score
                    
                    if geo.is_valid:
                        self.enrichment_stats["successfully_enriched"] += 1
                    else:
                        self.enrichment_stats["failed_enrichment"] += 1
            
            enriched.append(enriched_product)
        
        return enriched
    
    def get_stats(self) -> dict:
        """Retourne les statistiques d'enrichissement."""
        stats = self.enrichment_stats.copy()
        stats["geocoder_stats"] = self.geocoder.get_stats()
        
        if stats["total_processed"] > 0:
            stats["success_rate"] = stats["successfully_enriched"] / stats["total_processed"] * 100
        else:
            stats["success_rate"] = 0
        
        return stats
```

### 3.2 Exercice : Implémenter l'enrichissement

**À vous de jouer !** Adaptez l'enrichissement selon votre combinaison d'APIs :

```python
# Utilisez l'IA pour vous aider
from litellm import completion

prompt = """
Je veux enrichir mes données de [API PRINCIPALE] avec [API SECONDAIRE].

Données principales : [DESCRIPTION]
Enrichissement souhaité : [CE QUE VOUS VOULEZ AJOUTER]

Comment adapter le module enricher.py ?
"""

# Demander à l'IA
response = completion(
    model="gemini/gemini-2.0-flash-exp",
    messages=[{"role": "user", "content": prompt}]
)
print(response.choices[0].message.content)
```

---

## Partie 4 : Qualité des données et scoring (1h)

### 4.1 Module de qualité

Créez `pipeline/quality.py` :

```python
"""Module de scoring et rapport de qualité."""
import pandas as pd
from datetime import datetime
from pathlib import Path
from litellm import completion
from dotenv import load_dotenv

from .config import QUALITY_THRESHOLDS, REPORTS_DIR
from .models import QualityMetrics

load_dotenv()


class QualityAnalyzer:
    """Analyse et score la qualité des données."""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.metrics = None
    
    def calculate_completeness(self) -> float:
        """Calcule le score de complétude (% de valeurs non-nulles)."""
        total_cells = self.df.size
        non_null_cells = self.df.notna().sum().sum()
        return non_null_cells / total_cells if total_cells > 0 else 0
    
    def count_duplicates(self) -> tuple[int, float]:
        """Compte les doublons."""
        # Identifier la colonne d'ID
        id_col = 'code' if 'code' in self.df.columns else self.df.columns[0]
        
        duplicates = self.df.duplicated(subset=[id_col]).sum()
        pct = duplicates / len(self.df) * 100 if len(self.df) > 0 else 0
        
        return duplicates, pct
    
    def calculate_geocoding_stats(self) -> tuple[float, float]:
        """Calcule les stats de géocodage si applicable."""
        if 'geocoding_score' not in self.df.columns:
            return 0, 0
        
        valid_geo = self.df['geocoding_score'].notna() & (self.df['geocoding_score'] > 0)
        success_rate = valid_geo.sum() / len(self.df) * 100 if len(self.df) > 0 else 0
        avg_score = self.df.loc[valid_geo, 'geocoding_score'].mean() if valid_geo.any() else 0
        
        return success_rate, avg_score
    
    def calculate_null_counts(self) -> dict:
        """Compte les valeurs nulles par colonne."""
        return self.df.isnull().sum().to_dict()
    
    def determine_grade(self, completeness: float, duplicates_pct: float, geo_rate: float) -> str:
        """Détermine la note de qualité globale."""
        score = 0
        
        # Complétude (40 points max)
        score += min(completeness * 40, 40)
        
        # Doublons (30 points max)
        if duplicates_pct <= 1:
            score += 30
        elif duplicates_pct <= 5:
            score += 20
        elif duplicates_pct <= 10:
            score += 10
        
        # Géocodage (30 points max) - si applicable
        if 'geocoding_score' in self.df.columns:
            score += min(geo_rate / 100 * 30, 30)
        else:
            score += 30  # Pas de pénalité si pas de géocodage
        
        # Note finale
        if score >= 90:
            return 'A'
        elif score >= 75:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 40:
            return 'D'
        else:
            return 'F'
    
    def analyze(self) -> QualityMetrics:
        """Effectue l'analyse complète de qualité."""
        completeness = self.calculate_completeness()
        duplicates, duplicates_pct = self.count_duplicates()
        geo_rate, geo_avg = self.calculate_geocoding_stats()
        null_counts = self.calculate_null_counts()
        
        valid_records = len(self.df) - duplicates
        
        grade = self.determine_grade(completeness, duplicates_pct, geo_rate)
        
        self.metrics = QualityMetrics(
            total_records=len(self.df),
            valid_records=valid_records,
            completeness_score=round(completeness, 3),
            duplicates_count=duplicates,
            duplicates_pct=round(duplicates_pct, 2),
            geocoding_success_rate=round(geo_rate, 2),
            avg_geocoding_score=round(geo_avg, 3),
            null_counts=null_counts,
            quality_grade=grade,
        )
        
        return self.metrics
    
    def generate_ai_recommendations(self) -> str:
        """Génère des recommandations via l'IA."""
        if not self.metrics:
            self.analyze()
        
        context = f"""
        Analyse de qualité d'un dataset :
        - Total: {self.metrics.total_records} enregistrements
        - Complétude: {self.metrics.completeness_score * 100:.1f}%
        - Doublons: {self.metrics.duplicates_pct:.1f}%
        - Note: {self.metrics.quality_grade}
        
        Valeurs nulles par colonne:
        {self.metrics.null_counts}
        """
        
        response = completion(
            model="gemini/gemini-2.0-flash-exp",
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en qualité des données. Donne des recommandations concrètes et actionnables."
                },
                {
                    "role": "user", 
                    "content": f"{context}\n\nQuelles sont tes 5 recommandations prioritaires pour améliorer ce dataset ?"
                }
            ]
        )
        
        return response.choices[0].message.content
    
    def generate_report(self, output_name: str = "quality_report") -> Path:
        """Génère un rapport de qualité complet en Markdown."""
        if not self.metrics:
            self.analyze()
        
        recommendations = self.generate_ai_recommendations()
        
        report = f"""# Rapport de Qualité des Données

**Généré le** : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 Métriques Globales

| Métrique | Valeur | Seuil |
|----------|--------|-------|
| **Note globale** | **{self.metrics.quality_grade}** | A-B-C = Acceptable |
| Total enregistrements | {self.metrics.total_records} | - |
| Enregistrements valides | {self.metrics.valid_records} | - |
| Complétude | {self.metrics.completeness_score * 100:.1f}% | ≥ 70% |
| Doublons | {self.metrics.duplicates_pct:.1f}% | ≤ 5% |
| Géocodage réussi | {self.metrics.geocoding_success_rate:.1f}% | ≥ 50% |
| Score géocodage moyen | {self.metrics.avg_geocoding_score:.2f} | ≥ 0.5 |

## 📋 Valeurs Manquantes par Colonne

| Colonne | Valeurs nulles | % |
|---------|----------------|---|
"""
        
        for col, count in sorted(self.metrics.null_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / self.metrics.total_records * 100 if self.metrics.total_records > 0 else 0
            report += f"| {col} | {count} | {pct:.1f}% |\n"
        
        report += f"""

## 🤖 Recommandations IA

{recommendations}

## ✅ Conclusion

{"✅ **Dataset acceptable** pour l'analyse." if self.metrics.is_acceptable else "⚠️ **Dataset nécessite des corrections** avant utilisation."}

---
*Rapport généré automatiquement par le pipeline Open Data*
"""
        
        # Sauvegarder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = REPORTS_DIR / f"{output_name}_{timestamp}.md"
        filepath.write_text(report, encoding='utf-8')
        
        print(f"📄 Rapport sauvegardé : {filepath}")
        return filepath
```

### 4.2 Exercice : Analyser la qualité

```python
# Dans un notebook ou script
from pipeline.quality import QualityAnalyzer
import pandas as pd

# Charger vos données
df = pd.read_parquet("data/processed/votre_fichier.parquet")

# Analyser
analyzer = QualityAnalyzer(df)
metrics = analyzer.analyze()

print(f"Note de qualité : {metrics.quality_grade}")
print(f"Acceptable : {'✅ Oui' if metrics.is_acceptable else '❌ Non'}")

# Générer le rapport
report_path = analyzer.generate_report("mon_dataset")
```

---

## Partie 5 : Transformation avancée (45 min)

### 5.1 Module de transformation

Créez `pipeline/transformer.py` :

```python
"""Module de transformation et nettoyage."""
import pandas as pd
import numpy as np
from typing import Callable
from litellm import completion
from dotenv import load_dotenv

from .models import Product

load_dotenv()


class DataTransformer:
    """Transforme et nettoie les données."""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.transformations_applied = []
    
    def remove_duplicates(self, subset: list[str] = None) -> 'DataTransformer':
        """Supprime les doublons."""
        initial = len(self.df)
        
        if subset is None:
            subset = ['code'] if 'code' in self.df.columns else [self.df.columns[0]]
        
        self.df = self.df.drop_duplicates(subset=subset, keep='first')
        removed = initial - len(self.df)
        
        self.transformations_applied.append(f"Doublons supprimés: {removed}")
        return self
    
    def handle_missing_values(
        self, 
        numeric_strategy: str = 'median',
        text_strategy: str = 'unknown'
    ) -> 'DataTransformer':
        """Gère les valeurs manquantes."""
        
        # Colonnes numériques
        num_cols = self.df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            if numeric_strategy == 'median':
                fill_value = self.df[col].median()
            elif numeric_strategy == 'mean':
                fill_value = self.df[col].mean()
            elif numeric_strategy == 'zero':
                fill_value = 0
            else:
                fill_value = None
            
            if fill_value is not None:
                null_count = self.df[col].isnull().sum()
                if null_count > 0:
                    self.df[col] = self.df[col].fillna(fill_value)
                    self.transformations_applied.append(f"{col}: {null_count} nulls → {fill_value:.2f}")
        
        # Colonnes texte
        text_cols = self.df.select_dtypes(include=['object']).columns
        for col in text_cols:
            null_count = self.df[col].isnull().sum()
            if null_count > 0:
                self.df[col] = self.df[col].fillna(text_strategy)
                self.transformations_applied.append(f"{col}: {null_count} nulls → '{text_strategy}'")
        
        return self
    
    def normalize_text_columns(self, columns: list[str] = None) -> 'DataTransformer':
        """Normalise les colonnes texte (strip, lower)."""
        if columns is None:
            columns = self.df.select_dtypes(include=['object']).columns.tolist()
        
        for col in columns:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(str).str.strip().str.lower()
        
        self.transformations_applied.append(f"Normalisation texte: {columns}")
        return self
    
    def filter_outliers(
        self, 
        columns: list[str], 
        method: str = 'iqr',
        threshold: float = 1.5
    ) -> 'DataTransformer':
        """Filtre les outliers."""
        initial = len(self.df)
        
        for col in columns:
            if col not in self.df.columns:
                continue
            
            if method == 'iqr':
                Q1 = self.df[col].quantile(0.25)
                Q3 = self.df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - threshold * IQR
                upper = Q3 + threshold * IQR
                self.df = self.df[(self.df[col] >= lower) & (self.df[col] <= upper)]
            
            elif method == 'zscore':
                mean = self.df[col].mean()
                std = self.df[col].std()
                self.df = self.df[np.abs((self.df[col] - mean) / std) < threshold]
        
        removed = initial - len(self.df)
        self.transformations_applied.append(f"Outliers filtrés ({method}): {removed}")
        return self
    
    def add_derived_columns(self) -> 'DataTransformer':
        """Ajoute des colonnes dérivées."""
        
        # Exemple : catégorie de sucres
        if 'sugars_100g' in self.df.columns:
            self.df['sugar_category'] = pd.cut(
                self.df['sugars_100g'],
                bins=[0, 5, 15, 30, float('inf')],
                labels=['faible', 'modéré', 'élevé', 'très_élevé']
            )
            self.transformations_applied.append("Ajout: sugar_category")
        
        # Exemple : flag géocodé
        if 'geocoding_score' in self.df.columns:
            self.df['is_geocoded'] = self.df['geocoding_score'] >= 0.5
            self.transformations_applied.append("Ajout: is_geocoded")
        
        return self
    
    def generate_ai_transformations(self) -> str:
        """Demande à l'IA des transformations supplémentaires."""
        context = f"""
        Dataset avec {len(self.df)} lignes.
        Colonnes: {list(self.df.columns)}
        Types: {self.df.dtypes.to_dict()}
        
        Transformations déjà appliquées:
        {self.transformations_applied}
        """
        
        response = completion(
            model="gemini/gemini-2.0-flash-exp",
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en data engineering. Génère du code Python pandas exécutable."
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nQuelles transformations supplémentaires recommandes-tu ? Génère le code."
                }
            ]
        )
        
        return response.choices[0].message.content
    
    def apply_custom(self, func: Callable[[pd.DataFrame], pd.DataFrame], name: str) -> 'DataTransformer':
        """Applique une transformation personnalisée."""
        self.df = func(self.df)
        self.transformations_applied.append(f"Custom: {name}")
        return self
    
    def get_result(self) -> pd.DataFrame:
        """Retourne le DataFrame transformé."""
        return self.df
    
    def get_summary(self) -> str:
        """Retourne un résumé des transformations."""
        return "\n".join([f"• {t}" for t in self.transformations_applied])
```

---

## Partie 6 : Orchestration et tests (45 min)

### 6.1 Script principal

Créez `pipeline/main.py` :

```python
#!/usr/bin/env python3
"""Script principal du pipeline."""
import argparse
from datetime import datetime
import pandas as pd

from .fetchers.openfoodfacts import OpenFoodFactsFetcher
from .enricher import DataEnricher
from .transformer import DataTransformer
from .quality import QualityAnalyzer
from .storage import save_raw_json, save_parquet
from .config import MAX_ITEMS


def run_pipeline(
    category: str,
    max_items: int = MAX_ITEMS,
    skip_enrichment: bool = False,
    verbose: bool = True
) -> dict:
    """
    Exécute le pipeline complet.
    
    Args:
        category: Catégorie de produits
        max_items: Nombre max d'items
        skip_enrichment: Passer l'enrichissement (plus rapide)
        verbose: Afficher la progression
    
    Returns:
        Statistiques du pipeline
    """
    stats = {"start_time": datetime.now()}
    
    print("=" * 60)
    print(f"🚀 PIPELINE OPEN DATA - {category.upper()}")
    print("=" * 60)
    
    # === ÉTAPE 1 : Acquisition ===
    print("\n📥 ÉTAPE 1 : Acquisition des données")
    fetcher = OpenFoodFactsFetcher()
    products = list(fetcher.fetch_all(category, max_items, verbose))
    
    if not products:
        print("❌ Aucun produit récupéré. Arrêt.")
        return {"error": "No data fetched"}
    
    save_raw_json(products, f"{category}_raw")
    stats["fetcher"] = fetcher.get_stats()
    
    # === ÉTAPE 2 : Enrichissement ===
    if not skip_enrichment:
        print("\n🌍 ÉTAPE 2 : Enrichissement (géocodage)")
        enricher = DataEnricher()
        
        # Extraire les adresses uniques
        addresses = enricher.extract_addresses(products, "stores")
        
        if addresses:
            # Construire le cache de géocodage
            geo_cache = enricher.build_geocoding_cache(addresses[:100])  # Limiter pour le TP
            
            # Enrichir les produits
            products = enricher.enrich_products(products, geo_cache, "stores")
            stats["enricher"] = enricher.get_stats()
        else:
            print("⚠️ Pas d'adresses à géocoder")
    else:
        print("\n⏭️ ÉTAPE 2 : Enrichissement (ignoré)")
    
    # === ÉTAPE 3 : Transformation ===
    print("\n🔧 ÉTAPE 3 : Transformation et nettoyage")
    df = pd.DataFrame(products)
    
    transformer = DataTransformer(df)
    df_clean = (
        transformer
        .remove_duplicates()
        .handle_missing_values(numeric_strategy='median', text_strategy='unknown')
        .normalize_text_columns(['brands', 'categories'])
        .add_derived_columns()
        .get_result()
    )
    
    print(f"   Résumé des transformations:\n{transformer.get_summary()}")
    stats["transformer"] = {"transformations": transformer.transformations_applied}
    
    # === ÉTAPE 4 : Qualité ===
    print("\n📊 ÉTAPE 4 : Analyse de qualité")
    analyzer = QualityAnalyzer(df_clean)
    metrics = analyzer.analyze()
    
    print(f"   Note: {metrics.quality_grade}")
    print(f"   Complétude: {metrics.completeness_score * 100:.1f}%")
    print(f"   Doublons: {metrics.duplicates_pct:.1f}%")
    
    # Générer le rapport
    analyzer.generate_report(f"{category}_quality")
    stats["quality"] = metrics.dict()
    
    # === ÉTAPE 5 : Stockage ===
    print("\n💾 ÉTAPE 5 : Stockage final")
    output_path = save_parquet(df_clean, category)
    stats["output_path"] = str(output_path)
    
    # === RÉSUMÉ ===
    stats["end_time"] = datetime.now()
    stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).seconds
    
    print("\n" + "=" * 60)
    print("✅ PIPELINE TERMINÉ")
    print("=" * 60)
    print(f"   Durée: {stats['duration_seconds']}s")
    print(f"   Produits: {len(df_clean)}")
    print(f"   Qualité: {metrics.quality_grade}")
    print(f"   Fichier: {output_path}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Pipeline Open Data")
    parser.add_argument("--category", "-c", default="chocolats", help="Catégorie")
    parser.add_argument("--max-items", "-m", type=int, default=MAX_ITEMS, help="Nombre max")
    parser.add_argument("--skip-enrichment", "-s", action="store_true", help="Ignorer l'enrichissement")
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    
    args = parser.parse_args()
    
    run_pipeline(
        category=args.category,
        max_items=args.max_items,
        skip_enrichment=args.skip_enrichment,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
```

### 6.2 Module de stockage

Créez `pipeline/storage.py` :

```python
"""Module de stockage des données."""
import json
import pandas as pd
from datetime import datetime
from pathlib import Path

from .config import RAW_DIR, PROCESSED_DIR


def save_raw_json(data: list[dict], name: str) -> Path:
    """Sauvegarde les données brutes en JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = RAW_DIR / f"{name}_{timestamp}.json"
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    size_kb = filepath.stat().st_size / 1024
    print(f"   💾 Brut: {filepath.name} ({size_kb:.1f} KB)")
    
    return filepath


def save_parquet(df: pd.DataFrame, name: str) -> Path:
    """Sauvegarde le DataFrame en Parquet."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = PROCESSED_DIR / f"{name}_{timestamp}.parquet"
    
    df.to_parquet(filepath, index=False, compression="snappy")
    
    size_kb = filepath.stat().st_size / 1024
    print(f"   💾 Parquet: {filepath.name} ({size_kb:.1f} KB)")
    
    return filepath


def load_parquet(filepath: str | Path) -> pd.DataFrame:
    """Charge un fichier Parquet."""
    return pd.read_parquet(filepath)
```

### 6.3 Tests unitaires (OBLIGATOIRES)

Créez `tests/test_fetchers.py` :

```python
"""Tests pour les fetchers."""
import pytest
from pipeline.fetchers.openfoodfacts import OpenFoodFactsFetcher
from pipeline.fetchers.adresse import AdresseFetcher


class TestOpenFoodFactsFetcher:
    """Tests pour OpenFoodFactsFetcher."""
    
    def test_fetch_batch_returns_list(self):
        """Test que fetch_batch retourne une liste."""
        fetcher = OpenFoodFactsFetcher()
        result = fetcher.fetch_batch("chocolats", page=1, page_size=5)
        
        assert isinstance(result, list)
        assert len(result) <= 5
    
    def test_fetch_batch_has_required_fields(self):
        """Test que les produits ont les champs requis."""
        fetcher = OpenFoodFactsFetcher()
        products = fetcher.fetch_batch("chocolats", page=1, page_size=3)
        
        if products:
            product = products[0]
            assert "code" in product


class TestAdresseFetcher:
    """Tests pour AdresseFetcher."""
    
    def test_geocode_single_valid_address(self):
        """Test le géocodage d'une adresse valide."""
        fetcher = AdresseFetcher()
        result = fetcher.geocode_single("20 avenue de ségur paris")
        
        assert result.original_address == "20 avenue de ségur paris"
        assert result.score > 0.5
        assert result.latitude is not None
        assert result.longitude is not None
    
    def test_geocode_single_invalid_address(self):
        """Test le géocodage d'une adresse invalide."""
        fetcher = AdresseFetcher()
        result = fetcher.geocode_single("xyzabc123456")
        
        assert result.score < 0.5 or result.latitude is None
    
    def test_geocode_empty_address(self):
        """Test le géocodage d'une adresse vide."""
        fetcher = AdresseFetcher()
        result = fetcher.geocode_single("")
        
        assert result.score == 0
```

Créez `tests/test_transformer.py` :

```python
"""Tests pour le transformer."""
import pytest
import pandas as pd
import numpy as np
from pipeline.transformer import DataTransformer


class TestDataTransformer:
    """Tests pour DataTransformer."""
    
    @pytest.fixture
    def sample_df(self):
        """DataFrame de test."""
        return pd.DataFrame({
            'code': ['001', '002', '001', '003'],
            'name': ['  Test  ', None, 'Test', 'Other'],
            'value': [10.0, None, 10.0, 100.0],
        })
    
    def test_remove_duplicates(self, sample_df):
        """Test la suppression des doublons."""
        transformer = DataTransformer(sample_df)
        result = transformer.remove_duplicates(['code']).get_result()
        
        assert len(result) == 3
        assert result['code'].nunique() == 3
    
    def test_handle_missing_values_median(self, sample_df):
        """Test le remplacement par la médiane."""
        transformer = DataTransformer(sample_df)
        result = transformer.handle_missing_values(numeric_strategy='median').get_result()
        
        assert result['value'].isnull().sum() == 0
    
    def test_normalize_text(self, sample_df):
        """Test la normalisation du texte."""
        transformer = DataTransformer(sample_df)
        result = transformer.normalize_text_columns(['name']).get_result()
        
        # Vérifie que les espaces sont supprimés et en minuscules
        assert 'test' in result['name'].values
    
    def test_chaining(self, sample_df):
        """Test le chaînage des transformations."""
        transformer = DataTransformer(sample_df)
        result = (
            transformer
            .remove_duplicates()
            .handle_missing_values()
            .get_result()
        )
        
        assert len(transformer.transformations_applied) >= 2
```

### 6.4 Exécution des tests

```bash
# Exécuter tous les tests
uv run pytest tests/ -v

# Avec couverture
uv run pytest tests/ -v --cov=pipeline --cov-report=html
```

---

## Livrables attendus

📁 **Structure du rendu :**

```
tp2-pipeline/
├── .env
├── .gitignore
├── pyproject.toml
├── README.md                    # Documentation complète
├── pipeline/
│   ├── __init__.py
│   ├── config.py               # Configuration centralisée
│   ├── models.py               # Modèles Pydantic
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── openfoodfacts.py    # OU votre API
│   │   └── adresse.py
│   ├── enricher.py             # Enrichissement croisé
│   ├── transformer.py          # Transformations
│   ├── quality.py              # Scoring et rapport
│   ├── storage.py              # Stockage Parquet
│   └── main.py                 # Orchestration
├── tests/
│   ├── __init__.py
│   ├── test_fetchers.py
│   └── test_transformer.py
├── data/
│   ├── raw/                    # Données brutes JSON
│   ├── processed/              # Données Parquet
│   └── reports/                # Rapports de qualité
└── notebooks/
    └── exploration.ipynb       # Notebook d'exploration (optionnel)
```

---

## Critères d'évaluation

| Critère | Points | Description |
|---------|--------|-------------|
| **Architecture pipeline** | /3 | Structure modulaire, config centralisée, modèles Pydantic |
| **Acquisition multi-sources** | /3 | Fetchers fonctionnels, retry, pagination, rate limiting |
| **Enrichissement** | /2 | Croisement de données effectif entre 2 APIs |
| **Transformation** | /2 | Nettoyage pertinent, chaînable, outliers gérés |
| **Qualité & Rapport** | /2 | Scoring automatique, rapport Markdown généré |
| **Tests unitaires** | /2 | Au moins 5 tests passants (pytest) |
| **Documentation** | /1 | README clair, code commenté |
| **Total** | **/15** | |

---

## Bonus

| Bonus | Points | Description |
|-------|--------|-------------|
| Pipeline incrémental | +1 | Détection des nouveaux enregistrements uniquement |
| Logs structurés | +1 | Module `logging` avec niveaux et fichier |
| CI/CD | +1 | GitHub Actions pour exécuter les tests |
| Dashboard métriques | +1 | Visualisation Streamlit du rapport de qualité |

---

## Conseils

1. **Commencez simple** : Faites fonctionner l'acquisition avant d'ajouter l'enrichissement
2. **Testez souvent** : Exécutez `pytest` régulièrement pendant le développement
3. **Utilisez l'IA** : Demandez à l'assistant de générer du code de transformation
4. **Documentez au fur et à mesure** : N'attendez pas la fin pour le README
5. **Gérez les erreurs** : Prévoyez les cas où l'API ne répond pas
