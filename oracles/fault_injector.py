"""
Fault Injector module for oracle robustness experiments.

Allows injecting configurable error rates (e.g. 10%, 20%, 30%) and error modes
('random', 'off_by_one') into any oracle report. Uses independent seeded RNG
for reproducible scientific experimentation.
"""

import random
from typing import Optional, Tuple


class FaultInjector:
    """Configurable synthetic fault injector for oracle severity tiers."""

    VALID_MODES = ("random", "off_by_one")
    VALID_TIERS = (0, 1, 2, 3)

    def __init__(
        self,
        error_rate: float = 0.0,
        mode: str = "random",
        seed: Optional[int] = None,
    ):
        if not (0.0 <= error_rate <= 1.0):
            raise ValueError(f"Error rate must be between 0.0 and 1.0, got {error_rate}")
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Supported: {self.VALID_MODES}")

        self.error_rate = error_rate
        self.mode = mode
        self.seed = seed
        self._rng = random.Random(seed)

    def set_error_rate(self, error_rate: float):
        """Updates error rate probability."""
        if not (0.0 <= error_rate <= 1.0):
            raise ValueError(f"Error rate must be between 0.0 and 1.0, got {error_rate}")
        self.error_rate = error_rate

    def set_mode(self, mode: str):
        """Updates corruption mode ('random' or 'off_by_one')."""
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Supported: {self.VALID_MODES}")
        self.mode = mode

    def reset_seed(self, seed: Optional[int]):
        """Resets the internal random generator with a new seed."""
        self.seed = seed
        self._rng = random.Random(seed)

    def inject(self, true_tier: int) -> Tuple[int, bool]:
        """
        Conditionally corrupts the true severity tier based on error_rate.
        Returns:
            (reported_tier, was_faulted)
        """
        if true_tier not in self.VALID_TIERS:
            raise ValueError(f"True tier must be in {self.VALID_TIERS}, got {true_tier}")

        if self.error_rate <= 0.0:
            return true_tier, False

        # Roll probability
        roll = self._rng.random()
        if roll >= self.error_rate:
            return true_tier, False

        # Corrupt the tier
        if self.mode == "random":
            other_tiers = [t for t in self.VALID_TIERS if t != true_tier]
            corrupted_tier = self._rng.choice(other_tiers)
        elif self.mode == "off_by_one":
            if true_tier == 0:
                corrupted_tier = 1
            elif true_tier == 3:
                corrupted_tier = 2
            else:
                corrupted_tier = self._rng.choice([true_tier - 1, true_tier + 1])
        else:
            corrupted_tier = (true_tier + 1) % 4

        return corrupted_tier, True
