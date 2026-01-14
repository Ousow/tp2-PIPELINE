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