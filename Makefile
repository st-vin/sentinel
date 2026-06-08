.PHONY: up down test test-backend test-pdf lint clean logs

up:
	docker-compose up -d

down:
	docker-compose down

test: test-backend

test-backend:
	cd backend && pip install -e ".[dev]" -q && pytest --tb=short -q

test-pdf:
	cd backend && python -c "\
from output.pdf_generator import generate_pdf; \
from pathlib import Path; \
import json; \
report = { \
  'audit_run_id': 'test-run-001', \
  'created_at': '2026-05-28T12:00:00Z', \
  'target_agent': {'endpoint': 'http://mock/chat', 'arize_project_id': 'test'}, \
  'overall_score': 58, \
  'status': 'complete', \
  'modules': [{'module_id': 'prompt_injection', 'score': 35, 'findings': [{'finding_id': 'f1', 'module_id': 'prompt_injection', 'severity': 'critical', 'rule_id': 'GDPR-Art32', 'rule_name': 'Security of Processing', 'evidence': 'System prompt leaked in response', 'recommendation': 'Add output filtering', 'confidence': 0.95}], 'status': 'complete'}] \
}; \
pdf = generate_pdf(report); \
Path('/tmp/test-report.pdf').write_bytes(pdf); \
print(f'PDF generated: {len(pdf)} bytes -> /tmp/test-report.pdf')"

lint:
	cd backend && ruff check .

logs:
	docker-compose logs -f backend

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
