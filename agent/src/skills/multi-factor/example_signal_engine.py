"""多因子截面排名选股信号引擎。

对多只股票计算动量/波动率/量比等因子，截面标准化后综合打分，
选取 TopN 等权做多。纯 pandas 实现。
"""

from typing import Dict, List

import numpy as np
import pandas as pd


def zscore_cross_section(series_map: Dict[str, float]) -> Dict[str, float]:
    """对截面数据做 Z-score 标准化。

    Args:
        series_map: 标的代码到因子值的映射。

    Returns:
        标准化后的映射（均值 0，标准差 1）。
    """
    vals = [v for v in series_map.values() if not np.isnan(v)]
    if len(vals) < 2:
        return {k: 0.0 for k in series_map}
    mean = np.mean(vals)
    std = np.std(vals, ddof=1)
    if std < 1e-12:
        return {k: 0.0 for k in series_map}
    return {k: (v - mean) / std if not np.isnan(v) else 0.0 for k, v in series_map.items()}


def compute_ic_weights(
    ic_summaries: Dict[str, Dict[str, float]],
    metric: str = "ir",
    normalize: bool = True,
) -> Dict[str, float]:
    """Derive factor weights from factor_analysis IC summaries.

    Args:
        ic_summaries: Mapping factor_name -> {"ic_mean":..., "ir":..., "ic_std":...}
            as produced by factor_analysis_tool's ic_summary.json.
        metric: Which IC metric to use as weight: "ir" (IR = ic_mean/ic_std, default)
            or "ic_mean". Negative IC naturally yields negative weight (reversal).
        normalize: If True, scale so sum(|w|)==1.

    Returns:
        Dict factor_name -> normalized weight. Falls back to equal-weight if
        all IR are zero/NaN or ic_summaries empty.

    Example:
        >>> summaries = {"momentum": {"ir": 0.8}, "reversal": {"ir": -0.3}, "volatility": {"ir": 0.5}}
        >>> compute_ic_weights(summaries)
        {"momentum": 0.5, "reversal": -0.1875, "volatility": 0.3125}
    """
    if not ic_summaries:
        return {}
    raw = {}
    for name, summ in ic_summaries.items():
        v = summ.get(metric, 0.0)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            v = 0.0
        raw[name] = float(v)
    total_abs = sum(abs(v) for v in raw.values())
    if total_abs < 1e-12:
        # All zero → equal-weight fallback
        n = len(raw)
        return {k: 1.0 / n for k in raw} if n else {}
    if normalize:
        return {k: v / total_abs for k, v in raw.items()}
    return raw


