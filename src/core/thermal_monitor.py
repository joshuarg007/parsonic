"""
Thermal monitoring and safety system for Parsonic.

Monitors CPU and GPU temperatures, automatically pausing AI operations
when thresholds are exceeded to prevent thermal damage.

Ported from Vesper's thermal safety system.
"""

import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, List
from enum import Enum


class ThermalState(Enum):
    """Current thermal state of the system."""
    SAFE = "safe"           # All temps normal
    WARNING = "warning"     # Elevated but OK to continue
    DANGER = "danger"       # Pause AI operations
    CRITICAL = "critical"   # Kill AI processes


@dataclass
class ThermalThresholds:
    """Temperature thresholds in Celsius."""
    warn: float
    pause: float
    kill: float
    resume: float


@dataclass
class ThermalConfig:
    """Thermal monitoring configuration."""
    # CPU thresholds (Ryzen 9 / high-end desktop)
    cpu: ThermalThresholds = field(default_factory=lambda: ThermalThresholds(
        warn=80.0,
        pause=85.0,
        kill=87.0,
        resume=65.0
    ))
    # GPU thresholds (RTX 4090 / high-end GPU)
    gpu: ThermalThresholds = field(default_factory=lambda: ThermalThresholds(
        warn=75.0,
        pause=80.0,
        kill=85.0,
        resume=65.0
    ))
    # Polling interval in seconds
    poll_interval: float = 3.0


@dataclass
class ThermalStatus:
    """Current thermal readings and state."""
    cpu_temp: Optional[float] = None
    gpu_temp: Optional[float] = None
    gpu_vram_used_mb: int = 0
    gpu_vram_total_mb: int = 0
    gpu_utilization: int = 0
    state: ThermalState = ThermalState.SAFE
    reason: str = ""
    timestamp: float = 0.0

    @property
    def gpu_vram_percent(self) -> float:
        if self.gpu_vram_total_mb == 0:
            return 0.0
        return (self.gpu_vram_used_mb / self.gpu_vram_total_mb) * 100

    @property
    def is_safe(self) -> bool:
        return self.state in (ThermalState.SAFE, ThermalState.WARNING)

    @property
    def should_pause(self) -> bool:
        return self.state in (ThermalState.DANGER, ThermalState.CRITICAL)

    @property
    def should_kill(self) -> bool:
        return self.state == ThermalState.CRITICAL


