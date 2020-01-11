import argparse
import pandas as pd
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np
from scipy.io import arff
from pathlib import Path


def arff_to_csv(arff_dataset_path):
    data = arff.loadarff(arff_dataset_path)
    df = pd.DataFrame(data[0])
    path = Path(arff_dataset_path)
    outputdir = path.parent
    basename = os.path.basename(path)
    file_name, ext = os.path.splitext(basename)
    outputfile = os.path.join(outputdir, file_name + '.csv')
    df.to_csv(outputfile, index=False)


def tsne_visualizer(dataset_path, savedir):
    fileslist = get_files(dataset_path)
    for f in fileslist:
        df = pd.read_csv(f)
        final_df = df.iloc[:, 0:df.shape[1]-2]
        feat_cols = list(range(final_df.shape[1]))
        final_df['y'] = df.iloc[:, df.shape[1]-1]
        final_df['label'] = final_df['y'].apply(lambda i: str(i))
        tsne_results = TSNE(n_components=2, random_state=0, perplexity=50).fit_transform(df.iloc[:, feat_cols])

        final_df['tsne-2d-one'] = tsne_results[:, 0]
        final_df['tsne-2d-two'] = tsne_results[:, 1]

        colors = ["#383838", "#FF0B04"]

        sns.scatterplot(
            x="tsne-2d-one", y="tsne-2d-two",
            hue="y",
            palette=sns.color_palette(colors),
            data=final_df,
            legend="full",
        )

        dataset_name = os.path.splitext(os.path.basename(f))[0]
        output = os.path.join(savedir, 'tsne_' + dataset_name + '.png')
        if not os.path.exists(savedir):
            os.makedirs(savedir)

        plt.title(dataset_name)
        plt.savefig(output, dpi=300)
        plt.clf()


def get_files(dir_path):
    fileslist = []
    if not os.path.isdir(dir_path):
        return [dir_path]
    allfiles = os.listdir(dir_path)
    for f in allfiles:
        if f.endswith('.csv'):
            fileslist.append(os.path.join(dir_path, f))
    return fileslist


def outlier_differences(diffs):
    data_diffs = diffs.split(',')
    for i in range(len(data_diffs)):
        for j in range(i+1, len(data_diffs)):
            d1 = data_diffs[i]
            d2 = data_diffs[j]
            df1 = pd.read_csv(d1)
            df2 = pd.read_csv(d2)
            diff = df1.shape[0] - list(np.array(df1['is_anomaly'].tolist()) - np.array(df2['is_anomaly'].tolist())).count(0)
            print(os.path.splitext(os.path.basename(d1))[0], os.path.splitext(os.path.basename(d2))[0], diff)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-tocsv', '--arfftocsv', help='Arff dataset path to convert to csv', default=None)
    parser.add_argument('-viz', '--visualise', help='Dataset or Dataset folder to visualize.', default=None)
    parser.add_argument('-sv', '--saveviz', help='Directory to save the image.', default=None)
    parser.add_argument('-diff', '--differences', default=None, help='-datadiff d1,d2,d3', type=str)
    args = parser.parse_args()
    if args.arfftocsv is not None:
        arff_to_csv(args.arfftocsv)
    if args.visualise is not None:
        tsne_visualizer(args.visualise, args.saveviz)
    if args.differences is not None:
        outlier_differences(args.differences)
