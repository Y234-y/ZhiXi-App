import numpy as np
import pandas as pd


TIME_KEYWORDS = ["date", "time", "日期", "时间", "年", "月", "日", "dt", "timestamp"]
ID_KEYWORDS = ["id", "编号", "序号", "学号", "工号"]

def read_csv_smart(file):
    for enc in ["utf-8", "gbk", "gb18030", "utf-8-sig"]:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=enc)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    file.seek(0)
    return pd.read_csv(file, encoding="utf-8", errors="replace")

def load_single_file(file, sheet_name=None):
    name = file.name.lower()
    if name.endswith(".csv"):
        return read_csv_smart(file)
    df = pd.read_excel(file, sheet_name=sheet_name or 0, header=0)
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    return df

def detect_column_type(series: pd.Series, col_name: str = ""):
    if isinstance(series, pd.DataFrame):
        if series.shape[1] > 0: series = series.iloc[:, 0]
        else: return "empty"
    s = series.dropna()
    if len(s) == 0: return "empty"
    if pd.api.types.is_numeric_dtype(s):
        if s.nunique() / len(s) > 0.9 and any(k in str(col_name).lower() for k in ID_KEYWORDS):
            return "id"
        return "numeric"
    numeric_ratio = pd.to_numeric(s, errors="coerce").notna().mean()
    if numeric_ratio > 0.8: return "numeric"
    name_hint = any(kw in str(col_name).lower() for kw in TIME_KEYWORDS)
    has_sep = s.astype(str).str.contains(r"[-/:年月日]", regex=True).mean() > 0.5
    if name_hint or has_sep:
        dt_ratio = pd.to_datetime(s, errors="coerce").notna().mean()
        if dt_ratio > 0.8: return "datetime"
    unique_ratio = s.nunique() / len(s)
    if s.nunique() <= 50 or unique_ratio < 0.5: return "categorical"
    return "text"

def analyze_columns(df):
    return {c: detect_column_type(df[c], c) for c in df.columns}

# data_utils.py 里的清洗函数替换

def clean_dataframe(df, strip_space, na_strategy, drop_outliers):
    df = df.copy()
    
    # 1. 文本清洗
    if strip_space:
        df.columns = df.columns.str.strip()
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', np.nan)

    # 2. 缺失值处理
    if na_strategy == "删除包含缺失的行":
        df = df.dropna()
    elif na_strategy == "数值填均值":
        for col in df.select_dtypes(include=['number']).columns:
            df[col] = df[col].fillna(df[col].mean())
    elif na_strategy == "数值填中位数":
        for col in df.select_dtypes(include=['number']).columns:
            df[col] = df[col].fillna(df[col].median())

    # 3. 异常值处理 (3倍标准差剔除)
    if drop_outliers:
        for col in df.select_dtypes(include=['number']).columns:
            mean, std = df[col].mean(), df[col].std()
            if std > 0: # 防止除以0
                df = df[(df[col] >= mean - 3 * std) & (df[col] <= mean + 3 * std)]
    return df

def force_convert_numeric(df, col_types):
    df = df.copy()
    for col, t in col_types.items():
        if t == "numeric":
            df[col] = df[col].astype(str).str.extract(r'(-?\d+\.?\d*)')[0]
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df
