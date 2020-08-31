from pathlib import Path
from matplotlib.font_manager import FontProperties
import os, sys, inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
grandpadir = os.path.dirname(os.path.dirname(currentdir))
sys.path.insert(0, grandpadir)
from models.OutlierDetector import Detector
from baselines.posthoc_explanation_methods import ExplanationMethods
from configpkg import ConfigMger, DatasetConfig
from holders.Dataset import Dataset
from pipeline.automl.automl_processor import AutoML
from utils import metrics
from utils.helper_functions import read_nav_files, sort_files_by_dim
from utils.pseudo_samples import PseudoSamplesMger
from utils.shared_names import FileKeys, FileNames
from analysis.comparison.comparison_utils import load_baseline_explanations, get_dataset_name
from collections import OrderedDict
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


pipeline = 'results_predictive'

expl_size = 10
noise_level = None

datasets = {
    'wbc': 'Breast Cancer',
    'arrhythmia': 'Arrhythmia',
    'ionosphere': 'Ionosphere'
}

test_confs = [
    {'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'test'},
{'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'test'},
{'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'test'}
]

real_confs = [
    {'path': Path('..', pipeline, 'lof'), 'detector': 'lof', 'type': 'real'},
    {'path': Path('..', pipeline, 'iforest'), 'detector': 'iforest', 'type': 'real'},
    {'path': Path('..', pipeline, 'loda'), 'detector': 'loda', 'type': 'real'}
]


def analyze_explanation_size():
    fs_methods = 5
    pred_perfs_dict = {}
    fig, axes = plt.subplots(nrows=1, ncols=3, figsize=(10, 3), sharey=True)
    for conf in real_confs:
        print(conf)
        nav_files_json = sort_files_by_dim(read_nav_files(conf['path'], conf['type']))
        for dim, nav_file in nav_files_json.items():
            real_dims = dim - 1
            dname = get_dataset_name(nav_file[FileKeys.navigator_original_dataset_path], conf['type'] != 'real')
            if dname not in datasets:
                continue
            print(dname + ' ' + str(real_dims) + 'd')
            info_dict_proteus = read_proteus_files(nav_file)
            info_dict_baselines = read_baseline_files(nav_file)
            perfs_test = methods_effectiveness(nav_file, info_dict_proteus, info_dict_baselines, in_sample=False)
            if perfs_test.shape[1] < fs_methods:
                loda = pd.DataFrame(np.full(perfs_test.shape[0], 1), index=perfs_test.index, columns=['loda'])
                perfs_test = pd.concat([perfs_test, loda], axis=1)
            if dname not in pred_perfs_dict:
                pred_perfs_dict[dname] = perfs_test
            else:
                pred_perfs_dict[dname] += perfs_test
    min_perf = min([df.min().min() for df in pred_perfs_dict.values()]) / 3
    for i, (dname, df) in enumerate(pred_perfs_dict.items()):
        df /= 3
        plot_datasets_perfs(axes[i], df, datasets[dname], min_perf)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=5, fontsize=12, handletextpad=0.1)
    plt.subplots_adjust(wspace=.15, hspace=.15, top=.7)
    #plt.tight_layout()
    output_folder = Path('..', 'figures', 'results')
    output_folder.mkdir(parents=True, exist_ok=True)
    plt.savefig(Path(output_folder, 'real-noise-auc.png'), dpi=300, bbox_inches='tight', pad_inches=0)
    plt.clf()


def plot_datasets_perfs(ax, perfs, dataset_title, min_perf):
    leg_handles_dict = {
        'full': ('tab:blue', 'PROTEUS$_{full}$'),
        'fs': ('tab:orange', 'PROTEUS$_{fs}$'),
        'ca-lasso': ('tab:green', 'PROTEUS$_{ca-lasso}$'),
        'shap': ('tab:red', 'PROTEUS$_{shap}$'),
        'loda': ('tab:purple', 'PROTEUS$_{loda}$'),
    }
    colors = []
    markers = ["-s", "-o", "-v", "-^", "-*"]
    for m in leg_handles_dict:
        colors.append(leg_handles_dict[m][0])
    perfs.index = [str(int(float(x) * 100)) + '%' for x in perfs.index]
    perfs.columns = ['PROTEUS$_{' + x + '}$' for x in perfs.columns]
    perfs.plot(ax=ax, legend=None, style=markers, color=colors, markersize=8)
    #ax.locator_params(axis='x', nbins=perfs.shape[0])
    #ax.set_ylabel('Test AUC')
    ax.set_title(dataset_title, fontsize=14)
    ax.set_ylim([min_perf, 1.05])
    #ax.set_yticks(np.arange(0.5, 1.05, 0.05))
    plt.setp(ax.get_xticklabels(), fontsize=13)
    plt.setp(ax.get_yticklabels(), fontsize=13)
    #ax.set_yticks(np.arange(0, 1.2, 0.2))


def methods_effectiveness(nav_file, info_dict_proteus, info_dict_baselines, in_sample):
    method_perfs_pd = pd.DataFrame()
    for method, data in info_dict_proteus.items():
        fs = False if 'full' in method else True
        method_perfs_pd = pd.concat([method_perfs_pd, effectiveness(nav_file, data, method, False, fs, in_sample)], axis=1)
    for method, data in info_dict_baselines.items():
        method_perfs_pd = pd.concat([method_perfs_pd, effectiveness(nav_file, data, method, True, True, in_sample)], axis=1)
    return method_perfs_pd


def effectiveness(nav_file, info_dict, method, is_baseline, fs, in_sample):
    perf_dict = OrderedDict()
    if is_baseline:
        ps_dict = nav_file[FileKeys.navigator_baselines_key]
    else:
        ps_dict = nav_file[FileKeys.navigator_pseudo_samples_key]
    for k, v in info_dict.items():
        for ps_key, dir in v.items():
            if is_baseline:
                reform_pseudo_samples_dict(ps_dict[method][ps_key], dir)
            else:
                reform_pseudo_samples_dict(ps_dict[ps_key], dir)
        if is_baseline:
            ps_mger = PseudoSamplesMger(ps_dict[method], 'roc_auc', fs)
        else:
            ps_mger = PseudoSamplesMger(ps_dict, 'roc_auc', fs)
        perf, ci = get_effectiveness_of_best_model(ps_mger, in_sample)
        perf_dict[k] = perf
    return pd.DataFrame(perf_dict.values(), index=perf_dict.keys(), columns=[method])


def get_effectiveness_of_best_model(ps_mger, in_sample):
    effectiveness_key = 'effectiveness' if in_sample else 'hold_out_effectiveness'
    best_model, best_k = ps_mger.get_best_model()
    conf_intervals = [round(x, 2) for x in best_model['confidence_intervals']]
    return round(best_model[effectiveness_key], 3), conf_intervals


def reform_pseudo_samples_dict(ps_dict, dir):
    old_dir = ps_dict[FileKeys.navigator_pseudo_sample_dir_key]
    for k, v in ps_dict.items():
        if type(v) is str and old_dir in v:
            ps_dict[k] = old_dir.replace(old_dir, dir)
    return ps_dict


def read_proteus_files(nav_file):
    info_files_dict = {}
    for ps_samples, data in nav_file[FileKeys.navigator_pseudo_samples_key].items():
        ps_dir = Path(data[FileKeys.navigator_pseudo_sample_dir_key]).parent
        assert str(ps_dir).endswith(ps_samples)
        update_info_dict(info_files_dict, ps_dir, ps_samples)
    return {'full': sort_info_dict(info_files_dict),
            'fs': sort_info_dict(info_files_dict)}


def read_baseline_files(nav_file):
    info_files_dict = {}
    for method, method_data in nav_file[FileKeys.navigator_baselines_key].items():
        if method == 'random':
            continue
        info_files_dict[method] = {}
        for ps_samples, ps_data in method_data.items():
            update_info_dict(info_files_dict[method], ps_data[FileKeys.navigator_pseudo_sample_dir_key], ps_samples)
        info_files_dict[method] = sort_info_dict(info_files_dict[method])
    return info_files_dict


def update_info_dict(info_file_dict, folder, ps_samples):
    for r, d, f in os.walk(folder):
        for file in f:
            if FileNames.info_file_fname == file:
                info_dict = read_info_file(Path(r, file))
                if valid_info_file(info_dict):
                    if expl_size is None:
                        key = info_dict[FileKeys.info_file_explanation_size]
                    else:
                        key = info_dict[FileKeys.info_file_noise_level]
                    info_file_dict.setdefault(key, {})
                    info_file_dict[key][ps_samples] = r


def valid_info_file(info_dict):
    assert expl_size is not None or noise_level is not None
    if expl_size is not None and info_dict[FileKeys.info_file_explanation_size] != expl_size:
        return False
    if noise_level is not None and info_dict[FileKeys.info_file_noise_level] != noise_level:
        return False
    return True


def sort_info_dict(info_dict):
    info_dict_sorted = OrderedDict()
    for k in sorted(info_dict.keys()):
        info_dict_sorted[k] = info_dict[k]
    return info_dict_sorted


def read_info_file(info_file):
    with open(info_file) as json_file:
        info_dict = json.load(json_file)
        return info_dict


if __name__ == '__main__':
    analyze_explanation_size()