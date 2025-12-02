from typing import Union, Generic, TypeVar,Callable
T = TypeVar('T')
U = TypeVar('U')
E = TypeVar('E')
class Maybe (Generic[T]):
    def __init__(self, value: Union[T,None]):
        self._value = value
    @staticmethod
    def some(value: T) -> "Maybe[T]":
        return Maybe(value)
    @staticmethod
    def nothing() -> "Maybe[None]":
        return Maybe(None)
    def is_some(self) -> bool:
        return self._value is not None
    def map(self, func: Callable[[T], U]) -> "Maybe[U]":
        if self.is_some():
            return Maybe.some(func(self._value))  # type: ignore
        else:
            return Maybe.nothing()
    def bind(self, func: Callable[[T], "Maybe[U]"]) -> "Maybe[U]":
        if self.is_some():
            return func(self._value)  # type: ignore
        else:
            return Maybe.nothing()
    def get_or_else(self, default: U) -> Union[T, U]:
        return self._value if self.is_some() else default
class Either(Generic[E, T]):
    def __init__(self, is_right: bool, value: Union[E, T]):
        self.is_right = is_right
        self._value = value

    @staticmethod
    def right(value: T) -> "Either[E, T]":
        return Either(True, value)

    @staticmethod
    def left(value: E) -> "Either[E, T]":
        return Either(False, value)

    def map(self, f: Callable[[T], U]) -> "Either[E, U]":
        if self.is_right:
            try:
                return Either.right(f(self._value))
            except Exception as e:
                return Either.left(e)
        return Either.left(self._value)

    def bind(self, f: Callable[[T], "Either[E, U]"]) -> "Either[E, U]":
        if self.is_right:
            return f(self._value)
        return Either.left(self._value)

    def get_or_else(self, default: U) -> Union[T, U]:
        return self._value if self.is_right else default
