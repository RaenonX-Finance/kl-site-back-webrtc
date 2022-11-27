from .futures import FuturesSymbol


SOURCE_SYMBOLS: list[FuturesSymbol] = [
    FuturesSymbol(exchange="CME", symbol="NQ"),
    FuturesSymbol(exchange="CME", symbol="ES"),
    FuturesSymbol(exchange="CBOT", symbol="YM"),
    FuturesSymbol(exchange="TWF", symbol="FITX"),
]

FUTURES_SECURITY_TO_SYM_OBJ: dict[str, FuturesSymbol] = {
    entry.security: entry for entry in SOURCE_SYMBOLS if isinstance(entry, FuturesSymbol)
}

FUTURES_SYMBOL_TO_SYM_OBJ: dict[str, FuturesSymbol] = {
    entry.symbol_complete: entry for entry in SOURCE_SYMBOLS if isinstance(entry, FuturesSymbol)
}
