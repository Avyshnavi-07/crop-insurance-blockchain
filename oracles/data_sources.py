"""
Data sources module for hardware-free crop-insurance prototype.

Sources & Citations:
1. Rainfall & Temperature:
   Open-Meteo Historical Weather Archive API
   Docs: https://open-meteo.com/en/docs/historical-weather-api
   ERA5-Land reanalysis, 0.1 degree (~9 km) spatial resolution.

2. Satellite NDVI:
   Copernicus Sentinel-2 MSI Level-2A (Surface Reflectance Harmonized) via Google Earth Engine.
   Docs: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
   Bands: B8 (NIR, 842 nm, 10m), B4 (Red, 665 nm, 10m), QA60 / SCL (per-pixel cloud masking).
   Fallback: COPERNICUS/S2_HARMONIZED (Level-1C TOA) if SR is unavailable.

3. Soil Moisture:
   NASA-USDA Enhanced SMAP Global Soil Moisture Data via Google Earth Engine.
   Docs: https://developers.google.com/earth-engine/datasets/catalog/NASA_USDA_HSL_SMAP_soil_moisture
   Alternative: NASA/SMAP/SPL4SMGP/007 (SMAP L4 9 km Global Surface and Root Zone Soil Moisture).
   Resolution Limit: ~9 km spatial resolution. The 2 km agricultural parcel polygon
   samples within the enclosing SMAP 9 km grid cell.
"""

import json
import math
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests

# Geographic coordinates for Andhra Pradesh districts (Kharif groundnut belt)
# Bounding box is centered around primary agricultural parcel coordinates
DISTRICT_COORDINATES = {
    "Anantapur": {"lat": 14.68, "lon": 77.60},
    "Kurnool": {"lat": 15.83, "lon": 78.04},
    "Kadapa": {"lat": 14.47, "lon": 78.82},
}

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Expected observation days in Kharif season (1 June to 31 October inclusive)
EXPECTED_KHARIF_DAYS = 153


def get_bounding_box(
    lat: float, lon: float, box_size_km: float = 2.0
) -> Tuple[float, float, float, float]:
    """
    Computes bounding box (min_lat, min_lon, max_lat, max_lon) for a center point.
    1 degree of latitude is approximately 111 km.
    1 degree of longitude is approximately 111 * cos(lat) km.
    """
    half_box = box_size_km / 2.0
    lat_delta = half_box / 111.0
    lon_delta = half_box / (111.0 * math.cos(math.radians(lat)))
    return (
        round(lat - lat_delta, 5),
        round(lon - lon_delta, 5),
        round(lat + lat_delta, 5),
        round(lon + lon_delta, 5),
    )


# =============================================================================
# 1. Weather / Rainfall (Open-Meteo Historical Archive API)
# =============================================================================
def fetch_seasonal_rainfall(district: str, year: int) -> Dict:
    """
    Fetches seasonal cumulative rainfall (1 June - 31 October) from Open-Meteo Archive API.
    Caches raw response in data/raw/weather_{district}_{year}.json to prevent duplicate API hits.
    """
    if district not in DISTRICT_COORDINATES:
        raise ValueError(f"Unknown district: '{district}'. Allowed: {list(DISTRICT_COORDINATES.keys())}")
    if year < 1940 or year > 2030:
        raise ValueError(f"Invalid year: {year}")

    cache_file = RAW_DATA_DIR / f"weather_{district.lower()}_{year}.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)

    coords = DISTRICT_COORDINATES[district]
    start_date = f"{year}-06-01"
    end_date = f"{year}-10-31"

    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={coords['lat']}&longitude={coords['lon']}&"
        f"start_date={start_date}&end_date={end_date}&"
        f"daily=precipitation_sum,temperature_2m_max,temperature_2m_mean&"
        f"timezone=auto"
    )

    try:
        response = requests.get(url, timeout=30)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Network error querying Open-Meteo archive for {district} {year}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Open-Meteo API request failed for {district} {year} with status {response.status_code}: {response.text}"
        )

    data = response.json()
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)

    return data


def validate_weather_data(raw_weather_data: Dict) -> Dict:
    """
    Validates daily weather data structure, date completeness, and value sanity.
    Returns validation report dictionary.
    """
    daily = raw_weather_data.get("daily", {})
    times = daily.get("time", [])
    precip = daily.get("precipitation_sum", [])

    total_days = len(times)
    valid_precip = [p for p in precip if p is not None]
    negative_values = [p for p in valid_precip if p < 0]

    is_valid = (
        total_days == EXPECTED_KHARIF_DAYS
        and len(valid_precip) == total_days
        and len(negative_values) == 0
    )

    return {
        "is_valid": is_valid,
        "total_days": total_days,
        "valid_precip_count": len(valid_precip),
        "negative_count": len(negative_values),
        "start_date": times[0] if times else None,
        "end_date": times[-1] if times else None,
    }


def extract_cumulative_rainfall(raw_weather_data: Dict) -> Optional[float]:
    """
    Calculates total cumulative seasonal precipitation in mm from Open-Meteo daily response.
    Returns None if precipitation data is missing or empty.
    """
    daily = raw_weather_data.get("daily", {})
    precipitation_list = daily.get("precipitation_sum", [])
    if not precipitation_list:
        return None

    valid_precip = [p for p in precipitation_list if p is not None and p >= 0]
    if not valid_precip:
        return None

    return round(sum(valid_precip), 2)


# =============================================================================
# 2. Satellite NDVI (Sentinel-2 via Google Earth Engine)
# =============================================================================
def init_earth_engine(project_id: Optional[str] = None):
    """
    Initializes Earth Engine client with optional Google Cloud Project ID.
    Raises RuntimeError if Earth Engine credentials are not found.
    """
    import ee

    try:
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
    except Exception as exc:
        raise RuntimeError(
            f"Google Earth Engine initialization failed: {exc}. "
            "Please run 'earthengine authenticate' or provide a valid EE_PROJECT_ID in .env."
        ) from exc


