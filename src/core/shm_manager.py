
from multiprocessing import shared_memory
import logging

logger = logging.getLogger(__name__)

class SHMManager:
    def __init__(self, name="prices_shm", create=True):
        self.name = name
        # [CS2_Price, Rust_Price, TF2_Price, Dota_Price]
        self.init_data = [0.0, 0.0, 0.0, 0.0] 
        self.sl = None
        if create:
            self._create()
        else:
            self._attach()

    def _create(self):
        try:
            self.sl = shared_memory.ShareableList(self.init_data, name=self.name)
            logger.info(f"SHM created: {self.name}")
        except FileExistsError:
            logger.warning(f"SHM {self.name} exists, attaching...")
            self._attach()

    def _attach(self):
        try:
            self.sl = shared_memory.ShareableList(name=self.name)
        except FileNotFoundError:
             # Fallback if attach fails but should have created, or race condition
             self.sl = shared_memory.ShareableList(self.init_data, name=self.name)

    def update_prices(self, cs2=None, rust=None, tf2=None, dota=None):
        if cs2 is not None: self.sl[0] = float(cs2)
        if rust is not None: self.sl[1] = float(rust)
        if tf2 is not None: self.sl[2] = float(tf2)
        if dota is not None: self.sl[3] = float(dota)

    def get_prices(self):
        return {
            "CS2": self.sl[0],
            "Rust": self.sl[1],
            "TF2": self.sl[2],
            "Dota": self.sl[3]
        }

    def close(self):
        if self.sl:
            self.sl.shm.close()

    def unlink(self):
        if self.sl:
            self.sl.shm.unlink()
