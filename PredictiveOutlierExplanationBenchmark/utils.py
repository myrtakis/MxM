import json
import os
import collections
import pandas as pd
from itertools import chain


def calculate_metrics_avg(results_json):
    metrics_avg = {}
    reps = len(results_json.keys())
    for rep_id, res in results_json.items():
        for metric_key, val in res.items():
            for conf_id in val:
                if metric_key not in metrics_avg:
                    metrics_avg[metric_key] = {}
                if conf_id not in metrics_avg[metric_key]:
                    metrics_avg[metric_key][conf_id] = 0
                metrics_avg[metric_key][conf_id] += val[conf_id]['performance']
    # Take the average
    for metric_id, conf in metrics_avg.items():
        for conf_id, mval in conf.items():
            metrics_avg[metric_id][conf_id] = mval / reps
    return metrics_avg


def get_results_files(dir_path, starting=None, ending=None, exclude=None, contains=None):
    fileslist = []
    assert os.path.isdir(dir_path)
    allfiles = os.listdir(dir_path)
    for f in allfiles:
        start_cond = True if starting is None else f.startswith(starting)
        end_cond = True if ending is None else f.endswith(ending)
        contains_cond = True if contains is None else contains in f
        exclude_cond = True if exclude is None else exclude not in f
        if start_cond and end_cond and contains_cond and exclude_cond:
            fileslist.append(os.path.join(dir_path, f))
    return fileslist


def get_results_as_dict(results_files):
    metric_dim_results_dict = {}
    for f in results_files:
        with open(f) as json_file:
            results = json.load(json_file)
            datasetname = (os.path.splitext(os.path.basename(f))[0]).split('_')[0]
            dim = int(datasetname.replace("hics", "").strip())
            metrics_results_avg = calculate_metrics_avg(results)
            for metric_key, results in metrics_results_avg.items():
                if metric_key not in metric_dim_results_dict:
                    metric_dim_results_dict[metric_key] = {}
                for alg, perfomance in results.items():
                    if alg not in metric_dim_results_dict[metric_key]:
                        metric_dim_results_dict[metric_key][alg] = {}
                    if dim not in metric_dim_results_dict[metric_key][alg]:
                        metric_dim_results_dict[metric_key][alg][dim] = perfomance
                metric_dim_results_dict[metric_key] = \
                    dict(collections.OrderedDict(sorted(metric_dim_results_dict[metric_key].items())))
    for metric_key, algs_dict in metric_dim_results_dict.items():
        for alg, performances in algs_dict.items():
            metric_dim_results_dict[metric_key][alg] = dict(collections.OrderedDict(sorted(performances.items())))
    return metric_dim_results_dict


def find_result_file(result_files, log_file):
    log_file_base = os.path.splitext(os.path.basename(log_file))[0]
    for f in result_files:
        result_file_base = os.path.splitext(os.path.basename(f))[0]
        if log_file_base.startswith(result_file_base):
            return f
    assert False


def get_dataset_path_from_json(datasets_json):
    assert len(datasets_json) == 1
    for id, obj in datasets_json.items():
        return obj['dataset_path']


def subspace_to_list(subspacestr, min_dim=None, max_dim=None):
    subspacestr_arr = subspacestr.replace('[', '').replace(']', '').split(';')
    valid_subspaces = {}
    for s in subspacestr_arr:
        s = s.strip()
        if s is None:
            continue
        ssplit = s.split()
        subspace_dim = len(list(map(int, ssplit)))
        min_dim = subspace_dim if min_dim is None else min_dim
        max_dim = subspace_dim if max_dim is None else max_dim
        if min_dim <= subspace_dim <= max_dim:
            valid_subspaces[s] = subspace_dim
    return valid_subspaces


def sort_datasets_dim(datasets):
    dim_dict = {}
    for d in datasets:
        dim = pd.read_csv(d).shape[1]
        dim_dict[dim] = d
    return dict(collections.OrderedDict(sorted(dim_dict.items()))).values()


