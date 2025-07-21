# docs/CONTRIBUTING.md
### Development checklist
1. `pre‑commit run --all-files`  → black / isort / flake8 / pylint
2. `pytest -q --cov=docharvester_pro --cov-report=term-missing`
3. Keep coverage **≥ 90 %** and pylint **≥ 9.0**  
   `pylint $(git ls-files '*.py'|grep -v tests/)`
4. Draft a CHANGELOG entry under “Unreleased”.
5. Create a PR; CI must pass before merge.
