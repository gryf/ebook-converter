from ebook_converter.polyglot.builtins import is_py3
if is_py3:
    from functools import lru_cache
else:
    from backports.functools_lru_cache import lru_cache


lru_cache