def get_dataset_paths(dir_path):
    log_files = get_results_files(dir_path, contains='log')
    log_dataset_paths = {}
    for f in log_files:
        with open(f) as log_json_file:
            log = json.load(log_json_file)
            with open(log['config']) as conf_json_file:
                conf = json.load(conf_json_file)
                log_dataset_paths[f] = get_dataset_path_from_json(conf['datasets'])
    log_dataset_paths_dim_sorted = {}
    for log, dataset in log_dataset_paths.items():
        dim = pd.read_csv(dataset).shape[1]
        log_dataset_paths_dim_sorted[dim] = {log: dataset}
    return dict(collections.OrderedDict(sorted(log_dataset_paths_dim_sorted.items()))).values()


def get_relevant_features(df):
    rel_subspaces_str = set()
    rel_features_groups = {}
    subspaces = df[df['is_anomaly'] == 1]['subspaces']
    for sstr in subspaces:
        for s in subspace_to_list(sstr).keys():
            rel_subspaces_str.add(s)
    group_counter = 0
    for s in rel_subspaces_str:
        rel_features_groups[group_counter] = list(map(int, s.split()))
        group_counter += 1
    return rel_features_groups


def feature_is_rel(feature, rel_features):
    for rel_sub in rel_features.values():
        if feature in rel_sub:
            return True
    return False


def init_alg_feature_dict(alg, alg_feature_dict, rel_features):
    assert alg not in alg_feature_dict
    alg_feature_dict[alg] = {}
    for rel_sub in rel_features.values():
        for f in rel_sub:
            assert f not in alg_feature_dict[alg]
            alg_feature_dict[alg][f] = 0
    return alg_feature_dict


def calc_feature_count(rfile, rel_features):
    metric = 'roc_auc'
    alg_feature_dict = {}
    with open(rfile) as json_file:
        results = json.load(json_file)
        reps = len(results.keys())
        for rep, val in results.items():
            for alg, info in val[metric].items():
                if 'none' in alg:
                    continue
                sel_features = list(chain.from_iterable([x.split() for x in subspace_to_list(info['sel_features']).keys()]))
                sel_features = list(map(int, sel_features))
                if alg not in alg_feature_dict:
                    alg_feature_dict = init_alg_feature_dict(alg, alg_feature_dict, rel_features)
                for feature in sel_features:
                    if not feature_is_rel(feature, rel_features):
                        continue
                    alg_feature_dict[alg][feature] += 1
                    assert alg_feature_dict[alg][feature] <= reps
    return alg_feature_dict


def construct_alg_features_dataframes(alg_dim_feature_dict):
    alg_dim_df = {}
    for alg, dim_dict in alg_dim_feature_dict.items():
        fcount_df = pd.DataFrame(columns=list(dim_dict.keys()))
        for dim, fcount in dim_dict.items():
            fcount = dict(collections.OrderedDict(sorted(fcount.items())))
            for rel_f, rel_f_count in fcount.items():
                fcount_df.loc[rel_f, dim] = rel_f_count
        alg_dim_df[alg] = fcount_df
    return alg_dim_df


def feature_count_df(dir_path):
    result_files = get_results_files(dir_path, exclude='log', ending='json')
    alg_dim_feature_dict = {}
    for v in get_dataset_paths(dir_path):
        for log, dataset in v.items():
            df = pd.read_csv(dataset)
            rel_features = get_relevant_features(df)
            rfile = find_result_file(result_files, log)
            dim = df.shape[1]-2
            for alg, fcount in calc_feature_count(rfile, rel_features).items():
                if alg not in alg_dim_feature_dict:
                    alg_dim_feature_dict[alg] = {}
                alg_dim_feature_dict[alg][dim] = fcount
    return construct_alg_features_dataframes(alg_dim_feature_dict)

