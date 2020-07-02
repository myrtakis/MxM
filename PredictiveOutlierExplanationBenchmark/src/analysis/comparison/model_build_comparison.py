from pathlib import Path
from matplotlib.font_manager import FontProperties
import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
grandpadir = os.path.dirname(os.path.dirname(currentdir))
sys.path.insert(0,grandpadir)
from configpkg import ConfigMger, DatasetConfig
from holders.Dataset import Dataset
from pipeline.automl.automl_processor import AutoML
from utils import metrics
from utils.helper_functions import read_nav_files, sort_files_by_dim
from utils.pseudo_samples import PseudoSamplesMger
from utils.shared_names import FileKeys, FileNames
from analysis.comparison.comparison_utils import load_baseline_explanations, get_dataset_name
from collections import OrderedDict
from sklearn.metrics import roc_auc_score
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os


MAX_FEATURES = 10
pipeline = 'results_predictive'
holdout = True


conf = {'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'test'}
# conf = {'path': Path('..', pipeline, 'iforest'), 'detector': 'iforest', 'type': 'synthetic'}
# conf = {'path': Path('..', pipeline, 'loda'), 'detector': 'loda', 'type': 'synthetic'}

# conf = {'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'real'}
# conf = {'path': Path('..', pipeline, 'iforest'), 'detector': 'iforest', 'type': 'real'}
# conf = {'path': Path('..', pipeline, 'loda'), 'detector': 'loda', 'type': 'real'}


def compare_methods():
    nav_files_json = sort_files_by_dim(read_nav_files(conf['path'], conf['type']))
    dataset_names = []
    for dim, nav_file in nav_files_json.items():
        print('Dataset')
        real_dims = dim-1-(conf['type'] == 'synthetic')
        dname = get_dataset_name(nav_file[FileKeys.navigator_original_dataset_path], conf['type'] == 'synthetic')
        dataset_names.append(dname + ' ' + str(real_dims) + '-d')
        ConfigMger.setup_configs(nav_file[FileKeys.navigator_conf_path])
        ps_mger = PseudoSamplesMger(nav_file[FileKeys.navigator_pseudo_samples_key], 'roc_auc', fs=True)
        baselines_dir = nav_file[FileKeys.navigator_baselines_dir_key]
        explanations = load_baseline_explanations(baselines_dir, MAX_FEATURES)
        run_baseline_explanations_in_automl(ps_mger, explanations, baselines_dir)


def run_baseline_explanations_in_automl(ps_mger, explanations, baselines_dir):
    datasets = get_datasets(ps_mger, FileKeys.navigator_pseudo_samples_data_path)
    reps_fold_inds = get_reps_folds_inds(ps_mger)
    for k, dataset in datasets.items():
        for method, expl in explanations.items():
            dataset.get_
            method_output_dir = Path(baselines_dir, method, 'pseudo_samples' + k)
            method_output_dir.mkdir(parents=True, exist_ok=True)
            best_model = AutoML(method_output_dir).run_with_explanation(reps_fold_inds[k], dataset, expl)
            if holdout:
                pass
                # best_model = test_best_model_in_hold_out(best_model)
    pass


def get_datasets(ps_mger, data_path_key):
    datasets = OrderedDict()
    sorted_k_confs = sorted(ps_mger.list_k_confs())
    for k in sorted_k_confs:
        dataset_path = ps_mger.get_info_field_of_k(k, data_path_key)
        anomaly_col = DatasetConfig.get_anomaly_column_name()
        subspace_col = DatasetConfig.get_subspace_column_name()
        datasets[k] = Dataset(dataset_path, anomaly_col, subspace_col)
    return datasets


def test_best_model_in_hold_out(best_model, test_data):
    for m_id, conf in best_model.items():
        fsel = conf.get_fsel()
        clf = conf.get_clf()
        X_new = test_data.get_X().iloc[:, fsel.get_features()]
        predictions = clf.predict_proba(X_new)
        perf = metrics.calculate_metric(test_data.get_Y(), predictions, m_id)
        conf.set_hold_out_effectiveness(perf, m_id)
        best_model[m_id] = conf
    return best_model


def get_reps_folds_inds(ps_mger):
    sorted_k_confs = sorted(ps_mger.list_k_confs())
    reps_folds_inds_per_k = OrderedDict()
    for k in sorted_k_confs:
        ps_samples_dir = ps_mger.get_info_field_of_k(k, FileKeys.navigator_pseudo_sample_dir_key)
        repetitions = Path(ps_samples_dir, FileNames.indices_folder)
        rep_count = 0
        reps_folds_inds_per_k.setdefault(k, {})
        for f in os.listdir(repetitions):
            if not f.endswith('.json'):
                continue
            reps_folds_inds_per_k[k].setdefault(rep_count, {})
            with open(Path(repetitions, f)) as json_file:
                reps_folds_inds_per_k[k][rep_count] = json.load(json_file, object_pairs_hook=OrderedDict)
            rep_count += 1
    return reps_folds_inds_per_k


if __name__ == '__main__':
    compare_methods()
    pass
