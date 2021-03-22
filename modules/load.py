from .db_utils import get_connection
import pandas as pd
import numpy as np
from .custom import rev_dict_replace
import os
import glob
from joblib import dump, load
import datetime

# Global variables
SEGMENT_LIST = ["Emerging", "SMB", "Mid-Market", "Enterprise"]
SEGMENT_ENCODE_MAP = dict(zip(SEGMENT_LIST, list(range(4))))
SEGMENT_REPLACE_MAP = {"Unknown": np.nan, "Key": "Enterprise"}

QUANTILE_UPPER_RANGE = 0.98
QUANTILE_LOWER_RANGE = 0.02

NUMERIC_NON_INDICATORS = [
    "total_annual_volume",
    "total_annual_fcl_volume",
    "total_annual_air_volume",
    "total_annual_lcl_volume",
    "piers_shipment_count",
    "piers_total_teu",
    "piers_nvo_teu",
    "raw_piers_total_teu",
    "raw_piers_nvo_teu",
    "raw_piers_pct_nvo",
    "raw_piers_estimated_commodity_value",
]

LEAD_SOURCE_REVERSE_MAP = {
    "Organic Website": [
        "Organic Search",
        "Organic Social",
        "Web",
        "Web-Referral",
        "Affiliate",
    ],
    "Sales Generated": [
        "List Import",
        "Sales Generated",
        "Flexport Generated",
        "Partner",
        "Core",
    ],
    "Paid": ["Paid Search", "Paid Social", "Display Advertising"],
    "Other":
    ["Other Inbound", "Referrals", "Inbound", "Event", "Marketing Ops"],
}

TERRITORY_BUCKET_MAP = {
    "EMEA":
    ["UKI (EMEA)", "DACH", "Benelux", "EMEA", "Scandinavia", "Netherlands"],
    "ROW": ["APAC", "LATAM", "Rest of World", "China", "HK", "Caribbean"],
    "Northeast": ["Northeast", "NY 1", "NY 2", "NY 3"],
    "Northwest": ["Northwest", "SF 1", "SF 2", "SF 3"],
    "Midwest": ["Midwest"],
    "Southeast": ["Southeast"],
    "Southwest": ["Southwest", "LA 1", "LA 2"],
    "Canada": ["Canada"],
}

IMPORT_EXPORT_CAT_MAP = {
    "Importer and Exporter": "Importer & Exporter",
    "G": np.nan
}

PREPROCESS_DROP_COLS = [
    "client_id",
    "salesforce_account_id",
    "company_name",
    "first_shipment_accepted_at",
    "fy_shipments",
    "first_shipment_quarter",
    "first_shipment_month",
    "import_or_exporter_Importer & Exporter",
]

ECOMMERCE_SERVICES = [
    "Shopify Plus", "BigCommerce", "DemandWare", "Magneto Enterprise"
]

# Relative paths (relative to the notebook!)
NAICS_DNB_MAP_PATH = "./data/naics_dnb_map.csv"
ZOOMINFO_MAP_PATH = "./data/zoominfo_dnb_map.csv"
FP_INDUSTRY_MAP_PATH = "./data/fp_industry_dnb_map.csv"
SAVED_MODELS_PATH = "./models/"


