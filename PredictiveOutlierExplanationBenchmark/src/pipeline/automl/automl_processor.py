import collections
import numpy as np
from sklearn.model_selection import StratifiedKFold
from collections import OrderedDict
from pipeline.BbcCorrection import BBC
from pipeline.automl.automl_utils import save
from configpkg import SettingsConfig
from pipeline.automl.cv_classification import CV_Classification
from pipeline.automl.cv_feature_selection import CV_Fselection
from utils.shared_names import FileNames
from pipeline.ModelConfigsGen import generate_param_combs
from models.FeatureSelection import FeatureSelection
import pipeline.automl.automl_constants as automlconsts
from utils.ResultsWriter import ResultsWriter


class AutoML:

    __reps_fold_inds = None

    def __init__(self, output_dir):
        self.__output_dir = output_dir

    def run_with_explanation(self, reps_fold_inds, dataset, explanation, explanation_size):
        print('Running explanation', explanation)
        output_dir = ResultsWriter.add_explanation_size_to_path(self.__output_dir, explanation_size)
        explanation = list(map(int, explanation))
        assert len(explanation) <= explanation_size
        fsel = FeatureSelection({'id': 'explanation', 'params': None})
        fsel.set_features(explanation)
        fsel.set_time(.0)
        selected_features = dict.fromkeys(reps_fold_inds.keys())
        for k in selected_features.keys():
            selected_features[k] = dict.fromkeys(reps_fold_inds[k].keys(), [fsel])
        _, classifiers_conf_combs = generate_param_combs()
        best_model_trained, predictions_ordered = \
            CV_Classification(False, classifiers_conf_combs, output_dir, True). \
                run(reps_fold_inds, selected_features, dataset, explanation_size)
        best_model_trained = AutoML.__remove_bias(predictions_ordered, dataset.get_Y(), best_model_trained)
        print()
        return best_model_trained

    def run(self, dataset, knowledge_discovery, explanation=None):
        kfolds = min(SettingsConfig.get_kfolds(), AutoML.__get_rarest_class_count(dataset))
        assert kfolds > 1, kfolds
        if AutoML.__reps_fold_inds is None:
            AutoML.__reps_fold_inds = self.__create_folds_in_reps(kfolds, dataset, True)
        best_model_trained_per_expl_size = {}
        if explanation is not None:
            explanation_features_sorted = np.argsort(explanation)[::-1]
            for expl_size in automlconsts.EXPLANATION_SIZE:
                topk_explanation_features = list(explanation_features_sorted[0:expl_size])
                best_model_trained = self.run_with_explanation(AutoML.__reps_fold_inds, dataset,
                                                               topk_explanation_features, expl_size)
                best_model_trained_per_expl_size[expl_size] = best_model_trained
        else:
            print('------\nRunning PROTEAN pipeline')
            fsel_conf_combs, classifiers_conf_combs = generate_param_combs()
            selected_features = CV_Fselection(knowledge_discovery, fsel_conf_combs, kfolds).\
                run(AutoML.__reps_fold_inds, dataset)
            for expl_size, sel_features in selected_features.items():
                output_dir = ResultsWriter.add_explanation_size_to_path(self.__output_dir, expl_size)
                best_model_trained, predictions_ordered = \
                    CV_Classification(knowledge_discovery, classifiers_conf_combs, output_dir, False).\
                        run(AutoML.__reps_fold_inds, sel_features, dataset, expl_size)
                best_model_trained = AutoML.__remove_bias(predictions_ordered, dataset.get_Y(), best_model_trained)
                best_model_trained_per_expl_size[expl_size] = best_model_trained
            print()
        return best_model_trained_per_expl_size

    @staticmethod
    def __get_rarest_class_count(dataset):
        if not dataset.contains_pseudo_samples():
            assert dataset.get_pseudo_sample_indices_per_outlier() is None
            return int(min(collections.Counter(dataset.get_Y()).values()))
        else:
            assert dataset.last_original_sample_index() is not None
            assert dataset.get_pseudo_sample_indices_per_outlier() is not None
            return int(min(collections.Counter(dataset.get_Y()[:dataset.last_original_sample_index()]).values()))

    def __create_folds_in_reps(self, kfolds, dataset, save_option):
        reps_folds_inds = OrderedDict()
        for r in range(automlconsts.REPETITIONS):
            skf = StratifiedKFold(n_splits=kfolds, shuffle=True)
            folds_inds = AutoML.__indices_in_folds(dataset, skf)
            reps_folds_inds[r] = folds_inds
            if save_option:
                save(folds_inds, [self.__output_dir, FileNames.indices_folder], r,
                     lambda o: o.tolist() if isinstance(o, np.ndarray) else o)
        return reps_folds_inds

    @staticmethod
    def __indices_in_folds(dataset, skf):
        folds_inds = collections.OrderedDict()
        fold_id = 1
        if dataset.contains_pseudo_samples() and automlconsts.GROUPING:
            X = dataset.get_X()[:dataset.last_original_sample_index()]
            Y = dataset.get_Y()[:dataset.last_original_sample_index()]
        else:
            X = dataset.get_X()
            Y = dataset.get_Y()
        for train_inds, test_inds in skf.split(X, Y):
            if dataset.contains_pseudo_samples() and automlconsts.GROUPING:
                ps_indices_per_outlier = dataset.get_pseudo_sample_indices_per_outlier()
                train_inds = AutoML.__add_pseudo_samples_inds(ps_indices_per_outlier, train_inds)
                test_inds = AutoML.__add_pseudo_samples_inds(ps_indices_per_outlier, test_inds)
            folds_inds[fold_id] = {'train_indices': train_inds, 'test_indices': test_inds}
            fold_id += 1
        return folds_inds

    @staticmethod
    def __remove_bias(predictions, true_labels, best_models):
        for m_id in best_models:
            perf, ci = BBC(true_labels, predictions, m_id).correct_bias()
            best_models[m_id].set_effectiveness(perf, m_id, best_models[m_id].get_conf_id())
            best_models[m_id].set_confidence_intervals(ci, best_models[m_id].get_conf_id())
        return best_models

    @staticmethod
    def __add_pseudo_samples_inds(pseudo_samples_inds_per_outlier, inds):
        assert pseudo_samples_inds_per_outlier is not None
        common_inds = set(pseudo_samples_inds_per_outlier.keys()).intersection(inds)
        assert len(common_inds) > 0
        for ind in common_inds:
            ps_samples_range = pseudo_samples_inds_per_outlier[ind]
            ps_samples_inds = np.arange(ps_samples_range[0], ps_samples_range[1])
            inds = np.concatenate((inds, ps_samples_inds))
        return inds