class ThermalMonitor:
    """
    Monitors system temperatures and enforces thermal safety.

    Usage:
        monitor = ThermalMonitor()
        monitor.start()

        # Check before AI operations
        if monitor.is_safe():
            # Do AI work
        else:
            # Wait or skip

        monitor.stop()
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - only one monitor per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[ThermalConfig] = None):
        if self._initialized:
            return

        self._initialized = True
        self.config = config or ThermalConfig()
        self._status = ThermalStatus()
        self._callbacks: List[Callable[[ThermalStatus], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._thermal_state = {
            'warning_shown': False,
            'paused': False,
            'killed': False,
            'last_kill_time': 0.0
        }

    def start(self):
        """Start the thermal monitoring thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[THERMAL] Monitor started")

    def stop(self):
        """Stop the thermal monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        print("[THERMAL] Monitor stopped")

    def get_status(self) -> ThermalStatus:
        """Get current thermal status."""
        return self._status

    def is_safe(self) -> bool:
        """Check if system is thermally safe for AI operations."""
        return self._status.is_safe

    def add_callback(self, callback: Callable[[ThermalStatus], None]):
        """Add callback for thermal state changes."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[ThermalStatus], None]):
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        while self._running:
            try:
                self._update_status()
                self._check_thresholds()
                self._notify_callbacks()
            except Exception as e:
                print(f"[THERMAL] Monitor error: {e}")

            time.sleep(self.config.poll_interval)

    def _update_status(self):
        """Update thermal readings from system."""
        self._status.timestamp = time.time()

        # Get CPU temperature
        self._status.cpu_temp = self._get_cpu_temp()

        # Get GPU stats
        gpu_stats = self._get_gpu_stats()
        if gpu_stats:
            self._status.gpu_temp = gpu_stats.get('temp')
            self._status.gpu_vram_used_mb = gpu_stats.get('vram_used_mb', 0)
            self._status.gpu_vram_total_mb = gpu_stats.get('vram_total_mb', 0)
            self._status.gpu_utilization = gpu_stats.get('utilization', 0)

    def _get_cpu_temp(self) -> Optional[float]:
        """Get CPU temperature using psutil or fallback methods."""
        # Try psutil first
        try:
            import psutil
            temps = psutil.sensors_temperatures()
            if temps:
                # Try common sensor names in order of preference
                for sensor_name in ['coretemp', 'k10temp', 'zenpower', 'cpu_thermal', 'acpitz']:
                    if sensor_name in temps and temps[sensor_name]:
                        return max(t.current for t in temps[sensor_name])
                # Fallback to any available sensor
                for sensor_list in temps.values():
                    if sensor_list:
                        return max(t.current for t in sensor_list)
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback to sysfs
        try:
            result = subprocess.run(
                ['bash', '-c', '''
                for hwmon in /sys/class/hwmon/hwmon*; do
                    name=$(cat "$hwmon/name" 2>/dev/null)
                    if [ "$name" = "k10temp" ] || [ "$name" = "coretemp" ]; then
                        cat "$hwmon/temp1_input" 2>/dev/null
                        exit 0
                    fi
                done
                '''],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip()) / 1000  # millidegrees to degrees
        except Exception:
            pass

        return None

    def _get_gpu_stats(self) -> Optional[dict]:
        """Get GPU stats using nvidia-smi."""
        try:
            result = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(', ')
                if len(parts) >= 4:
                    return {
                        'temp': float(parts[0]),
                        'vram_used_mb': int(float(parts[1])),
                        'vram_total_mb': int(float(parts[2])),
                        'utilization': int(parts[3])
                    }
        except FileNotFoundError:
            # nvidia-smi not available (no NVIDIA GPU)
            pass
        except Exception as e:
            print(f"[THERMAL] GPU stats error: {e}")

        return None

    def _check_thresholds(self):
        """
        Check temperatures against thresholds and update state.

        Thresholds:
        - CPU: Warn 80°C, Pause 85°C, Kill 87°C, Resume <65°C
        - GPU: Warn 75°C, Pause 80°C, Kill 85°C, Resume <65°C
        """
        cpu_temp = self._status.cpu_temp
        gpu_temp = self._status.gpu_temp
        cfg = self.config

        # Determine threshold levels
        cpu_critical = cpu_temp is not None and cpu_temp >= cfg.cpu.kill
        cpu_danger = cpu_temp is not None and cpu_temp >= cfg.cpu.pause
        cpu_warn = cpu_temp is not None and cpu_temp >= cfg.cpu.warn

        gpu_critical = gpu_temp is not None and gpu_temp >= cfg.gpu.kill
        gpu_danger = gpu_temp is not None and gpu_temp >= cfg.gpu.pause
        gpu_warn = gpu_temp is not None and gpu_temp >= cfg.gpu.warn

        current_time = time.time()

        # CRITICAL: Kill AI processes
        if cpu_critical or gpu_critical:
            self._status.state = ThermalState.CRITICAL
            self._status.reason = f"CPU: {cpu_temp:.0f}°C" if cpu_critical else f"GPU: {gpu_temp:.0f}°C"

            # Only kill once per 30 seconds
            if current_time - self._thermal_state['last_kill_time'] > 30:
                self._thermal_state['last_kill_time'] = current_time
                self._thermal_state['killed'] = True
                self._kill_ai_processes()
                print(f"[THERMAL KILL] {self._status.reason} - AI processes terminated")

        # DANGER: Pause AI operations
        elif cpu_danger or gpu_danger:
            self._status.state = ThermalState.DANGER
            self._status.reason = f"CPU: {cpu_temp:.0f}°C" if cpu_danger else f"GPU: {gpu_temp:.0f}°C"

            if not self._thermal_state['paused']:
                self._thermal_state['paused'] = True
                print(f"[THERMAL PAUSE] {self._status.reason} - Pausing AI operations")

        # WARNING: Alert but continue
        elif cpu_warn or gpu_warn:
            self._status.state = ThermalState.WARNING
            self._status.reason = f"CPU: {cpu_temp:.0f}°C" if cpu_warn else f"GPU: {gpu_temp:.0f}°C"

            if not self._thermal_state['warning_shown']:
                self._thermal_state['warning_shown'] = True
                print(f"[THERMAL WARN] {self._status.reason}")

        # Check for safe resume
        cpu_cool = cpu_temp is None or cpu_temp < cfg.cpu.resume
        gpu_cool = gpu_temp is None or gpu_temp < cfg.gpu.resume

        if cpu_cool and gpu_cool:
            if self._thermal_state['paused'] or self._thermal_state['killed']:
                print(f"[THERMAL RESUME] Temps cooled - CPU: {cpu_temp or 'N/A'}°C, GPU: {gpu_temp or 'N/A'}°C")

            self._status.state = ThermalState.SAFE
            self._status.reason = ""
            self._thermal_state['warning_shown'] = False
            self._thermal_state['paused'] = False
            self._thermal_state['killed'] = False

        elif not (cpu_warn or gpu_warn or cpu_danger or gpu_danger or cpu_critical or gpu_critical):
            # Between resume and warn - clear warning but keep pause if set
            if not self._thermal_state['paused'] and not self._thermal_state['killed']:
                self._status.state = ThermalState.SAFE
                self._status.reason = ""
            self._thermal_state['warning_shown'] = False

    def _kill_ai_processes(self):
        """Kill AI inference processes to reduce thermal load."""
        processes_to_kill = [
            'ollama runner',
            'ollama_llama_server',
            'llama-server',
            'vllm',
        ]

        for proc in processes_to_kill:
            try:
                subprocess.run(['pkill', '-f', proc], timeout=5, capture_output=True)
            except Exception:
                pass

    def _notify_callbacks(self):
        """Notify registered callbacks of status update."""
        for callback in self._callbacks:
            try:
                callback(self._status)
            except Exception as e:
                print(f"[THERMAL] Callback error: {e}")


