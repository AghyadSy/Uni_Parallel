import ctypes
import math
import os
import statistics
import time
import tracemalloc
from dataclasses import dataclass


def _round_ms(value):
    return round(value, 2)


def _percentile(values, percentile):
    if not values:
        return 0.0

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * (percentile / 100)
    lower_index = math.floor(rank)
    upper_index = math.ceil(rank)

    if lower_index == upper_index:
        return ordered[lower_index]

    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    return lower_value + (upper_value - lower_value) * (rank - lower_index)


def _process_memory_bytes():
    if os.name == "nt":
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            process_handle = ctypes.windll.kernel32.GetCurrentProcess()
            result = ctypes.windll.psapi.GetProcessMemoryInfo(
                process_handle,
                ctypes.byref(counters),
                counters.cb,
            )
            if result:
                return int(counters.WorkingSetSize)
        except Exception:
            return None

    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as proc_file:
            parts = proc_file.readline().split()
        if len(parts) >= 2:
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int(parts[1]) * int(page_size)
    except Exception:
        return None

    return None


class MemoryUsageProbe:
    def __init__(self):
        self._use_tracemalloc = _process_memory_bytes() is None
        if self._use_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()

    def measure_mb(self):
        memory_bytes = _process_memory_bytes()
        if memory_bytes is not None:
            return round(memory_bytes / (1024 * 1024), 2)

        current_bytes, _ = tracemalloc.get_traced_memory()
        return round(current_bytes / (1024 * 1024), 2)


@dataclass
class BenchmarkRun:
    success: bool
    elapsed_ms: float
    database_queries: int


class BenchmarkService:
    def __init__(self, total_runs=20, memory_probe=None):
        self.total_runs = total_runs
        self.memory_probe = memory_probe or MemoryUsageProbe()

    def run(
        self,
        scenario,
        operation,
        *,
        timestamp,
        query_count_getter=None,
        before_all=None,
        after_all=None,
        extra=None,
    ):
        query_count_getter = query_count_getter or (lambda result: result.get("db_query_count", 0))
        extra = extra or {}

        if before_all is not None:
            before_all()

        memory_before_mb = self.memory_probe.measure_mb()
        total_start = time.perf_counter()
        runs = []

        for _ in range(self.total_runs):
            started = time.perf_counter()
            try:
                result = operation()
                success = True
                database_queries = max(0, int(query_count_getter(result)))
            except Exception:
                success = False
                database_queries = 0
            elapsed_ms = (time.perf_counter() - started) * 1000
            runs.append(
                BenchmarkRun(
                    success=success,
                    elapsed_ms=elapsed_ms,
                    database_queries=database_queries,
                )
            )

        total_execution_time_ms = (time.perf_counter() - total_start) * 1000
        memory_after_mb = self.memory_probe.measure_mb()

        if after_all is not None:
            after_all()

        durations = [run.elapsed_ms for run in runs]
        successful_runs = sum(1 for run in runs if run.success)
        failed_runs = self.total_runs - successful_runs
        database_queries = sum(run.database_queries for run in runs)

        benchmark = {
            "scenario": scenario,
            "timestamp": timestamp,
            "total_runs": self.total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate_percent": _round_ms((successful_runs / self.total_runs) * 100) if self.total_runs else 0,
            "total_execution_time_ms": _round_ms(total_execution_time_ms),
            "average_response_time_ms": _round_ms(statistics.mean(durations)) if durations else 0,
            "min_response_time_ms": _round_ms(min(durations)) if durations else 0,
            "max_response_time_ms": _round_ms(max(durations)) if durations else 0,
            "p50_response_time_ms": _round_ms(_percentile(durations, 50)),
            "standard_deviation_ms": _round_ms(statistics.pstdev(durations)) if len(durations) > 1 else 0,
            "fastest_run_ms": _round_ms(min(durations)) if durations else 0,
            "slowest_run_ms": _round_ms(max(durations)) if durations else 0,
            "memory_usage_before_mb": round(memory_before_mb, 2),
            "memory_usage_after_mb": round(memory_after_mb, 2),
            "memory_consumed_mb": round(memory_after_mb - memory_before_mb, 2),
            "database_queries": database_queries,
            "average_queries_per_run": _round_ms(database_queries / self.total_runs) if self.total_runs else 0,
            "status": "PASSED" if failed_runs == 0 else "FAILED",
        }
        benchmark.update(extra)
        return benchmark
