"""
Isolation Forest Anomaly Detection Model for Parametric Crop Insurance.

Unsupervised tree-based anomaly detector. Fits exclusively on feature distributions
without labels. Selects decision threshold strictly on the validation set.
"""

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler


class IsolationForestDetector:
    """
    Unsupervised Isolation Forest detector.
    Feature scaling via StandardScaler.
    Threshold tuning evaluated strictly on validation set.
    """

    def __init__(
        self,
        n_estimators: int = 150,
        max_samples: float = 0.8,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state

        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=self.random_state,
            contamination="auto",
        )
        self.threshold: float = 0.0  # Tuned on validation set

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: Optional[np.ndarray] = None,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[np.ndarray] = None,
    ):
        """
        Fits Isolation Forest on X_train without labels.
        If X_val and y_val are provided, selects the anomaly threshold that maximizes F1.
        """
        X_scaled = self.scaler.fit_transform(X_train)
        self.model.fit(X_scaled)

        # In sklearn IsolationForest, decision_function returns negative values for anomalies,
        # positive for inliers.
        if X_val is not None and y_val is not None:
            self.tune_threshold(X_val, y_val)
        else:
            self.threshold = 0.0

        return self

    def tune_threshold(self, X_val: pd.DataFrame, y_val: np.ndarray):
        """
        Tunes the anomaly threshold exclusively on the validation set.
        """
        scores = self.decision_function(X_val)
        # Search candidate percentiles
        percentiles = np.linspace(1, 25, 100)
        candidate_thresholds = np.percentile(scores, percentiles)

        best_f1 = -1.0
        best_threshold = 0.0

        for thresh in candidate_thresholds:
            # Lower score means more anomalous
            preds = (scores <= thresh).astype(int)
            score = f1_score(y_val, preds, zero_division=0)
            if score > best_f1:
                best_f1 = score
                best_threshold = float(thresh)

        self.threshold = best_threshold

    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        """
        Returns raw anomaly scores from Isolation Forest.
        Lower values correspond to higher abnormality.
        """
        X_scaled = self.scaler.transform(X)
        return self.model.decision_function(X_scaled)

    def predict_anomaly_score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Returns inverted, normalized anomaly score in [0, 1] where higher = more fraudulent.
        """
        raw_scores = self.decision_function(X)
        # Invert so higher = more anomalous
        inverted = -raw_scores
        # Min-max scale
        s_min, s_max = inverted.min(), inverted.max()
        if s_max > s_min:
            return (inverted - s_min) / (s_max - s_min)
        return np.zeros_like(inverted)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predicts binary fraud class based on the validation-tuned threshold.
        """
        scores = self.decision_function(X)
        return (scores <= self.threshold).astype(int)
