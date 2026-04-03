# OTel Config Generator

Generates production-ready OpenTelemetry configuration for Splunk Observability Cloud — collector config, Helm values, and SDK initialization code — from a single command.

## Supported

| Language | Frameworks |
|----------|-----------|
| Java | spring-boot, quarkus, micronaut, generic |
| Python | fastapi, flask, django, celery, generic |
| Node | express, nestjs, fastify, generic |

Infrastructure: Kubernetes (v1)
Collector modes: agent, gateway, sidecar

## Setup

```bash
pip install -r requirements.txt
export AWS_DEFAULT_REGION=us-west-2  # for Bedrock
```

## Usage

**Interactive:**
```bash
python3 otel_config_gen.py --interactive
```

**CLI:**
```bash
python3 otel_config_gen.py \
  --service-name checkout-service \
  --language java \
  --framework spring-boot \
  --environment production \
  --realm us1 \
  --mode agent
```

Output is written to `otel-config/<service-name>/`:
```
otel-config/checkout-service/
  ├── collector.yaml
  ├── helm-values.yaml
  ├── sdk-init.java
  └── README.md
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SPLUNK_ACCESS_TOKEN` | Yes | Your Splunk Observability Cloud access token |
| `SERVICE_VERSION` | Recommended | Service version tag for traces |
| `AWS_DEFAULT_REGION` | Yes | AWS region for Bedrock (us-west-2) |
