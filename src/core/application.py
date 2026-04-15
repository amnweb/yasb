from asyncio import AbstractEventLoop, Event

from PyQt6.QtWidgets import QApplication


class YASBApplication(QApplication):
    """
    Subclass of QApplication to provide type-safe access to application-wide
    asyncio loop and shutdown events.
    Might also be used to store other application-wide state.
    """

    def __init__(self, args: list[str]):
        super().__init__(args)
        self.loop: AbstractEventLoop | None = None
        self.close_event: Event | None = None
