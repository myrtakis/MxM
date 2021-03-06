from scipy.io import loadmat
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from arff2pandas import a2p
from pathlib import Path


anomaly_column = 'is_anomaly'


def convert_arff_to_csv(path, split_cols_to_char=None, savedir=None):
    with open(path) as f:
        df = a2p.load(f)
    if split_cols_to_char is not None:
        cols = [col.split(split_cols_to_char)[0] for col in df.columns]
        cols[-1] = anomaly_column
        df = df.set_axis(cols, axis=1, inplace=False)
    df = preprocess(df, anomaly_column)
    if savedir is not None:
        savedir = Path(savedir, Path(path).stem)
    else:
        savedir = path
    df.to_csv(savedir, index=False)
    return df


def convert_mat_to_csv(path, savedir=None):
    mat = loadmat(path)
    vars = np.arange(mat['X'].shape[1]+1)
    vars = ['Var' + str(v) for v in vars]
    vars[-1] = anomaly_column
    csv = np.hstack((mat['X'], mat['y']))
    path = path.replace('mat', 'csv')
    df = pd.DataFrame(csv, columns=vars)
    df = preprocess(df, anomaly_column)
    if savedir is not None:
        savedir = Path(savedir, Path(path).stem)
    else:
        savedir = path
    df.to_csv(savedir, index=False)
    return df


def unify_format_of_df(path, savedir=None):
    df = pd.read_csv(path)
    cols = list(df.columns)
    cols[-1] = anomaly_column
    df.columns = cols
    class_counts = df[anomaly_column].value_counts()
    if 0 not in list(class_counts) and 1 not in list(class_counts):
        df[anomaly_column] = df[anomaly_column].replace([class_counts.index[np.argmax(list(class_counts))]], 0)
        df[anomaly_column] = df[anomaly_column].replace([class_counts.index[np.argmin(list(class_counts))]], 1)
    df = preprocess(df, anomaly_column)
    if savedir is not None:
        savedir = Path(savedir, Path(path).stem)
    else:
        savedir = path
    df.to_csv(savedir, index=False)
    return df


def preprocess(df, target_column, subspace_column=None):
    df = remove_nan_columns(df, target_column)
    df = remove_nan_rows(df)
    df = remove_features_of_single_value(df, target_column)
    df = remove_duplicates(df)
    df = df.apply(pd.to_numeric)
    df = standarization(df, target_column, subspace_column)
    assert not df.isnull().values.any()
    return df


def min_max_normalization(df, target_col_name, subspace_col_name=None):
    scaler = MinMaxScaler()
    X = df.drop(columns=[target_col_name])
    if subspace_col_name is not None:
        X = df.drop(columns=[subspace_col_name])
        ground_truth = df.loc[:, [target_col_name, subspace_col_name]]
    else:
        ground_truth = df.loc[:, [target_col_name]]
    X_scaled = scaler.fit_transform(X.values)
    X = pd.DataFrame(X_scaled, columns=X.columns)
    print('Dataframe normalized using MinMax normalization')
    return pd.concat([X, ground_truth], axis=1)


def standarization(df, target_col_name, subspace_col_name=None):
    standar = StandardScaler()
    X = df.drop(columns=[target_col_name])
    if subspace_col_name is not None:
        X = df.drop(columns=[subspace_col_name])
        ground_truth = df.loc[:, [target_col_name, subspace_col_name]]
    else:
        ground_truth = df.loc[:, [target_col_name]]
    X_scaled = standar.fit_transform(X.values)
    print('Dataframe standarized using Z-score')
    return pd.DataFrame(np.concatenate((X_scaled, ground_truth.values), axis=1), columns=df.columns)


def remove_nan_columns(df, target_column):
    y = df[target_column]
    df = df.drop(columns=[target_column])
    nan_cols = df.columns[df.isna().any()].tolist()
    print(len(nan_cols), 'columns contained NaN and removed')
    if len(nan_cols) > 0:
        df = df.drop(columns=nan_cols)
    return pd.concat([df, y], axis=1)


def remove_nan_rows(df):
    old_row_num = df.shape[0]
    df = df.dropna()
    print(old_row_num - df.shape[0], 'rows contained NaN and removed')
    return df.dropna()


def remove_features_of_single_value(df, target_column):
    y = df[target_column]
    df = df.drop(columns=[target_column])
    unq = df.nunique()
    one_val_columns = list(unq[unq == 1].index)
    print(len(one_val_columns), 'contained were single valued and removed')
    if len(one_val_columns) > 0:
        df = df.drop(columns=one_val_columns)
    return pd.concat([df, y], axis=1)


def remove_duplicates(df):
    old_rows = df.shape[0]
    df = df.drop_duplicates(keep='last')
    print(old_rows - df.shape[0], 'rows were duplicated and removed')
    return df
