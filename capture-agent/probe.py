"""CPU/RAM probe — decides which denoiser to use on this machine."""

from __future__ import annotations

import time

import psutil


class MachineProfile:
    def __init__(self) -> None:
        self.cpu_count = psutil.cpu_count(logical=True)
        self.ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        self.cpu_percent = psutil.cpu_percent(interval=1.0)
        self.use_deepfilter: bool = True

    def evaluate(self) -> str:
        """Return 'deepfilter' or 'rnnoise' based on machine capability."""
        if self.ram_gb < 4.0 or self.cpu_count < 4:
            self.use_deepfilter = False
        bench_score = self._cpu_bench()
        if bench_score < 200:
            self.use_deepfilter = False
        return "deepfilter" if self.use_deepfilter else "rnnoise"

    def _cpu_bench(self) -> float:
        """Quick 1-second float throughput benchmark."""
        start = time.monotonic()
        count = 0
        deadline = start + 1.0
        while time.monotonic() < deadline:
            _ = sum(i * i for i in range(1000))
            count += 1
        elapsed = time.monotonic() - start
        return count / elapsed if elapsed > 0 else 0

    def summary(self) -> dict:
        return {
            "cpu_count": self.cpu_count,
            "ram_gb": round(self.ram_gb, 1),
            "denoiser": self.evaluate(),
        }


if __name__ == "__main__":
    profile = MachineProfile()
    result = profile.summary()
    print(f"CPU cores: {result['cpu_count']}")
    print(f"RAM: {result['ram_gb']} GB")
    print(f"Selected denoiser: {result['denoiser']}")
