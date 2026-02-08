import logging
import os
import shutil
from subprocess import PIPE, Popen
from typing import NamedTuple

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication


class GpuData(NamedTuple):
    """GPU data returned by nvidia-smi query."""

    index: int
    utilization: int
    mem_total: int
    mem_used: int
    mem_free: int
    temp: int
    fan_speed: int
    power_draw: str


class GpuWorker(QThread):
    """GPU Worker thread."""

    _instance: "GpuWorker | None" = None
    data_ready = pyqtSignal(list)  # list[GpuData]
    _nvidia_smi_path: str | None = None

    @classmethod
    def get_instance(cls, update_interval: int) -> "GpuWorker":
        if cls._instance is None:
            cls._instance = cls(update_interval)
        return cls._instance

    def __init__(self, update_interval: int, parent=None):
        super().__init__(parent)
        self._running = True
        self._update_interval = update_interval
        app_inst = QApplication.instance()
        if app_inst is not None:
            app_inst.aboutToQuit.connect(self.stop)

    def stop(self):
        self._running = False
        GpuWorker._instance = None

    @classmethod
    def _get_nvidia_smi_path(cls) -> str:
        if cls._nvidia_smi_path is not None:
            return cls._nvidia_smi_path
        path = shutil.which("nvidia-smi")
        if path:
            cls._nvidia_smi_path = path
        else:
            cls._nvidia_smi_path = os.path.join(
                os.environ["SystemDrive"] + "\\", "Program Files", "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"
            )
        return cls._nvidia_smi_path

    def run(self):
        while self._running:
            try:
                gpu_data_list = self._query_nvidia_smi()
                if self._running:
                    self.data_ready.emit(gpu_data_list)
            except Exception as e:
                logging.error(f"Error in GPU worker: {e}")
                if self._running:
                    self.data_ready.emit([])
            self.msleep(self._update_interval)

    def _query_nvidia_smi(self) -> list[GpuData]:
        nvidia_smi = self._get_nvidia_smi_path()
        gpu = Popen(
            [
                nvidia_smi,
                "--query-gpu=index,utilization.gpu,memory.total,memory.used,memory.free,temperature.gpu,fan.speed,power.draw",
                "--format=csv,noheader,nounits",
            ],
            stdout=PIPE,
            stderr=PIPE,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        try:
            stdout, stderr = gpu.communicate(timeout=5)
        except Exception:
            if gpu.poll() is None:
                gpu.kill()
                gpu.wait()
            return []

        if gpu.returncode != 0 or not stdout:
            return []

        results = []
        for line in stdout.decode("utf-8").strip().split("\n"):
            fields = [f.strip() for f in line.split(",")]
            if len(fields) < 7:
                continue
            results.append(
                GpuData(
                    index=int(fields[0]),
                    utilization=int(fields[1]),
                    mem_total=int(fields[2]),
                    mem_used=int(fields[3]),
                    mem_free=int(fields[4]),
                    temp=int(fields[5]),
                    fan_speed=int(fields[6]) if fields[6].isdigit() else 0,
                    power_draw=fields[7].strip() if len(fields) > 7 else "0",
                )
            )
        return results
