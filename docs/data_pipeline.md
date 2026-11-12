# Phase 2: Agricultural Data Pipeline Documentation

This document describes the data sources, ingestion pipeline, leave-one-year-out baseline methodology, and parametric tier mapping for the hardware-free blockchain crop-insurance research prototype.

---

## 1. Data Sources & Official Documentation Citations

| Data Stream | Primary Provider / Collection | Resolution | Temporal Window | Official Documentation URL |
| :--- | :--- | :--- | :--- | :--- |
| **Rainfall & Temperature** | Open-Meteo Historical Archive API (ERA5-Land reanalysis) | ~9 km (0.1°) | Daily (153 days / season) | [Open-Meteo Archive Docs](https://open-meteo.com/en/docs/historical-weather-api) |
| **Canopy NDVI** | Copernicus Sentinel-2 MSI Level-2A (`COPERNICUS/S2_SR_HARMONIZED`) | 10 m (B8, B4) | 5-day revisit (cloud masked) | [Sentinel-2 GEE Catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED) |
| **Soil Moisture** | NASA-USDA Enhanced SMAP Global Soil Moisture (`NASA_USDA/HSL/SMAP_soil_moisture`) | ~9 km grid | 3-day composite | [NASA SMAP GEE Catalog](https://developers.google.com/earth-engine/datasets/catalog/NASA_USDA_HSL_SMAP_soil_moisture) |

---

## 2. Geographic Target Scope & Coordinates

Target Region: Rayalaseema agricultural belt, Andhra Pradesh, India.
Primary Crop: Kharif Rainfed Groundnut (*Arachis hypogaea*).
Agricultural Season: Kharif (1 June to 31 October inclusive; 153 days).

| District | Center Latitude | Center Longitude | Parcel Bounding Box | Soil Characteristics |
| :--- | :--- | :--- | :--- | :--- |
| **Anantapur** | 14.68000° N | 77.60000° E | 2 km × 2 km polygon | Red sandy loam (alfisols), high drought risk |
| **Kurnool** | 15.83000° N | 78.04000° E | 2 km × 2 km polygon | Mixed red and black soils (vertisols) |
| **Kadapa** | 14.47000° N | 78.82000° E | 2 km × 2 km polygon | Red-loamy valley soils |

Bounding box formula for $2\text{ km}$ box ($\Delta\text{lat} = \frac{1}{111}\text{ deg}$, $\Delta\text{lon} = \frac{1}{111 \cdot \cos(\text{lat})}\text{ deg}$).

---

## 3. Data Processing & Methodology

### 3.1 Seasonal Weather Aggregation (Open-Meteo)
- Daily cumulative precipitation is extracted across the 153-day Kharif window.
- Quality validation rejects negative values and confirms observation completeness:
  $$\text{Rainfall}_{\text{seasonal}} = \sum_{t=\text{June 1}}^{\text{October 31}} P_t \quad (\text{mm})$$
- Raw daily responses are persistently cached in `data/raw/weather_{district}_{year}.json` to prevent redundant network requests.

### 3.2 Satellite NDVI Calculation & Cloud Masking (Sentinel-2)
- **Bands**: Band 8 (Near-Infrared, $842\text{ nm}$) and Band 4 (Red, $665\text{ nm}$).
- **Per-pixel cloud masking**: QA60 bitmask (bit 10 = opaque clouds, bit 11 = cirrus).
- **Index**:
  $$\text{NDVI} = \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4}}$$
- **Seasonal Metric**: Peak composite ($\max(\text{NDVI})$) during peak vegetative / flowering stage.
- **Fallback**: Level-1C Top-of-Atmosphere (`COPERNICUS/S2_HARMONIZED`) if Level-2A surface reflectance is absent.

