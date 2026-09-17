from enum import Enum 
from dataclasses import dataclass 


class MarketRegime(Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY_PANIC = "HIGH_VOLATILITY_PANIC" 


@dataclass
class RegimePolicy:
    regime: MarketRegime 
    grid_spacing_multiplier: float 
    max_pyramiding_levels = int 
    allow_new_entries = bool 
    force_liquidation: bool 


class MacroRegimeEngine :
    def __init__(self, vix_crisis_threshold: float = 24.0 , vix_calm_threshold: float =14.0):
        self.vix_crisis_threshold = vix_crisis_threshold
        self.vix_calm_threshold = vix_calm_threshold

    def evaluate_regime(self, proxy_vix:float, index_close: float , index_fast_ema:float) -> RegimePolicy :

        # Case when market is very volatile 
        if proxy_vix>= self.vix_crisis_threshold:
            return RegimePolicy(
                regime= MarketRegime.HIGH_VOLATILITY_PANIC, 
                grid_spacing_multiplier=2.5, #widen the grid 
                max_pyramiding_levels = 0 , # disable pyraqmiding 
                allow_new_entries = False , # Halt any new orders 
                force_liquidation=False  
            )

        #directional trends
        trend_delta_pct = (index_close - index_fast_ema) / index_fast_ema

        if trend_delta_pct > 0.005:
            return RegimePolicy(
                regime=MarketRegime.TRENDING_BULL,
                grid_spacing_multiplier=1.0,
                max_pyramiding_levels=3,
                allow_new_entries=True,
                force_liquidation=False
            )
        elif trend_delta_pct < -0.005:
            return RegimePolicy(
                regime=MarketRegime.TRENDING_BEAR,
                grid_spacing_multiplier=1.0,
                max_pyramiding_levels=3,
                allow_new_entries=True,
                force_liquidation=False
            )
        else:
            # Low vol, oscillating market: Ideal for Mean Reverting Grid
            return RegimePolicy(
                regime=MarketRegime.RANGE_BOUND,
                grid_spacing_multiplier=0.8,  # Tighter grid
                max_pyramiding_levels=1,
                allow_new_entries=True,
                force_liquidation=False
            )