# Module-level singleton accessor
_monitor: Optional[ThermalMonitor] = None


def get_thermal_monitor() -> ThermalMonitor:
    """Get the singleton thermal monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = ThermalMonitor()
    return _monitor


def start_thermal_monitoring():
    """Start thermal monitoring (convenience function)."""
    monitor = get_thermal_monitor()
    monitor.start()
    return monitor


def stop_thermal_monitoring():
    """Stop thermal monitoring (convenience function)."""
    monitor = get_thermal_monitor()
    monitor.stop()


def is_thermal_safe() -> bool:
    """Check if system is thermally safe (convenience function)."""
    monitor = get_thermal_monitor()
    return monitor.is_safe()


def get_thermal_status() -> ThermalStatus:
    """Get current thermal status (convenience function)."""
    monitor = get_thermal_monitor()
    return monitor.get_status()


# Quick test
if __name__ == "__main__":
    print("=" * 60)
    print("Thermal Monitor Test")
    print("=" * 60)

    monitor = get_thermal_monitor()

    # Get initial reading
    monitor._update_status()
    status = monitor.get_status()

    print(f"\nCPU Temperature: {status.cpu_temp or 'N/A'}°C")
    print(f"GPU Temperature: {status.gpu_temp or 'N/A'}°C")
    print(f"GPU VRAM: {status.gpu_vram_used_mb}MB / {status.gpu_vram_total_mb}MB ({status.gpu_vram_percent:.1f}%)")
    print(f"GPU Utilization: {status.gpu_utilization}%")
    print(f"State: {status.state.value}")
    print(f"Safe for AI: {status.is_safe}")

    print("\nThresholds:")
    print(f"  CPU: warn={monitor.config.cpu.warn}°C, pause={monitor.config.cpu.pause}°C, kill={monitor.config.cpu.kill}°C")
    print(f"  GPU: warn={monitor.config.gpu.warn}°C, pause={monitor.config.gpu.pause}°C, kill={monitor.config.gpu.kill}°C")

    print("\n[OK] Thermal monitor ready")
