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