class SignalEngine:
    """多因子截面排名信号引擎。

    计算动量、反转、波动率、量比四个因子，截面标准化后等权打分，
    选 TopN 股票等权做多。

    Attributes:
        momentum_window: 动量回看窗口。
        vol_window: 波动率回看窗口。
        top_n: 选股数量。
        rebalance_freq: 调仓频率（交易日）。

    Example:
        >>> engine = SignalEngine(top_n=2, rebalance_freq=20)
        >>> signals = engine.generate(data_map)
    """

    def __init__(
        self,
        momentum_window: int = 20,
        vol_window: int = 20,
        top_n: int = 3,
        rebalance_freq: int = 20,
        factor_weights: Dict[str, float] | None = None,
    ):
        """初始化多因子引擎。

        Args:
            momentum_window: 动量回看窗口。
            vol_window: 波动率回看窗口。
            top_n: 选股数量。
            rebalance_freq: 调仓频率（交易日）。
            factor_weights: Optional dict mapping factor_name -> weight for IC-weighted synthesis.
                If None, equal-weight (1.0 per factor). Example from factor_analysis:
                {"momentum": 0.5, "reversal": -0.2, "volatility": 0.3} where weight = IR or ic_mean.
                Weights are auto-normalized to sum(|w|)=1 if sum != 0.
        """
        self.momentum_window = momentum_window
        self.vol_window = vol_window
        self.top_n = top_n
        self.rebalance_freq = rebalance_freq
        self.factor_weights = factor_weights

    def _compute_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算单只股票的因子值。

        Args:
            df: OHLCV DataFrame。

        Returns:
            包含各因子列的 DataFrame。
        """
        close = df["close"]
        volume = df["volume"]
        returns = close.pct_change()

        factors = pd.DataFrame(index=df.index)
        # 动量：过去 N 日累计收益（正向）
        factors["momentum"] = close / close.shift(self.momentum_window) - 1
        # 反转：过去 5 日收益（反向，取负数使"越低越好"变成"越高越好"）
        factors["reversal"] = -(close / close.shift(5) - 1)
        # 波动率：过去 N 日收益标准差（反向，取负数）
        factors["volatility"] = -returns.rolling(self.vol_window).std()
        # 量比：当日量 / N 日均量（正向）
        factors["volume_ratio"] = volume / volume.rolling(self.vol_window).mean()

        return factors

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """截面排名选股，TopN 等权做多。

        Args:
            data_map: 标的代码到 OHLCV DataFrame 的映射。

        Returns:
            标的代码到信号 Series 的映射（1/N = 入选，0 = 未入选）。
        """
        codes = list(data_map.keys())
        if len(codes) < 2:
            # 单只股票无法做截面排名
            return {code: pd.Series(0.0, index=df.index) for code, df in data_map.items()}

        # 计算所有股票的因子
        factor_map: Dict[str, pd.DataFrame] = {}
        for code, df in data_map.items():
            factor_map[code] = self._compute_factors(df)

        # 获取公共日期
        all_dates = sorted(set().union(*(f.index for f in factor_map.values())))
        date_index = pd.DatetimeIndex(all_dates)

        # Resolve factor weights: equal-weight or IC-weighted (normalized)
        if self.factor_weights:
            # Normalize so sum(|w|) == 1, preserving sign (IC may be negative)
            total_abs = sum(abs(v) for v in self.factor_weights.values())
            if total_abs > 1e-12:
                norm_weights = {k: v / total_abs for k, v in self.factor_weights.items()}
            else:
                norm_weights = {k: 1.0 / len(self.factor_weights) for k in self.factor_weights}
        else:
            norm_weights = {name: 1.0 for name in ["momentum", "reversal", "volatility", "volume_ratio"]}

        signals = {code: pd.Series(0.0, index=date_index) for code in codes}
        factor_names = [n for n in ["momentum", "reversal", "volatility", "volume_ratio"] if n in norm_weights]

        last_selected: List[str] = []
        for i, dt in enumerate(date_index):
            # 非调仓日，沿用上次信号
            if i % self.rebalance_freq != 0 and last_selected:
                weight = 1.0 / len(last_selected) if last_selected else 0.0
                for code in last_selected:
                    signals[code].at[dt] = weight
                continue

            # 调仓日：截面排名 (IC-weighted if factor_weights provided)
            composite_scores: Dict[str, float] = {}
            for factor_name in factor_names:
                w = norm_weights.get(factor_name, 1.0)
                raw_vals = {}
                for code in codes:
                    if dt in factor_map[code].index:
                        raw_vals[code] = factor_map[code].at[dt, factor_name]
                    else:
                        raw_vals[code] = np.nan
                z_vals = zscore_cross_section(raw_vals)
                for code in codes:
                    composite_scores[code] = composite_scores.get(code, 0.0) + w * z_vals.get(code, 0.0)

            # 排名取 TopN
            ranked = sorted(composite_scores.items(), key=lambda x: x[1], reverse=True)
            effective_n = min(self.top_n, len([s for _, s in ranked if not np.isnan(s)]))
            selected = [code for code, _ in ranked[:effective_n]]
            last_selected = selected

            if selected:
                weight = 1.0 / len(selected)
                for code in selected:
                    signals[code].at[dt] = weight

        # 对齐到原始索引
        result = {}
        for code, df in data_map.items():
            result[code] = signals[code].reindex(df.index).fillna(0.0)
        return result


if __name__ == "__main__":
    import requests

    def _fetch_okx(inst_id: str, bar: str = "1D", limit: int = 300) -> pd.DataFrame:
        """从 OKX API 获取 K 线数据。

        Args:
            inst_id: 交易对标识，如 "BTC-USDT"。
            bar: K 线周期。
            limit: 获取根数。

        Returns:
            OHLCV DataFrame。
        """
        resp = requests.get(
            "https://www.okx.com/api/v5/market/candles",
            params={"instId": inst_id, "bar": bar, "limit": str(limit)},
        )
        candles = resp.json()["data"]
        columns = ["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"]
        df = pd.DataFrame(reversed(candles), columns=columns)
        df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
        df = df.set_index("ts")
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        df["volume"] = df["vol"].astype(float)
        return df

    symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT"]
    data_map = {}
    for sym in symbols:
        print(f"Fetching {sym} ...")
        data_map[sym] = _fetch_okx(sym, bar="1D", limit=300)

    engine = SignalEngine(top_n=2, rebalance_freq=20)
    signals = engine.generate(data_map)

    for sym in symbols:
        sig = signals[sym]
        active = (sig > 0).sum()
        print(f"\n{sym}: selected {active}/{len(sig)} days")
        if active > 0:
            print(f"  Avg weight when selected: {sig[sig > 0].mean():.2%}")