def fetch_sentinel2_ndvi(district: str, year: int, project_id: Optional[str] = None) -> Dict:
    """
    Extracts seasonal NDVI for a 2 km polygon from Sentinel-2 Surface Reflectance (COPERNICUS/S2_SR_HARMONIZED).
    Uses per-pixel cloud masking via QA60 band (bits 10 opaque cloud, 11 cirrus).
    Falls back to Level-1C (COPERNICUS/S2_HARMONIZED) if SR coverage is missing.
    Caches raw stats in data/raw/satellite_{district}_{year}.json.
    """
    if district not in DISTRICT_COORDINATES:
        raise ValueError(f"Unknown district: '{district}'")

    cache_file = RAW_DATA_DIR / f"satellite_{district.lower()}_{year}.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)

    init_earth_engine(project_id)
    import ee

    coords = DISTRICT_COORDINATES[district]
    min_lat, min_lon, max_lat, max_lon = get_bounding_box(coords["lat"], coords["lon"], box_size_km=2.0)
    region = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])

    start_date = f"{year}-06-01"
    end_date = f"{year}-10-31"

    def mask_s2_clouds(image):
        qa = image.select("QA60")
        cloud_bit_mask = 1 << 10
        cirrus_bit_mask = 1 << 11
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
        return image.updateMask(mask).divide(10000)

    # Primary: Surface Reflectance Harmonized
    collection_name = "COPERNICUS/S2_SR_HARMONIZED"
    s2 = (
        ee.ImageCollection(collection_name)
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .map(mask_s2_clouds)
    )

    image_count = s2.size().getInfo()

    # Fallback to Level-1C if SR collection has 0 images
    if image_count == 0:
        collection_name = "COPERNICUS/S2_HARMONIZED"
        s2 = (
            ee.ImageCollection(collection_name)
            .filterBounds(region)
            .filterDate(start_date, end_date)
            .map(mask_s2_clouds)
        )
        image_count = s2.size().getInfo()

    if image_count == 0:
        result = {
            "district": district,
            "year": year,
            "collection": collection_name,
            "image_count": 0,
            "peak_ndvi": None,
            "mean_ndvi": None,
            "status": "NO_CLEAR_IMAGES",
            "data_status": "REAL_API",
        }
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)
        return result

    # Compute NDVI: (B8 - B4) / (B8 + B4)
    def add_ndvi(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return img.addBands(ndvi)

    s2_ndvi = s2.map(add_ndvi).select("NDVI")

    # Max/Peak NDVI composite over season (standard agricultural drought metric)
    peak_composite = s2_ndvi.max()
    stats = peak_composite.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=10,
        maxPixels=1e6,
    ).getInfo()

    peak_ndvi = stats.get("NDVI")
    result = {
        "district": district,
        "year": year,
        "collection": collection_name,
        "image_count": image_count,
        "peak_ndvi": round(peak_ndvi, 4) if peak_ndvi is not None else None,
        "status": "SUCCESS" if peak_ndvi is not None else "NO_DATA",
        "data_status": "REAL_API",
    }

    with open(cache_file, "w") as f:
        json.dump(result, f, indent=2)

    return result


# =============================================================================
# 3. NASA SMAP Soil Moisture (via Google Earth Engine)
# =============================================================================
def fetch_smap_soil_moisture(district: str, year: int, project_id: Optional[str] = None) -> Dict:
    """
    Extracts seasonal mean surface soil moisture from NASA-USDA SMAP.
    Dataset: NASA_USDA/HSL/SMAP_soil_moisture
    Resolution Limit: ~9 km grid. 2 km farm box samples the encompassing grid cell.
    Caches raw stats in data/raw/soil_{district}_{year}.json.
    """
    if district not in DISTRICT_COORDINATES:
        raise ValueError(f"Unknown district: '{district}'")

    cache_file = RAW_DATA_DIR / f"soil_{district.lower()}_{year}.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)

    init_earth_engine(project_id)
    import ee

    coords = DISTRICT_COORDINATES[district]
    min_lat, min_lon, max_lat, max_lon = get_bounding_box(coords["lat"], coords["lon"], box_size_km=2.0)
    region = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])

    start_date = f"{year}-06-01"
    end_date = f"{year}-10-31"

    collection_name = "NASA_USDA/HSL/SMAP_soil_moisture"
    smap = (
        ee.ImageCollection(collection_name)
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .select(["ssm", "smp"])  # ssm: surface soil moisture (mm), smp: soil moisture percentile
    )

    image_count = smap.size().getInfo()
    if image_count == 0:
        result = {
            "district": district,
            "year": year,
            "collection": collection_name,
            "image_count": 0,
            "mean_surface_soil_moisture": None,
            "status": "NO_DATA",
            "data_status": "REAL_API",
        }
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)
        return result

    mean_composite = smap.select("ssm").mean()
    stats = mean_composite.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=1000,
        maxPixels=1e6,
    ).getInfo()

    mean_ssm = stats.get("ssm")
    result = {
        "district": district,
        "year": year,
        "collection": collection_name,
        "image_count": image_count,
        "mean_surface_soil_moisture": round(mean_ssm, 3) if mean_ssm is not None else None,
        "resolution_note": "NASA SMAP nominal resolution is ~9 km. Spatial bounding box samples grid intersection.",
        "status": "SUCCESS" if mean_ssm is not None else "NO_DATA",
        "data_status": "REAL_API",
    }

    with open(cache_file, "w") as f:
        json.dump(result, f, indent=2)

    return result
