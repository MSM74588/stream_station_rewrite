from abc import ABC, abstractmethod
from typing import Optional, Dict, Literal

from app.models import PlayerInfo

class MediaPlayerBase(ABC):
    type: str

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
