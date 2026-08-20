import os
import time
import platform
import psutil
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..security.auth import CurrentUser

router = APIRouter(tags=["Monitoring"])


class CpuInfo(BaseModel):
    percent: float
    cores_logical: int
    cores_physical: int
    load_avg: Optional[list[float]] = None


class MemoryInfo(BaseModel):
    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent: float


class ProcessInfo(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    memory_rss_bytes: int
    memory_vms_bytes: int
    threads: int
    uptime_seconds: float


class ServerMonitorResponse(BaseModel):
    hostname: str
    platform: str
    timestamp: float
    cpu: CpuInfo
    memory: MemoryInfo
    process: ProcessInfo


@router.get("/", response_model=ServerMonitorResponse, description="Report server-wide CPU and RAM usage of the running app")
def monitor_server(user: CurrentUser):
    proc = psutil.Process(os.getpid())

    cpu = CpuInfo(
        percent=psutil.cpu_percent(interval=0.2),
        cores_logical=psutil.cpu_count(logical=True) or 0,
        cores_physical=psutil.cpu_count(logical=False) or 0,
        load_avg=list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
    )

    vm = psutil.virtual_memory()
    memory = MemoryInfo(
        total_bytes=vm.total,
        available_bytes=vm.available,
        used_bytes=vm.used,
        percent=vm.percent,
    )

    with proc.oneshot():
        process = ProcessInfo(
            pid=proc.pid,
            name=proc.name(),
            cpu_percent=proc.cpu_percent(interval=0.2),
            memory_rss_bytes=proc.memory_info().rss,
            memory_vms_bytes=proc.memory_info().vms,
            threads=proc.num_threads(),
            uptime_seconds=time.time() - proc.create_time(),
        )

    return ServerMonitorResponse(
        hostname=platform.node(),
        platform=platform.platform(),
        timestamp=time.time(),
        cpu=cpu,
        memory=memory,
        process=process,
    )
