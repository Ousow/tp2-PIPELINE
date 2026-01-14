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
        model="ollama/mistral", 
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un expert en data cleaning. "
                    "Génère du code Python Pandas exécutable directement. "
                    "Inclus : gestion des valeurs manquantes, types, normalisation."
                )
            },
            {
                "role": "user",
                "content": f"{context}\n\nGénère le code de nettoyage complet."
            }
        ],
        temperature=0.2,
        api_base="http://localhost:11434" 
    )

    return response.choices[0].message.content

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoyage avec intégration des transformations pertinentes
    proposées par l'IA (valeurs manquantes, normalisation, encodage).
    """
    df_clean = df.copy()

    # 1. Suppression des doublons
    initial_count = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    print(f"Doublons supprimés : {initial_count - len(df_clean)}")

    # Séparation des types
    text_cols = df_clean.select_dtypes(include=["object"]).columns
    num_cols = df_clean.select_dtypes(include=["number"]).columns

    # 2. Gestion des valeurs manquantes
    if len(text_cols) > 0:
        df_clean[text_cols] = df_clean[text_cols].fillna("non renseigné")

    for col in num_cols:
        df_clean[col] = df_clean[col].fillna(df_clean[col].median())

    # 3. Normalisation des textes
    for col in text_cols:
        df_clean[col] = (
            df_clean[col]
            .astype(str)
            .str.strip()
            .str.lower()
        )

    # 4. Normalisation des variables numériques (z-score)
    if len(num_cols) > 0:
        df_clean[num_cols] = (
            df_clean[num_cols] - df_clean[num_cols].mean()
        ) / df_clean[num_cols].std()

    # 5. Encodage des variables catégorielles (One-Hot Encoding pandas)
    if len(text_cols) > 0:
        df_clean = pd.get_dummies(
            df_clean,
            columns=text_cols,
            drop_first=True
        )

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