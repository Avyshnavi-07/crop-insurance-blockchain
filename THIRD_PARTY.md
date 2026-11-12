# Third-Party Software and Data Attribution

This repository incorporates open-source software libraries and public earth observation / meteorological datasets. Below are the licenses, attribution requirements, and terms of use.

---

## 1. Third-Party Software Dependencies

| Component | Repository / Package | License | Copyright / Notice |
|---|---|---|---|
| **OpenZeppelin Contracts** | `@openzeppelin/contracts` (v5.1.0) | MIT | Copyright (c) 2016-2024 OpenZeppelin |
| **Hardhat Toolchain** | `hardhat` (v2.29.1) | MIT | Copyright (c) 2019-2024 Nomic Foundation |
| **Ethers.js** | `ethers` (v6.14.0) | MIT | Copyright (c) 2023 Richard Moore |
| **Web3.py** | `web3` (v6.20.3) | MIT | Copyright (c) 2016-2024 Ethereum Foundation |
| **Scikit-learn** | `scikit-learn` (v1.5.2) | BSD 3-Clause | Copyright (c) 2007-2024 scikit-learn developers |
| **Pandas** | `pandas` (v2.2.3) | BSD 3-Clause | Copyright (c) 2008-2024 NumFOCUS / pandas developers |
| **NumPy** | `numpy` (v1.26.4) | BSD 3-Clause | Copyright (c) 2005-2024 NumPy Developers |
| **Matplotlib** | `matplotlib` (v3.9.2) | PSF-compatible | Copyright (c) 2002-2024 Matplotlib Development Team |
| **React & React-DOM** | `react`, `react-dom` (v18.3.1) | MIT | Copyright (c) Meta Platforms, Inc. and affiliates |
| **Vite** | `vite` (v5.4.10) | MIT | Copyright (c) 2019-present Evan You & Vite Contributors |
| **Vitest** | `vitest` (v2.1.4) | MIT | Copyright (c) 2021-present Vitest Team |

---

## 2. Public Data Sources & Attribution

All remote-sensing and weather streams used in this research prototype are public, non-commercial research datasets. The cached extracts in `data/processed/` and `data/raw/` are provided strictly for academic reproducibility under their respective open data terms:

### A. Open-Meteo Historical Weather API / ERA5-Land Reanalysis
- **Provider**: Open-Meteo / European Centre for Medium-Range Weather Forecasts (ECMWF) / Copernicus Climate Change Service (C3S).
- **License / Terms**:
  - ERA5-Land data is governed by the [Licence to use Copernicus Products](https://cds.climate.copernicus.eu/api/v2/terms/static/licence-to-use-copernicus-products.pdf): worldwide, free, non-exclusive, royalty-free access with mandatory attribution.
  - Open-Meteo API is open-access for non-commercial research under Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Mandatory Attribution**:
  - *"Contains modified Copernicus Climate Change Service information [2017-2024]"*.
  - *"Weather data supplied by Open-Meteo.com under CC BY 4.0"*.
- **Redistribution Terms**: Academic caching and redistribution of aggregated daily precipitation extracts are fully permitted.

### B. Copernicus Sentinel-2 MSI Surface Reflectance
- **Provider**: European Space Agency (ESA) / European Commission Copernicus Programme.
- **Collection**: `COPERNICUS/S2_SR_HARMONIZED` via Google Earth Engine.
- **License / Terms**:
  - Governed by the [Copernicus Open Access Policy](https://sentinels.copernicus.eu/web/sentinel/terms-conditions) (Regulation (EU) No 377/2014). Free, full, and open access for all users.
- **Mandatory Attribution**:
  - *"Contains modified Copernicus Sentinel data [2017-2024]"*.
- **Redistribution Terms**: The cached seasonal NDVI statistics represent derived scientific indicators from open Copernicus Sentinel data and are freely redistributable for research.

### C. NASA-USDA Enhanced SMAP Global Soil Moisture
- **Provider**: National Aeronautics and Space Administration (NASA) / United States Department of Agriculture (USDA) / Jet Propulsion Laboratory (JPL).
- **Collection**: `NASA_USDA/HSL/SMAP_soil_moisture` via Google Earth Engine.
- **License / Terms**:
  - Governed by the [NASA Open Data Policy](https://www.nasa.gov/open/data.html). NASA data is in the public domain (US Government Work under 17 U.S.C. § 105).
- **Mandatory Attribution**:
  - *"NASA-USDA Enhanced SMAP Global Soil Moisture data courtesy of NASA/JPL-Caltech and USDA-ARS"*.
- **Redistribution Terms**: No restrictions on reproduction, distribution, or research adaptation.

---

## 3. Scope of Repository License

The MIT License in [`LICENSE`](LICENSE) applies exclusively to the original software code, smart contracts, scripts, and documentation created for the Crop Insurance Chain research prototype. It does not alter, replace, or supersede the licenses and terms governing the third-party dependencies and data products listed above.
