from typing import Callable, Any

def compose(*funcs: Callable) -> Callable:
    """
    Композиция функций: f(g(h(x))). 
    Применяет функции справа налево.
    """
    def inner(x: Any) -> Any:
        result = x
        for func in reversed(funcs):
            result = func(result)
        return result
    return inner

def pipe(x: Any, *funcs: Callable) -> Any:
    """
    Конвейер (pipeline): f(x) | g | h. 
    Применяет функции слева направо.
    """
    result = x
    for func in funcs:
        result = func(result)
    return result
