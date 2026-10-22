from enum import Enum, EnumMeta


class MetaEvent(EnumMeta):
    def __contains__(cls, item: object) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        return True


class Event(Enum, metaclass=MetaEvent):
    pass
