"""Benchmark script to demonstrate and compare synchronous vs. asynchronous execution.

This script demonstrates the latency and throughput difference between:
1. Sequential synchronous execution (thread blocking per call)
2. Concurrent asynchronous execution (non-blocking asyncio event loop)
"""

import asyncio
import time
from typing import List
from backend.models import AgentState


class MockBenchmarkEngine:
    """Mock engine simulating network round-trip latency to an external LLM."""

    def __init__(self, simulated_latency: float = 0.5):
        self.simulated_latency = simulated_latency

    def process(self, state: AgentState) -> AgentState:
        """Simulate synchronous thread blocking."""
        time.sleep(self.simulated_latency)
        state_copy = state.model_copy(deep=True)
        state_copy.messages.append({
            "role": "assistant",
            "content": "Simulated assistant reply."
        })
        return state_copy

    async def aprocess(self, state: AgentState) -> AgentState:
        """Simulate non-blocking async network I/O."""
        await asyncio.sleep(self.simulated_latency)
        state_copy = state.model_copy(deep=True)
        state_copy.messages.append({
            "role": "assistant",
            "content": "Simulated assistant reply."
        })
        return state_copy


def run_sync_batch(cases: List[AgentState], engine: MockBenchmarkEngine):
    """Run test cases sequentially using .process()"""
    start = time.perf_counter()
    results = []
    for idx, c in enumerate(cases):
        case_start = time.perf_counter()
        res = engine.process(c)
        exec_ms = int((time.perf_counter() - case_start) * 1000)
        results.append((idx, exec_ms))
    total_ms = int((time.perf_counter() - start) * 1000)
    return total_ms, results


async def run_async_batch(cases: List[AgentState], engine: MockBenchmarkEngine):
    """Run test cases concurrently using await .aprocess() and asyncio.gather()"""
    start = time.perf_counter()

    async def run_one(idx: int, c: AgentState):
        case_start = time.perf_counter()
        res = await engine.aprocess(c)
        exec_ms = int((time.perf_counter() - case_start) * 1000)
        return idx, exec_ms

    results = await asyncio.gather(*[run_one(idx, c) for idx, c in enumerate(cases)])
    total_ms = int((time.perf_counter() - start) * 1000)
    return total_ms, results


def main():
    num_cases = 10
    simulated_llm_latency_sec = 0.3
    engine = MockBenchmarkEngine(simulated_latency=simulated_llm_latency_sec)

    print("==================================================================")
    print(f"BENCHMARK: Comparing {num_cases} Conversations (Simulated LLM latency = {simulated_llm_latency_sec}s)")
    print("==================================================================")

    test_states = [
        AgentState(messages=[{"role": "user", "content": f"Test case #{i}: need repairs"}])
        for i in range(num_cases)
    ]

    # 1. Run Synchronous
    print(f"\n1. Running {num_cases} cases SYNCHRONOUSLY (one by one)...")
    sync_total_ms, sync_results = run_sync_batch(test_states, engine)
    print(f"   --> Total Time: {sync_total_ms} ms (~{sync_total_ms/1000:.2f} s)")

    # 2. Run Asynchronous
    print(f"\n2. Running {num_cases} cases ASYNCHRONOUSLY (concurrent event loop)...")
    async_total_ms, async_results = asyncio.run(run_async_batch(test_states, engine))
    print(f"   --> Total Time: {async_total_ms} ms (~{async_total_ms/1000:.2f} s)")

    # 3. Summary
    speedup = sync_total_ms / async_total_ms if async_total_ms > 0 else 1
    print("\n------------------------------------------------------------------")
    print(f"RESULTS:")
    print(f"  Synchronous Time:  {sync_total_ms:>6} ms")
    print(f"  Asynchronous Time: {async_total_ms:>6} ms")
    print(f"  Speedup Factor:    {speedup:>6.2f}x faster with Asyncio!")
    print("==================================================================")


if __name__ == "__main__":
    main()
