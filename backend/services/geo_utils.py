import math
from typing import Dict, Tuple


TELANGANA_CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "hyderabad": (17.3850, 78.4867),
    "secunderabad": (17.4399, 78.4983),
    "warangal": (17.9689, 79.5941),
    "hanamkonda": (18.0077, 79.5585),
    "nizamabad": (18.6725, 78.0941),
    "karimnagar": (18.4386, 79.1288),
    "khammam": (17.2473, 80.1514),
    "nalgonda": (17.0575, 79.2684),
    "mahbubnagar": (16.7488, 78.0035),
    "suryapet": (17.1400, 79.6200),
    "adilabad": (19.6756, 78.5339),
    "jagtial": (18.7947, 78.9166),
    "sangareddy": (17.6289, 78.0820),
    "medak": (18.0450, 78.2600),
    "rangareddy": (17.3000, 78.2000),
    "nagarkurnool": (16.4821, 78.3247),
    "mulugu": (18.1930, 79.9410),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the distance between two coordinates in km."""
    earth_radius_km = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return earth_radius_km * c


def infer_tel_city_from_text(text: str) -> str:
    text_l = (text or "").lower()
    for city in TELANGANA_CITY_COORDS:
        if city in text_l:
            return city
    return "hyderabad"


def infer_telangana_anchor(text: str) -> Tuple[float, float]:
    city = infer_tel_city_from_text(text)
    return TELANGANA_CITY_COORDS[city]