def load_data(filename: str):

    # Get the database connection and cursor objects
    conn, cur = get_connection()

    # Use a context manager to open and close connection and files
    with conn:

        # Open the query.sql file
        with open(filename, "r") as q:

            # Save contents of query.sql as string
            query_str = q.read()

        # Use the read_sql method to get the data from Snowflake into a
        # Pandas dataframe
        df = pd.read_sql(query_str, conn)

    # Make all the columns lowercase
    df.columns = map(str.lower, df.columns)

    # Input the groupings for the NAICS codes
    naics_codes_df = pd.read_csv(NAICS_DNB_MAP_PATH, dtype=str)

    # Join ancillary data to main dataframe
    df["naics2"] = df["dnb_naics"].str[:2]
    df = df.merge(naics_codes_df,
                  how="left",
                  left_on="naics2",
                  right_on="code").rename(columns={"code": "naics_code"})

    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:

    # DNB Industry mappings
    zoominfo_map, fp_industry_map = (
        pd.read_csv(path, index_col=0).to_dict()["dnb_industry"]
        for path in [ZOOMINFO_MAP_PATH, FP_INDUSTRY_MAP_PATH])

    df["dnb_industry"] = (df["dnb_industry"].combine_first(
        df["industry_zoominfo"].replace(zoominfo_map)).combine_first(
            df["industry"].replace(fp_industry_map)))

    # Drop industry code columns
    df = df.drop(columns=["naics2", "dnb_naics", "naics_code"])

    print(f"Initial table dimensions: {df.shape}")

    # Filter out clients with null net revenue
    df = df[df["actual_net_revenue"].notnull()]

    # Bucket territories
    df["flexport_territory"] = df["flexport_territory"].apply(
        rev_dict_replace, args=[TERRITORY_BUCKET_MAP])

    # Create boolean indicator for E-commerce service features
    df["uses_ecommerce_service"] = df["wholesale_partners"].str.contains(
        "|".join(ECOMMERCE_SERVICES), na=False)

    # Separate out E-commerce services from rest of wholesale partner options
    df["has_wholesale_partners_non_ecommerce"] = (
        (df["wholesale_partners"].notnull() * 1) -
        df["uses_ecommerce_service"]) == 1

    # Logic for encoding import / export status
    df["import_or_exporter"] = df["import_or_exporter"].replace(
        IMPORT_EXPORT_CAT_MAP)
    df = pd.get_dummies(df, columns=["import_or_exporter"])
    mask = df["import_or_exporter_Importer & Exporter"] == 1
    df.loc[mask,
           ("import_or_exporter_Exporter", "import_or_exporter_Importer")] = 1

    # Filter for clients with lifetime < 365 days & within past 3 years
    cutoff_date = pd.to_datetime("today") - pd.Timedelta(days=365)
    three_year_cutoff = pd.to_datetime("today") - datetime.timedelta(days=365 *
                                                                     3)
    df = df[(df["first_shipment_accepted_at"] >= three_year_cutoff)
            & (df["first_shipment_accepted_at"] < cutoff_date)]

    # Remove outliers within each segment
    filtered_df = pd.DataFrame()
    for segment in list(df["segment"].unique()):
        temp_df = df[df["segment"] == segment].copy()
        temp_df = temp_df[
            (temp_df["actual_net_revenue"] >
             temp_df["actual_net_revenue"].quantile(QUANTILE_LOWER_RANGE))
            & (temp_df["actual_net_revenue"] <
               temp_df["actual_net_revenue"].quantile(QUANTILE_UPPER_RANGE))]
        filtered_df = filtered_df.append(temp_df)
    df = filtered_df.copy()

    # Encode 'Unknown' segments as nulls; encode known segments as integers
    df = (df.replace({
        "segment": SEGMENT_REPLACE_MAP
    }).replace({
        "segment": SEGMENT_ENCODE_MAP
    }).dropna(subset=["segment"]))

    # Binning lead sources
    df["lead_source"] = df["lead_source"].apply(rev_dict_replace,
                                                args=[LEAD_SOURCE_REVERSE_MAP])

    # Drop columns ID, misc. columns, leakage data
    df = df.drop(columns=PREPROCESS_DROP_COLS)

    # Cast categorical variables
    df = pd.concat(
        [
            df.select_dtypes([], ["object"]),
            df.select_dtypes(["object"]).apply(pd.Series.astype,
                                               dtype="category"),
        ],
        axis=1,
    ).reindex(df.columns, axis=1)

    # Remove aberrant revenue or cost accounts
    df = df.query("not invoice_total_revenue <= 0"
                  "and not bill_total_sans_passthrough <= 0")

    print(f"Final table dimensions: {df.shape}")

    return df


# Save pickled sklearn models
def model_saver(model, custom_prefix="model_"):
    model_filename = os.path.join(
        SAVED_MODELS_PATH,
        custom_prefix + f"({datetime.datetime.now()})" + ".skmodel")
    dump(model, model_filename)
    print("Model successfully saved!", model_filename)


# Load pickled sklearn models
def model_loader(model_filename: str = None, path=SAVED_MODELS_PATH):
    # Choose latest trained model
    model_dir_list = glob.glob(path + "*")
    latest_model_filename = min(model_dir_list, key=os.path.getctime)
    print(f"Model chosen: {latest_model_filename}")

    if not model_filename:
        return load(latest_model_filename)
    else:
        return load(model_filename)