### 3.3 Root-Zone / Surface Soil Moisture (NASA SMAP)
- Parameter: Surface Soil Moisture (`ssm`, in mm).
- **Resolution Limit**: The nominal spatial resolution of NASA SMAP is approximately $9\text{ km}$. The $2\text{ km}$ cadastral boundary samples the enclosing $9\text{ km}$ grid cell intersection.
- **Seasonal Metric**: Mean surface soil moisture across the Kharif growing cycle.

---

## 4. Leave-One-Year-Out Historical Baseline Methodology

To avoid future-data or current-season data leakage, baselines are computed dynamically using a **leave-one-year-out** window:

$$\text{Baseline}(D, Y) = \text{Median}\left(\{ X(D, y) \mid y \in \mathcal{Y}, y \neq Y \}\right)$$

Where $\mathcal{Y} = \{2017, 2018, \dots, 2024\}$.

### Percentage Deficit Formulation:
$$\text{Deficit}_{\%} = \max\left(0.0, \frac{\text{Baseline} - \text{Observed}}{\text{Baseline}} \times 100.0\right)$$
- If observed moisture or rainfall exceeds the baseline, deficit is clamped to $0.0\%$ (normal / favorable conditions).

---

## 5. Parametric Severity Tiers & Smart Contract Parity

Threshold cut-offs are configured in [`config/tier_rules.json`](../config/tier_rules.json) as versioned research assumptions:

| Severity Tier | Payout % | Rainfall Deficit Cut-off | Satellite NDVI Deficit | Soil Moisture Deficit | Agronomic Interpretation |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **Tier 0** | **0%** | $\le 20.0\%$ | $\le 15.0\%$ | $\le 15.0\%$ | Normal / Mild variation; no yield-crushing drought |
| **Tier 1** | **25%** | $20.01\% - 40.0\%$ | $15.01\% - 30.0\%$ | $15.01\% - 30.0\%$ | Moderate moisture deficit; canopy stunting |
| **Tier 2** | **50%** | $40.01\% - 60.0\%$ | $30.01\% - 45.0\%$ | $30.01\% - 45.0\%$ | Severe drought; significant yield reduction |
| **Tier 3** | **100%** | $> 60.0\%$ | $> 45.0\%$ | $> 45.0\%$ | Catastrophic failure; total crop desiccation |

### Multi-Source 2-of-3 Oracle Consensus Logic:
1. **Any 2 Match**: If any 2 of the 3 independent oracles report the same tier, that tier is adopted immediately.
2. **All 3 Differ**: If all 3 sources report different tiers (e.g. Weather = Tier 2, Satellite = Tier 1, Soil = Tier 3), the **median tier** (Tier 2) is chosen.
3. **Fewer Than 2 Reports / Conflicting Pair**: Settlement pauses and waits for the 3rd oracle report.

---

## 6. Execution & Verification Instructions

### Run Ingestion Pipeline:
```powershell
.\.venv\Scripts\python build_dataset.py
```

### Run Pipeline Unit Tests:
```powershell
.\.venv\Scripts\python -m unittest test/test_data_pipeline.py
```

### Run Flake8 Linter:
```powershell
.\.venv\Scripts\flake8 oracles/ build_dataset.py test/test_data_pipeline.py
```

---

## 7. Dataset Limitations & Academic Notice

1. **Spatial Resolution**: NASA SMAP (~9 km grid) and ERA5-Land (~9 km grid) are coarser than individual smallholder plot sizes ($0.5 - 2\text{ ha}$). They serve as regional parametric drought proxies rather than micro-plot yield guarantees.
2. **Earth Engine Credentials**: Live Google Earth Engine API extraction requires an authenticated GCP project. When credentials are not provided in `.env`, the pipeline utilizes documented benchmark observations (`data_status: "CACHED_BENCHMARK_FALLBACK"`), clearly identifying fallback data rather than claiming live GEE extraction succeeded.
3. **Basis Risk**: Discrepancies between meteorological deficit and ground yield constitute parametric basis risk, addressed by our 2-of-3 multi-source consensus.
