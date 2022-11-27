from datetime import datetime, timedelta, timezone
from typing import Callable, Literal, TypeAlias

from tcoreapi_mq.model import SOURCE_SYMBOLS

MarketDateType: TypeAlias = Literal[
    "US Index Futures",
    "FITX"
]


def get_epoch_sec_time(hour: int, minute: int = 0) -> int:
    return hour * 3600 + minute * 60


def _calc_market_date_us_index_futures(timestamp: datetime, epoch_sec_time: float) -> datetime:
    return datetime.combine(
        timestamp.date() + timedelta(0 if epoch_sec_time < get_epoch_sec_time(22) else 1),
        datetime.min.time()
    )


def _calc_market_date_fitx(timestamp: datetime, epoch_sec_time: float) -> datetime:
    return datetime.combine(
        timestamp.date() + timedelta(0 if epoch_sec_time < get_epoch_sec_time(22) else 1),
        datetime.min.time()
    )


_symbol_market_date_type_map: dict[str, MarketDateType] = {
    entry.symbol_complete: "US Index Futures"
    for entry in SOURCE_SYMBOLS
}

_calc_function_map: dict[MarketDateType, Callable[[datetime, float], datetime]] = {
    "US Index Futures": _calc_market_date_us_index_futures,
    "FITX": _calc_market_date_fitx,
}


def calc_market_date(timestamp: datetime, epoch_sec_time: float, symbol_complete: str) -> datetime:
    if calc_market_date_symbol := _calc_function_map.get(_symbol_market_date_type_map[symbol_complete]):
        return calc_market_date_symbol(timestamp, epoch_sec_time).replace(tzinfo=timezone.utc)

    raise ValueError(f"Symbol `{symbol_complete}` does not have market date calculation logic")
