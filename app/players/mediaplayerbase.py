from abc import ABC, abstractmethod
from typing import Optional, Dict, Literal
from app.models import PlayerInfo


class MediaPlayerBase(ABC):
    type: str
    unloaded: bool = False  # Optional, but helpful if tracking unload state

    def __enter__(self):
        """
        Allow use in a context manager (`with` statement).
        Override in subclass if needed.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ensure resources are released when exiting context.
        """
        self.unload()

    def unload(self):
        """
        Optional: Cleanup method to be overridden by subclasses.
        """
        self.unloaded = True

    @abstractmethod
    def play(self): ...

    @abstractmethod
    def pause(self): ...

    @abstractmethod
    def stop(self): ...

    @abstractmethod
    def set_repeat(self) -> Literal["on", "off"]: ...

    @abstractmethod
    def set_volume(self, volume: int): ...

    @abstractmethod
    def get_volume(self) -> Optional[int]: ...

    @abstractmethod
    def get_progress(self) -> Optional[int]: ...

    @abstractmethod
    def get_state(self) -> Optional[PlayerInfo]: ...
