import os, inspect, sys
from pathlib import Path

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
grandpadir = os.path.dirname(currentdir)
sys.path.insert(0, grandpadir)

from utils import helper_functions
from configpkg import ConfigMger, DatasetConfig
from holders.Dataset import Dataset
from utils.helper_functions import sort_files_by_dim, read_nav_files
from utils.shared_names import *
from comparison.comparison_utils import get_dataset_name
from utils.pseudo_samples import PseudoSamplesMger
import pandas as pd
import json
import numpy as np
from pipeline.automl.automl_constants import MAX_FEATURES

pipeline = 'results_predictive'


# conf = {'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'test'}
# conf = {'path': Path('..', pipeline, 'iforest'), 'detector': 'iforest', 'type': 'test'}

conf = {'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'synthetic'}
# conf = {'path': Path('..', pipeline, 'iforest'), 'detector': 'iforest', 'type': 'synthetic'}
# conf = {'path': Path('..', pipeline, 'loda'), 'detector': 'loda', 'type': 'synthetic'}

# conf = {'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'real'}
# conf = {'path': Path('..', pipeline, 'iforest'), 'detector': 'iforest', 'type': 'real'}
# conf = {'path': Path('..', pipeline, 'loda'), 'detector': 'loda', 'type': 'real'}


def analyze():
    nav_files = read_nav_files(conf['path'], conf['type'])
    nav_files = sort_files_by_dim(nav_files)
    analysis_per_nav_file(nav_files)


def analysis_per_nav_file(nav_files):
    dataset_names = []
    feature_perf_prec = pd.DataFrame()
    feature_perf_recall = pd.DataFrame()
    for dim, nav_file in nav_files.items():
        ConfigMger.setup_configs(nav_file[FileKeys.navigator_conf_path])
        real_dims = dim - 1 - (conf['type'] == 'synthetic')
        dname = get_dataset_name(nav_file[FileKeys.navigator_original_dataset_path], conf['type'] == 'synthetic')
        print(dname + ' ' + str(real_dims) + '-d')
        dataset_names.append(dname + ' ' + str(real_dims) + '-d')
        methods_features = get_selected_features_per_method(nav_file)
        rel_features = get_relevant_features(nav_file)
        recall, prec = calculate_feature_metrics(methods_features, rel_features)
        feature_perf_prec = pd.concat([feature_perf_prec, prec], axis=1)
        feature_perf_recall = pd.concat([feature_perf_recall, recall], axis=1)
    feature_perf_prec.columns = dataset_names
    feature_perf_recall.columns = dataset_names
    pd.concat([feature_perf_recall,feature_perf_prec], axis=1).to_latex('abnormalfeatures.tex', index=True, header=True)


def get_selected_features_per_method(nav_file):
    methods_sel_features = {}
    protean_psmger = PseudoSamplesMger(nav_file[FileKeys.navigator_pseudo_samples_key], 'roc_auc', fs=True)
    best_model, best_k = protean_psmger.get_best_model()
    methods_sel_features['PROTEUS$_{fs}$'] = best_model['feature_selection']['features']
    methods_explanations_file = Path(nav_file[FileKeys.navigator_baselines_dir_key], FileNames.baselines_explanations_fname)
    with open(methods_explanations_file) as json_file:
        explanations = json.load(json_file)
        for method, data in explanations.items():
            features_sorted = np.argsort(np.array(data['global_explanation']))[::-1]
            method_name = '$PROTEUS$_{' + method + '}$'
            methods_sel_features[method_name] = features_sorted[:MAX_FEATURES]
    return methods_sel_features


def get_relevant_features(nav_file):
    orig_data = Dataset(nav_file[FileKeys.navigator_original_dataset_path], DatasetConfig.get_anomaly_column_name(),
                        DatasetConfig.get_subspace_column_name())
    rel_features = orig_data.get_relevant_features()
    if len(rel_features) == 0:
        assert conf['type'] == 'real'
        rel_features = set(np.arange(orig_data.get_X().shape[1]))
    return rel_features


def calculate_feature_metrics(methods_features, rel_features):
    methods_precision = {}
    methods_recall = {}
    for method, sel_features in methods_features.items():
        methods_precision[method] = features_precision(sel_features, rel_features)
        methods_recall[method] = features_recall(sel_features, rel_features)
    methods_recall_as_df = pd.DataFrame(methods_recall.values(), index=methods_recall.keys())
    methods_precision_as_df = pd.DataFrame(methods_precision.values(), index=methods_precision.keys())
    return methods_recall_as_df, methods_precision_as_df


def features_precision(selected_features, optimal_features):
    return len(optimal_features.intersection(selected_features)) / len(selected_features)


def features_recall(selected_features, optimal_features):
    return len(optimal_features.intersection(selected_features)) / len(optimal_features)


if __name__ == '__main__':
    analyze()