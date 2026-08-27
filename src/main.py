"""Elevate Project Group 3 - HR System Entrypoint."""
import asyncio
from src.agents.root_orchestrator import RootOrchestrator


async def main():
    print("Initializing Elevate Group 3 HR Multi-Agent System...")
    orchestrator = RootOrchestrator()
    print(f"Master Agent: {orchestrator.name} ready.")


if __name__ == "__main__":
    asyncio.run(main())
