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