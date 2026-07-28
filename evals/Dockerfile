# OPTIONAL: run the recording fake service in a one-off container (for a developer without local
# Python). Co-located with the executor if the workspace/run dir is mounted from the host, so it
# keeps full-fidelity checks. Build context is the evals/ dir: `docker build -t skillhub-evals evals`.
FROM python:3.12-slim
WORKDIR /app
COPY . /app/evals
# stdlib only — nothing to pip install. Entry is `python -m`, so the container runs any evals
# command: `... evals.fake_service --run-dir /run` or `... evals.harness check <scenario> ...`.
ENTRYPOINT ["python", "-m"]
CMD ["evals.fake_service", "--help"]
