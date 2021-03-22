import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


def data_prep(
    df,
    target_cols=[
        "actual_net_revenue",
        "bill_total_sans_passthrough",
        "invoice_total_revenue",
    ],
    target_feature="actual_net_revenue",
):

    # Pull and check dataframe
    data = df.copy()
    assert target_feature in data.columns
    assert target_feature in target_cols

    # Pare down features as specified
    data = data.drop(
        [feature for feature in target_cols if feature != target_feature],
        axis=1)

    # Set up for training or prediction
    data = data[data[target_feature].notnull()]
    X = data.drop([target_feature], axis=1)
    y = data[target_feature]
    assert y.equals(data[target_feature])
    return X, y


class ZeroVariance(BaseEstimator, TransformerMixin):
    """
    Transformer to identify zero variance and optionally low variance features
    for removal
    This works similarly to the R caret::nearZeroVariance function
    """
    def __init__(self, near_zero=False, freq_cut=95 / 5, unique_cut=10):
        """
        near zero: boolean.
            False: remove only zero variance columns
            True: remove near zero and zero variance columns
        freq_cut: cutoff frequency ratio of most to second-most frequent values
        unique_cut: cutoff for percentage unique values
        """
        self.near_zero = near_zero
        self.freq_cut = freq_cut
        self.unique_cut = unique_cut

    def fit(self, X, y=None):
        self.zero_var = np.zeros(X.shape[1], dtype=bool)
        self.near_zero_var = np.zeros(X.shape[1], dtype=bool)
        n_obs = X.shape[0]

        for i, col in enumerate(X.T):
            # obtain values, counts of values and sort counts from
            # most to least frequent
            val_counts = np.unique(col, return_counts=True)
            counts = val_counts[1]
            counts_len = counts.shape[0]
            counts_sort = np.sort(counts)[::-1]

            # if only one value, is ZV
            if counts_len == 1:
                self.zero_var[i] = True
                self.near_zero_var[i] = True
                continue

            # ratio of most frequent / second most frequent
            freq_ratio = counts_sort[0] / counts_sort[1]
            # percent unique values
            unique_pct = (counts_len / n_obs) * 100

            if (unique_pct < self.unique_cut) and (freq_ratio > self.freq_cut):
                self.near_zero_var[i] = True

        return self

    def transform(self, X, y=None):
        if self.near_zero:
            return X.T[~self.near_zero_var].T
        else:
            return X.T[~self.zero_var].T

    def get_feature_names(self, input_features=None):
        if self.near_zero:
            return input_features[~self.near_zero_var]
        else:
            return input_features[~self.zero_var]


class FindCorrelation(BaseEstimator, TransformerMixin):
    """
    Remove pairwise correlations beyond threshold.
    This is not 'exact': it does not recalculate correlation
    after each step, and is therefore less expensive.
    """
    def __init__(self, threshold=0.9):
        self.threshold = threshold

    def fit(self, X, y=None):
        """
        Produce binary array for filtering columns in feature array.
        Remember to transpose the correlation matrix so is
        column major.

        Loop through columns in (n_features,n_features) correlation matrix.
        Determine rows where value is greater than threshold.

        For the candidate pairs, one must be removed. Determine which feature
        has the larger average correlation with all other features and remove
        it.
        """
        self.correlated = np.zeros(X.shape[1], dtype=bool)
        self.corr_mat = np.corrcoef(X.T)
        abs_corr_mat = np.abs(self.corr_mat)

        for i, col in enumerate(abs_corr_mat.T):
            corr_rows = np.where(col[i + 1:] > self.threshold)[0]
            avg_corr = np.mean(col)

            if len(corr_rows) > 0:
                for j in corr_rows:
                    if np.mean(abs_corr_mat.T[:, j]) > avg_corr:
                        self.correlated[j] = True
                    else:
                        self.correlated[i] = True

        return self

    def transform(self, X, y=None):
        """
        Mask the array with the features flagged for removal
        """
        return X.T[~self.correlated].T

    def get_feature_names(self, input_features=None):
        return input_features[~self.correlated]
