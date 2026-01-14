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


def save_raw_parquet(df_raw: pd.DataFrame, name: str) -> str:
    """Sauvegarde les données brutes en Parquet."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = RAW_DIR / f"{name}_{timestamp}.parquet"
    
    df_raw.to_parquet(filepath, index=False, compression="snappy")
    
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"Données brutes sauvegardées : {filepath} ({size_mb:.2f} MB)")
    return str(filepath)


def save_clean_parquet(df_clean: pd.DataFrame, name: str) -> str:
    """Sauvegarde les données nettoyées en Parquet."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = PROCESSED_DIR / f"{name}_{timestamp}.parquet"
    
    df_clean.to_parquet(filepath, index=False, compression="snappy")
    
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"Données nettoyées sauvegardées : {filepath} ({size_mb:.2f} MB)")
    return str(filepath)


def load_parquet(filepath: str) -> pd.DataFrame:
    """Charge un fichier Parquet."""
    return pd.read_parquet(filepath)


if __name__ == "__main__":
    # Test
    test_data = [
        {"name": "raw1", "value": 10},
        {"name": "raw2", "value": None}
    ]
    import pandas as pd

    # DF brut
    df_raw = pd.DataFrame(test_data)
    save_raw_parquet(df_raw, "chocolats_raw")
    
    # DF nettoyé (exemple)
    df_clean = df_raw.fillna(0)
    save_clean_parquet(df_clean, "chocolats_clean")
    
    # Chargement test
    loaded = load_parquet(PROCESSED_DIR / "chocolats_clean_*.parquet")
    print(loaded)
