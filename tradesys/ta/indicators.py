from typing import List , Tuple 
import math  



class Indicators:
    @staticmethod
    def ema(values: List[float], period:int) -> List[float]:
        """  EMA trend """
        if len(values) < period or period <= 0:
            return [float("nan")] * len(values)

        multiplier = 2.0/ (period + 1.0)
        ema_values = [float("nan")] * (period - 1)

        #init with SMA
        sma = sum(values[: period]) / period 
        ema_values.append(sma)

        for price in values[period:]:
            new_ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(new_ema)


    @staticmethod 
    def rsi(closes: List[float], period: int=14) -> List[float]:
        """ relative strength index using Wilder's smoothing """

        if len(closes) <= period:
            return [float("nan")] * len(closes)

        deltas = [closes[i] -  closes[i-1] for i in range(1, len(closes))]
        gains = [max(d, 0.0) for d in deltas]
        losses = [abs(min(d,0.0)) for d in deltas]

        rsi_series = [float("nan")] * period 
        avg_gain = sum(gains[:period])/period 
        avg_loss = sum(losses[:period]) / period 

        def _calc(ag: float , al: float) -> float:
            if al == 0.0:
                return 1000.0 if ag>0 else 50.0 
            rs = ag/al 
            return 100.0 - (100.0/(1.0 + rs))

        rsi_series.append((_calc(avg_gain, avg_loss)))

        for i in range(period , len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            rsi_series.append(_calc(avg_gain, avg_loss))

        return rsi_series 

    @staticmethod
    def vwap(highs: List[float], lows: List[float], closes:List[float], volumes:List[float]) -> List[float]:
        n = len(closes)
        if not (len(highs) == len(lows) == n == len(volumes)) or n == 0:
            raise ValueError("All arrays must be non-empty and of identical length.")

        comulative_tp_vol = 0.0 
        comulative_vol = 0 
        vwap_series = []

        for h , l , c, v in zip(highs , lows , closes , volumes):
            typical_price = (h+l+c) / 3.0 
            comulative_tp_vol += typical_price * v 
            comulative_vol +=v 
            vwap_series.append(comulative_tp_vol/comulative_vol if comulative_vol > 0 else typical_price)

        return vwap_series