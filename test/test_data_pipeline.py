"""
Unit tests for Crop Insurance Data Pipeline (Phase 2).
Covers:
1. Weather data extraction and daily validation.
2. Bounding box calculation for 2 km farm parcels.
3. Leave-one-year-out baseline calculations (verifying zero data leakage).
4. Deficit calculation and clamping.
5. Tier mapping and exact boundary condition handling.
6. 2-of-3 Oracle consensus and median fallback parity with CropInsurance.sol.
7. Payout schedule calculations.
8. Missing and corrupt data handling.
9. Dataset schema and integrity verification on data/processed/dataset.csv.
"""

import unittest
import pandas as pd

from oracles.data_sources import (
    DISTRICT_COORDINATES,
    get_bounding_box,
    extract_cumulative_rainfall,
    validate_weather_data,
)
from build_dataset import (
    load_tier_rules,
    compute_leave_one_out_baseline,
    compute_deficit_pct,
    map_deficit_to_tier,
    calculate_consensus,
    calculate_payout_pct,
    CONFIG_PATH,
    OUTPUT_FILE,
)


class TestDataPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_tier_rules(CONFIG_PATH)

    def test_district_coordinates(self):
        """Validates geographic coordinates for Andhra Pradesh target districts."""
        self.assertIn("Anantapur", DISTRICT_COORDINATES)
        self.assertIn("Kurnool", DISTRICT_COORDINATES)
        self.assertIn("Kadapa", DISTRICT_COORDINATES)
        self.assertAlmostEqual(DISTRICT_COORDINATES["Anantapur"]["lat"], 14.68, places=2)
        self.assertAlmostEqual(DISTRICT_COORDINATES["Anantapur"]["lon"], 77.60, places=2)

    def test_bounding_box_geometry(self):
        """Verifies 2 km bounding box delta computation."""
        min_lat, min_lon, max_lat, max_lon = get_bounding_box(14.68, 77.60, box_size_km=2.0)
        self.assertLess(min_lat, 14.68)
        self.assertGreater(max_lat, 14.68)
        self.assertLess(min_lon, 77.60)
        self.assertGreater(max_lon, 77.60)
        # Approximate 2 km height in latitude degrees is 2 / 111 ~= 0.018
        self.assertAlmostEqual(max_lat - min_lat, 0.018, places=3)

    def test_extract_cumulative_rainfall_valid(self):
        """Tests extraction and summation of valid precipitation data."""
        mock_raw = {
            "daily": {
                "time": ["2023-06-01", "2023-06-02", "2023-06-03"],
                "precipitation_sum": [10.5, 0.0, 24.5],
            }
        }
        total = extract_cumulative_rainfall(mock_raw)
        self.assertEqual(total, 35.0)

    def test_extract_cumulative_rainfall_with_none_and_negative(self):
        """Tests filtering of None and rejection of invalid negative values."""
        mock_raw = {
            "daily": {
                "precipitation_sum": [10.0, None, -5.0, 15.0],
            }
        }
        total = extract_cumulative_rainfall(mock_raw)
        self.assertEqual(total, 25.0)

    def test_extract_cumulative_rainfall_empty(self):
        """Tests handling of empty or missing daily data."""
        self.assertIsNone(extract_cumulative_rainfall({}))
        self.assertIsNone(extract_cumulative_rainfall({"daily": {}}))
        self.assertIsNone(extract_cumulative_rainfall({"daily": {"precipitation_sum": []}}))

    def test_validate_weather_data(self):
        """Tests validation of Kharif 153-day completeness."""
        valid_mock = {
            "daily": {
                "time": [f"2023-day-{i}" for i in range(153)],
                "precipitation_sum": [2.0] * 153,
            }
        }
        report = validate_weather_data(valid_mock)
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["total_days"], 153)
        self.assertEqual(report["negative_count"], 0)

        invalid_mock = {
            "daily": {
                "time": ["2023-06-01", "2023-06-02"],
                "precipitation_sum": [5.0, -1.0],
            }
        }
        report_bad = validate_weather_data(invalid_mock)
        self.assertFalse(report_bad["is_valid"])
        self.assertEqual(report_bad["negative_count"], 1)

    def test_leave_one_out_baseline_no_leakage(self):
        """
        Verifies that target year's observation is strictly excluded from its own baseline.
        Given series with values: {2017: 100, 2018: 200, 2019: 300, 2020: 1000}
        Baseline for 2020 should be median([100, 200, 300]) = 200 (1000 is excluded).
        Baseline for 2017 should be median([200, 300, 1000]) = 300 (100 is excluded).
        """
        series = pd.Series({2017: 100.0, 2018: 200.0, 2019: 300.0, 2020: 1000.0})
        b_2020 = compute_leave_one_out_baseline(series, 2020)
        self.assertEqual(b_2020, 200.0)

        b_2017 = compute_leave_one_out_baseline(series, 2017)
        self.assertEqual(b_2017, 300.0)

    def test_compute_deficit_pct(self):
        """Tests deficit calculation and zero-clamping."""
        # 500 baseline, 250 observed -> 50% deficit
        self.assertEqual(compute_deficit_pct(500.0, 250.0), 50.0)
        # 500 baseline, 600 observed -> 0% deficit (surplus)
        self.assertEqual(compute_deficit_pct(500.0, 600.0), 0.0)
        # Missing values
        self.assertIsNone(compute_deficit_pct(None, 250.0))
        self.assertIsNone(compute_deficit_pct(500.0, None))

    def test_tier_mapping_weather_threshold_boundaries(self):
        """
        Tests weather rainfall deficit thresholds from tier_rules.json:
          Tier 0: <= 20.0%
          Tier 1: 20.01% - 40.0%
          Tier 2: 40.01% - 60.0%
          Tier 3: > 60.0%
        """
        self.assertEqual(map_deficit_to_tier(0.0, "weather_rainfall", self.rules), 0)
        self.assertEqual(map_deficit_to_tier(20.0, "weather_rainfall", self.rules), 0)
        self.assertEqual(map_deficit_to_tier(20.01, "weather_rainfall", self.rules), 1)
        self.assertEqual(map_deficit_to_tier(40.0, "weather_rainfall", self.rules), 1)
        self.assertEqual(map_deficit_to_tier(40.01, "weather_rainfall", self.rules), 2)
        self.assertEqual(map_deficit_to_tier(60.0, "weather_rainfall", self.rules), 2)
        self.assertEqual(map_deficit_to_tier(60.01, "weather_rainfall", self.rules), 3)
        self.assertEqual(map_deficit_to_tier(95.0, "weather_rainfall", self.rules), 3)

    def test_tier_mapping_ndvi_threshold_boundaries(self):
        """
        Tests satellite NDVI deficit thresholds from tier_rules.json:
          Tier 0: <= 15.0%
          Tier 1: 15.01% - 30.0%
          Tier 2: 30.01% - 45.0%
          Tier 3: > 45.0%
        """
        self.assertEqual(map_deficit_to_tier(15.0, "satellite_ndvi", self.rules), 0)
        self.assertEqual(map_deficit_to_tier(15.01, "satellite_ndvi", self.rules), 1)
        self.assertEqual(map_deficit_to_tier(30.0, "satellite_ndvi", self.rules), 1)
        self.assertEqual(map_deficit_to_tier(30.01, "satellite_ndvi", self.rules), 2)
        self.assertEqual(map_deficit_to_tier(45.0, "satellite_ndvi", self.rules), 2)
        self.assertEqual(map_deficit_to_tier(45.01, "satellite_ndvi", self.rules), 3)

    def test_consensus_two_match(self):
        """Verifies 2-of-3 agreement selects matching tier."""
        tier, rule = calculate_consensus(2, 2, 3)
        self.assertEqual(tier, 2)
        self.assertEqual(rule, "TWO_OF_THREE_AGREE")

        tier, rule = calculate_consensus(0, 1, 1)
        self.assertEqual(tier, 1)
        self.assertEqual(rule, "TWO_OF_THREE_AGREE")

    def test_consensus_three_differ_median(self):
        """Verifies that when all three differ, the median tier is selected."""
        tier, rule = calculate_consensus(0, 2, 1)
        self.assertEqual(tier, 1)  # sorted: [0, 1, 2] -> median is 1
        self.assertEqual(rule, "THREE_DIFFER_MEDIAN")

        tier, rule = calculate_consensus(3, 1, 2)
        self.assertEqual(tier, 2)  # sorted: [1, 2, 3] -> median is 2
        self.assertEqual(rule, "THREE_DIFFER_MEDIAN")

    def test_consensus_insufficient_or_disagreeing_reports(self):
        """Verifies waiting when consensus conditions are not met."""
        # Only 1 report
        tier, rule = calculate_consensus(2, None, None)
        self.assertIsNone(tier)
        self.assertEqual(rule, "AWAITING_REPORTS")

        # 2 reports disagreeing
        tier, rule = calculate_consensus(1, 2, None)
        self.assertIsNone(tier)
        self.assertEqual(rule, "DISAGREEMENT_WAIT_THIRD")

        # 2 reports matching
        tier, rule = calculate_consensus(2, 2, None)
        self.assertEqual(tier, 2)
        self.assertEqual(rule, "TWO_MATCH")

    def test_payout_schedule(self):
        """Verifies tiered parametric payout schedule."""
        self.assertEqual(calculate_payout_pct(0), 0.0)
        self.assertEqual(calculate_payout_pct(1), 25.0)
        self.assertEqual(calculate_payout_pct(2), 50.0)
        self.assertEqual(calculate_payout_pct(3), 100.0)
        self.assertEqual(calculate_payout_pct(None), 0.0)

    def test_generated_dataset_csv_integrity(self):
        """Validates the output data/processed/dataset.csv file schema and data contents."""
        self.assertTrue(OUTPUT_FILE.exists(), f"dataset.csv not found at {OUTPUT_FILE}")

        df = pd.read_csv(OUTPUT_FILE)

        # 1. Row count & coverage
        self.assertEqual(len(df), 24, "Dataset must contain exactly 24 rows (3 districts x 8 years)")
        self.assertEqual(set(df["district"].unique()), {"Anantapur", "Kurnool", "Kadapa"})
        self.assertEqual(set(df["year"].unique()), set(range(2017, 2025)))

        # 2. No duplicate district-year pairs
        duplicates = df.duplicated(subset=["district", "year"])
        self.assertFalse(duplicates.any(), "Duplicate district-year rows found in dataset.csv")

        # 3. Essential columns present
        required_cols = [
            "district",
            "year",
            "season",
            "crop",
            "rainfall_mm",
            "rainfall_baseline_mm",
            "rainfall_deficit_pct",
            "rainfall_tier",
            "ndvi_peak",
            "ndvi_baseline",
            "ndvi_deficit_pct",
            "ndvi_tier",
            "soil_moisture_mean",
            "soil_baseline",
            "soil_deficit_pct",
            "soil_tier",
            "consensus_tier",
            "payout_pct",
            "consensus_rule",
            "data_source_weather",
            "data_source_satellite",
            "data_source_soil",
            "satellite_data_status",
            "soil_data_status",
        ]
        for col in required_cols:
            self.assertIn(col, df.columns, f"Required column missing: {col}")

        # 4. Zero nulls in core numerical metrics
        for col in [
            "rainfall_mm",
            "rainfall_baseline_mm",
            "rainfall_deficit_pct",
            "rainfall_tier",
            "ndvi_peak",
            "ndvi_baseline",
            "ndvi_deficit_pct",
            "ndvi_tier",
            "soil_moisture_mean",
            "soil_baseline",
            "soil_deficit_pct",
            "soil_tier",
            "consensus_tier",
            "payout_pct",
        ]:
            self.assertEqual(df[col].isnull().sum(), 0, f"Column {col} has unexpected null values")

        # 5. Payout percentages strictly valid
        valid_payouts = {0.0, 25.0, 50.0, 100.0}
        self.assertTrue(
            set(df["payout_pct"].unique()).issubset(valid_payouts),
            f"Invalid payout percentages found: {set(df['payout_pct'].unique())}",
        )

        # 6. Consensus tiers strictly in {0, 1, 2, 3}
        self.assertTrue(
            set(df["consensus_tier"].unique()).issubset({0, 1, 2, 3}),
            f"Invalid consensus tiers found: {set(df['consensus_tier'].unique())}",
        )


if __name__ == "__main__":
    unittest.main()
