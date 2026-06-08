# run_mock_agent.py – place in the backend folder
import asyncio
from agent.orchestrator import AuditOrchestrator
from agent.state import AuditContext

async def main():
    cfg = {
        "arize_api_key": "",
        "arize_project_id": "",
        "elastic_api_key": "",
        "elastic_cloud_id": "",
        "endpoint_url": "http://localhost",
    }
    ctx = AuditContext(config=cfg, selected_modules=["prompt_injection"])
    orchestrator = AuditOrchestrator()
    report = await orchestrator.run_audit(ctx)
    print(report.model_dump())

if __name__ == "__main__":
    asyncio.run(main())