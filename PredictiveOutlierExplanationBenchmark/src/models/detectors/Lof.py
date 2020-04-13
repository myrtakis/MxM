from sklearn.neighbors import LocalOutlierFactor
import numpy as np


class Lof:

    def __init__(self):
        self.__clf = None

    def train(self, X_train, params):
        self.__clf = LocalOutlierFactor(n_neighbors=params['n_neighbors'], novelty=True,
                                        contamination='auto').fit(X_train)

    def score_samples(self):
        return np.array(self.__clf.negative_outlier_factor_) * -1

    def predict_scores(self, new_samples):
        return np.array(self.__clf.score_samples(new_samples)) * -1