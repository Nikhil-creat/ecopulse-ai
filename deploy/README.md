# Kubernetes deployment (Helm)

Prerequisites: a cluster with an NGINX ingress controller, a TimescaleDB+pgvector Postgres, Redis, and a ReadWriteMany volume for `/app/artifacts`.

    helm upgrade --install ecopulse deploy/helm/ecopulse -n ecopulse --create-namespace \
      --set imageTag=<git-sha> --set ingress.host=ecopulse.example.com \
      --set existingSecret=ecopulse-secrets --set artifacts.existingClaim=ecopulse-artifacts

Notes: run the schema once (`infra/db/init/*.sql`) against the database. `beat` must stay at 1 replica; `worker` and `api` scale horizontally.
Images are built and pushed to GHCR by `.github/workflows/docker.yml`.
