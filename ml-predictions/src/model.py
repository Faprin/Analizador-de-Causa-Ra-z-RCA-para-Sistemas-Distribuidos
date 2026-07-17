import joblib
import os
import json
import pandas as pd

MODEL_DIR = os.path.join(os.path.dirname(__file__), "../modelos")
BEST_MODEL_NAME = "01_isolation_forest"

class RCAModel:

    def __init__(self):
        self.model = None
        self.metadata = None
    
    def load_model(self):
        self.model = joblib.load(f"{MODEL_DIR}/{BEST_MODEL_NAME}.pkl")

        with open(f"{MODEL_DIR}/metadatos.json", "r") as f:
            self.metadata = json.load(f)
        
        print(f"Modelo cargado: {self.metadata['fecha_entreno']}")
        # print(f"Features: {self.metadata['features']}")
        return self

    def predict(self, df: pd.DataFrame) -> pd.Series:
        pred = self.model.predict(df)
        return pd.Series(pred, index=df, name='prediction')
    
    def score(self, df: pd.DataFrame) -> pd.Series:
        scores = self.model.decision_function(df)
        return pd.Series(scores, index=df, name='scores')

    def analize(self, df: pd.DataFrame) -> pd.DataFrame:
        resultado = df.copy
        resultado["prediction"] = self.predict(df)
        resultado["anomaly_score"] = self.score(df)
        
        anomalias = resultado[resultado["prediction"] == -1].copy()
        anomalias = anomalias.sort_values("anomaly_score")
        return anomalias

rca_model = RCAModel()