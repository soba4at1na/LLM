import psutil
import subprocess
import json
from typing import Dict, Any

class SystemMonitor:
    def __init__(self):
        self.gpu_available = self._check_gpu()
        self._gpu_details = self._get_gpu_details()
    
    def _check_gpu(self) -> bool:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def _get_gpu_details(self) -> Dict:
        if not self.gpu_available:
            return {}
        
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,power.limit", "--format=csv,noheader"],
                capture_output=True,
                text=True
            )
            parts = result.stdout.strip().split(',')
            return {
                "name": parts[0] if len(parts) > 0 else "Unknown",
                "driver": parts[1] if len(parts) > 1 else "Unknown",
                "power_limit": parts[2] if len(parts) > 2 else "Unknown"
            }
        except:
            return {}
    
    def _get_gpu_metrics(self) -> Dict[str, Any]:
        if not self.gpu_available:
            return {}
        
        try:
            # GPU Utilization
            util_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader"],
                capture_output=True,
                text=True
            )
            gpu_util = float(util_result.stdout.strip().replace('%', ''))
            
            # GPU Memory
            mem_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True
            )
            mem_used, mem_total = mem_result.stdout.strip().split(',')
            mem_used = float(mem_used.replace('MiB', '').strip()) / 1024
            mem_total = float(mem_total.replace('MiB', '').strip()) / 1024
            
            # GPU Temperature
            temp_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                capture_output=True,
                text=True
            )
            temp = float(temp_result.stdout.strip()) if temp_result.stdout.strip() else None
            
            # GPU Power
            power_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader"],
                capture_output=True,
                text=True
            )
            power = float(power_result.stdout.strip().replace('W', '').strip()) if power_result.stdout.strip() else None
            
            # GPU Processes
            proc_result = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader"],
                capture_output=True,
                text=True
            )
            processes = []
            for line in proc_result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        processes.append({
                            "pid": parts[0].strip(),
                            "memory_mb": float(parts[1].strip().replace('MiB', '').strip()) if parts[1].strip() else 0
                        })
            
            return {
                "gpu_utilization": gpu_util,
                "gpu_memory_used_gb": round(mem_used, 1),
                "gpu_memory_total_gb": round(mem_total, 1),
                "gpu_memory_percent": round((mem_used / mem_total) * 100, 1),
                "gpu_temperature": temp,
                "gpu_power_draw": power,
                "gpu_processes": processes
            }
        except Exception as e:
            print(f"GPU metrics error: {e}")
            return {
                "gpu_utilization": 0,
                "gpu_memory_used_gb": 0,
                "gpu_memory_total_gb": 0,
                "gpu_memory_percent": 0,
                "gpu_temperature": None,
                "gpu_power_draw": None,
                "gpu_processes": []
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "cpu_count": psutil.cpu_count(),
            "memory_percent": memory.percent,
            "memory_used_gb": round(memory.used / (1024**3), 1),
            "memory_total_gb": round(memory.total / (1024**3), 1),
            "gpu_available": self.gpu_available,
            "gpu_details": self._gpu_details,
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1)
        }
        
        metrics.update(self._get_gpu_metrics())
        return metrics