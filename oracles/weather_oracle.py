"""
Weather Oracle Service (Open-Meteo Rainfall Deficit).
Signs and submits reports to CropInsurance.sol with ORACLE_WEATHER_ROLE.
"""

from typing import Dict, Optional
from oracles.common import (
    get_district_year_metrics,
    get_oracle_private_key,
    get_rpc_url,
    setup_oracle_logger,
)
from oracles.contract_adapter import ContractAdapter, OracleSource, SeverityTier
from oracles.fault_injector import FaultInjector

logger = setup_oracle_logger("WeatherOracle")


class WeatherOracleService:
    """Service daemon for reporting weather / rainfall drought severity tiers."""

    def __init__(
        self,
        adapter: ContractAdapter,
        private_key: Optional[str] = None,
        fault_injector: Optional[FaultInjector] = None,
    ):
        self.adapter = adapter
        self.private_key = private_key or get_oracle_private_key("WEATHER")
        self.fault_injector = fault_injector or FaultInjector(error_rate=0.0)

    def determine_tier(self, district: str, year: int) -> int:
        """Retrieves verified rainfall tier from processed dataset."""
        metrics = get_district_year_metrics(district, year)
        return int(metrics["rainfall_tier"])

    def report_for_policy(
        self,
        policy_id: int,
        district: str,
        year: int,
    ) -> Dict:
        """
        Calculates or reads tier, applies fault injection if enabled,
        and submits the report to the smart contract.
        """
        true_tier = self.determine_tier(district, year)
        reported_tier, was_faulted = self.fault_injector.inject(true_tier)

        if was_faulted:
            logger.warning(
                f"[FAULT INJECTED] Policy {policy_id} ({district} {year}): "
                f"True Tier {true_tier} -> Corrupted Tier {reported_tier}"
            )
        else:
            logger.info(
                f"Policy {policy_id} ({district} {year}): Reporting Weather Tier {reported_tier}"
            )

        receipt = self.adapter.submit_report(
            oracle_private_key=self.private_key,
            policy_id=policy_id,
            source=OracleSource.WEATHER,
            tier=SeverityTier(reported_tier),
        )
        return {
            "policy_id": policy_id,
            "source": "WEATHER",
            "true_tier": true_tier,
            "reported_tier": reported_tier,
            "was_faulted": was_faulted,
            "tx_hash": receipt["transactionHash"].hex(),
        }


if __name__ == "__main__":
    rpc = get_rpc_url()
    adapter = ContractAdapter(rpc_url=rpc)
    service = WeatherOracleService(adapter=adapter)
    logger.info("Weather Oracle initialized. Ready to process policy events.")
