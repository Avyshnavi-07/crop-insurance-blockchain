"""
Autoencoder Reconstruction Anomaly Detection Model for Parametric Crop Insurance.

Reconstruction baseline using scikit-learn MLPRegressor bottleneck architecture.
Trained strictly on legitimate (non-fraud) training rows to learn normal underwriting profiles.
Reconstruction error threshold is chosen strictly on the validation set.
"""

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler


class AutoencoderDetector:
    """
    MLP Autoencoder baseline for tabular fraud detection.
    Bottleneck architecture: Input -> 8 -> 4 -> 8 -> Output.
    Trained strictly on non-fraud training profiles.
    Decision threshold selected strictly on validation set.
    """

    def __init__(
        self,
        hidden_layer_sizes: tuple = (8, 4, 8),
        activation: str = "relu",
        max_iter: int = 250,
        random_state: int = 42,
    ):
        self.hidden_layer_sizes = hidden_layer_sizes
        self.activation = activation
        self.max_iter = max_iter
        self.random_state = random_state

        self.scaler = StandardScaler()
        self.model = MLPRegressor(
            hidden_layer_sizes=self.hidden_layer_sizes,
            activation=self.activation,
            max_iter=self.max_iter,
            random_state=self.random_state,
            early_stopping=True,
            n_iter_no_change=15,
            learning_rate_init=0.01,
        )
        self.threshold: float = 0.5  # Tuned on validation set

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: Optional[np.ndarray] = None,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[np.ndarray] = None,
    ):
        """
        Trains autoencoder strictly on non-fraud training instances.
        If y_train is provided, filters for y_train == 0.
        Tunes threshold on validation set.
        """
        if y_train is not None:
            mask = (y_train == 0)
            X_legit = X_train[mask]
        else:
            X_legit = X_train

        X_scaled = self.scaler.fit_transform(X_legit)
        # Autoencoder task: reconstruct the input
        self.model.fit(X_scaled, X_scaled)

        if X_val is not None and y_val is not None:
            self.tune_threshold(X_val, y_val)

        return self

    def compute_reconstruction_error(self, X: pd.DataFrame) -> np.ndarray:
        """
        Computes Mean Squared Error (MSE) between scaled input features and reconstructed output.
        """
        X_scaled = self.scaler.transform(X)
        X_reconstructed = self.model.predict(X_scaled)
        # Element-wise squared difference averaged across features
        mse = np.mean(np.square(X_scaled - X_reconstructed), axis=1)
        return mse

    def tune_threshold(self, X_val: pd.DataFrame, y_val: np.ndarray):
        """
        Selects reconstruction error threshold that maximizes F1 score on validation set.
        """
        errors = self.compute_reconstruction_error(X_val)

        # Search percentiles between 75% and 99.5%
        percentiles = np.linspace(75, 99.5, 120)
        candidate_thresholds = np.percentile(errors, percentiles)

        best_f1 = -1.0
        best_threshold = float(np.median(errors))

        for thresh in candidate_thresholds:
            preds = (errors >= thresh).astype(int)
            score = f1_score(y_val, preds, zero_division=0)
            if score > best_f1:
                best_f1 = score
                best_threshold = float(thresh)

        self.threshold = best_threshold

    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        """
        Returns reconstruction error MSE. Higher values indicate higher abnormality.
        """
        return self.compute_reconstruction_error(X)

    def predict_anomaly_score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Normalized reconstruction anomaly score in [0, 1].
        """
        errors = self.compute_reconstruction_error(X)
        e_min, e_max = errors.min(), errors.max()
        if e_max > e_min:
            return (errors - e_min) / (e_max - e_min)
        return np.zeros_like(errors)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predicts binary fraud class based on validation-tuned reconstruction error threshold.
        """
        errors = self.compute_reconstruction_error(X)
        return (errors >= self.threshold).astype(int)
