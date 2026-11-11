from __future__ import annotations

DMV_ZIPS = {
    "20001": ("Washington", "DC", 38.9101, -77.0171),
    "20002": ("Washington", "DC", 38.9047, -76.9786),
    "20003": ("Washington", "DC", 38.8876, -76.9901),
    "20007": ("Washington", "DC", 38.9146, -77.0730),
    "20910": ("Silver Spring", "MD", 38.9981, -77.0318),
    "20814": ("Bethesda", "MD", 38.9897, -77.1003),
    "20850": ("Rockville", "MD", 39.0918, -77.1812),
    "20742": ("College Park", "MD", 38.9869, -76.9426),
    "20770": ("Greenbelt", "MD", 39.0046, -76.8755),
    "21401": ("Annapolis", "MD", 38.9784, -76.4922),
    "22201": ("Arlington", "VA", 38.8871, -77.0932),
    "22314": ("Alexandria", "VA", 38.8048, -77.0469),
    "22102": ("McLean", "VA", 38.9339, -77.1773),
    "22030": ("Fairfax", "VA", 38.8462, -77.3064),
    "20190": ("Reston", "VA", 38.9586, -77.3570),
    "20170": ("Herndon", "VA", 38.9695, -77.3861),
}

CITY_COORDS = {
    "washington dc": (38.9072, -77.0369),
    "silver spring md": (38.9907, -77.0261),
    "bethesda md": (38.9847, -77.0947),
    "rockville md": (39.0840, -77.1528),
    "college park md": (38.9897, -76.9378),
    "greenbelt md": (39.0046, -76.8755),
    "annapolis md": (38.9784, -76.4922),
    "arlington va": (38.8797, -77.1068),
    "alexandria va": (38.8048, -77.0469),
    "mclean va": (38.9339, -77.1773),
    "fairfax va": (38.8462, -77.3064),
    "reston va": (38.9586, -77.3570),
    "herndon va": (38.9695, -77.3861),
}


def reviewed_stored_pin(city, state, zip_code, lat, lng) -> tuple[float | None, float | None]:
    # Match the same canonical state, ZIP and ASCII city rules as the SQL viewport filter.
    if state not in ("DC", "MD", "VA") or lat is None or lng is None:
        return None, None
    known_zip = DMV_ZIPS.get(zip_code) if isinstance(zip_code, str) else None
    if known_zip and known_zip[1] == state and (lat, lng) == known_zip[2:]:
        return known_zip[2], known_zip[3]
    if isinstance(city, str) and city.isascii():
        city_pin = CITY_COORDS.get(f"{city.lower()} {state.lower()}")
        if city_pin == (lat, lng):
            return city_pin
    return None, None
