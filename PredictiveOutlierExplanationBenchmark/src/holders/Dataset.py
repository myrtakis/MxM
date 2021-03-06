from configpkg.SettingsConfig import SettingsConfig
import pandas as pd
import numpy as np


class Dataset:

    def __init__(self, dataset, anomaly_column, subspace_column, reset_index=False):
        self.__anomaly_column = anomaly_column
        self.__subspace_column = subspace_column
        self.__task_is_classification = SettingsConfig.is_classification_task()
        self.__df_data = None
        self.__labels = None
        self.__scores = None
        self.__subspaces = None
        self.__outlier_indices = None
        self.__inlier_indices = None
        self.__pseudo_sample_indices_per_outlier = None
        self.__reset_index = reset_index
        self.__setup_dataset(dataset)

    def __setup_dataset(self, dataset):
        self.__set_df(dataset)
        self.__set_df_data()
        self.__set_subspaces()
        if self.__task_is_classification:
            self.__set_labels()
            self.__set_outlier_indices()
            self.__set_inlier_indices()
        else:
            self.__set_scores()

    # Setter Functions

    def __set_df(self, dataset):
        if isinstance(dataset, pd.DataFrame):
            self.__df = dataset.copy()
            if self.__reset_index:
                self.__df = self.__df.reset_index(drop=True)
        else:
            self.__df = pd.read_csv(dataset)

    def __set_df_data(self):
        self.__df_data = self.__df.drop(columns=[self.__anomaly_column])
        if self.__subspace_column is not None:
            self.__df_data = self.__df_data.drop(columns=[self.__subspace_column])

    def __set_subspaces(self):
        if self.__subspace_column is not None:
            self.__subspaces = self.__df[self.__subspace_column]

    def __set_outlier_indices(self):
        self.__outlier_indices = np.array(self.__df.loc[self.__labels == 1, self.__anomaly_column].index).tolist()

    def __set_inlier_indices(self):
        self.__inlier_indices = np.array(self.__df.loc[self.__labels == 0, self.__anomaly_column].index).tolist()

    def __set_labels(self):
        self.__labels = self.__df[self.__anomaly_column]

    def __set_scores(self):
        self.__scores = self.__df[self.__anomaly_column]

    def set_pseudo_samples_indices_per_outlier(self, ps_indices_per_outlier):
        assert ps_indices_per_outlier is not None and isinstance(ps_indices_per_outlier, dict)
        self.__pseudo_sample_indices_per_outlier = ps_indices_per_outlier

    # Getter Functions

    def get_X(self):
        return self.__df_data

    def get_Y(self):
        if self.__task_is_classification:
            return np.array(self.__labels)
        else:
            return np.array(self.__scores)

    def get_subspaces(self):
        return self.__subspaces

    def get_relevant_features(self):
        rel_features = set()
        if self.__subspaces is not None:
            for sub in set(self.__subspaces[np.where(self.__subspaces != '-')[0]]):
                sub_as_set = set(map(int, sub[sub.index('[') + 1: sub.index(']')].split()))
                rel_features = rel_features.union(sub_as_set)
        return rel_features


    def get_outlier_indices(self):
        assert self.__task_is_classification, "Outliers are predefined only for Classifcation Task and not for Regression"
        return self.__outlier_indices

    def get_std_per_column(self):
        return np.std(self.get_X().values, axis=0)

    def get_mean_per_column(self):
        return np.mean(self.get_X().values, axis=0)

    def get_inlier_indices(self):
        assert self.__task_is_classification, "Inliers are predefined only for Classifcation Task and not for Regression"
        return self.__inlier_indices

    def get_df(self):
        return self.__df

    def get_anomaly_column_name(self):
        return self.__anomaly_column

    def get_subspace_column_name(self):
        return self.__subspace_column

    def get_subspace_column_data(self):
        if self.__subspace_column is not None:
            return np.array(self.__df[self.__subspace_column])
        else:
            return None

    def get_pseudo_sample_indices_per_outlier(self):
        return self.__pseudo_sample_indices_per_outlier

    def contains_pseudo_samples(self):
        return self.__pseudo_sample_indices_per_outlier is not None

    def last_original_sample_index(self):
        if self.__pseudo_sample_indices_per_outlier is not None:
            return min(min(self.__pseudo_sample_indices_per_outlier.values()))
        else:
            return None
