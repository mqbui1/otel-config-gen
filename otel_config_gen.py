#!/usr/bin/env python3
"""
OpenTelemetry Auto-Config Generator for Splunk Observability Cloud
Generates collector config, Helm values, and SDK init code for a given service.
"""

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

import boto3
import yaml

BEDROCK_PROFILE = "arn:aws:bedrock:us-west-2:387769110234:application-inference-profile/fky19kpnw2m7"

SUPPORTED_LANGUAGES  = ["java", "python", "node"]
SUPPORTED_FRAMEWORKS = {
    "java":   ["spring-boot", "quarkus", "micronaut", "generic"],
    "python": ["fastapi", "flask", "django", "celery", "generic"],
    "node":   ["express", "nestjs", "fastify", "generic"],
}
SUPPORTED_REALMS = ["us0", "us1", "us2", "eu0", "ap0", "au0", "jp0", "ca0", "gov0"]

SDK_EXTENSION = {
    "java":   "java",
    "python": "py",
    "node":   "js",
}


# ---------------------------------------------------------------------------
# Claude (Bedrock) helpers
# ---------------------------------------------------------------------------

def call_claude(prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name="us-west-2")
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = client.invoke_model(modelId=BEDROCK_PROFILE, body=json.dumps(body))
    return json.loads(resp["body"].read())["content"][0]["text"]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_collector_prompt(args) -> str:
    return textwrap.dedent(f"""
    You are an OpenTelemetry expert specializing in Splunk Observability Cloud.

    Generate a production-ready OpenTelemetry Collector configuration (YAML) for the following service:

    - Service name: {args.service_name}
    - Language: {args.language}
    - Framework: {args.framework}
    - Infrastructure: Kubernetes
    - Deployment mode: {args.mode}
    - Environment: {args.environment}
    - Splunk realm: {args.realm}

    Requirements:
    - Use OTLP receivers (grpc + http)
    - Export traces and metrics to Splunk Observability Cloud (ingest.{args.realm}.signalfx.com)
    - Include a memory_limiter and batch processor with production-appropriate settings
    - Set resource attributes: service.name={args.service_name}, deployment.environment={args.environment}
    - Include health_check and pprof extensions
    - Use ${{SPLUNK_ACCESS_TOKEN}} as the token placeholder
    - For {args.mode} mode, configure appropriately (agent=daemonset style, gateway=deployment style, sidecar=sidecar style)
    - Add helpful comments explaining each section

    Return ONLY the YAML content, no explanation, no markdown fences.
    """).strip()


def build_helm_prompt(args) -> str:
    return textwrap.dedent(f"""
    You are an OpenTelemetry expert specializing in Splunk Observability Cloud.

    Generate production-ready Helm values (YAML) for the splunk-otel-collector Helm chart for the following:

    - Service name: {args.service_name}
    - Language: {args.language}
    - Framework: {args.framework}
    - Infrastructure: Kubernetes
    - Deployment mode: {args.mode}
    - Environment: {args.environment}
    - Splunk realm: {args.realm}
    - Cluster name: {args.service_name}-cluster

    Requirements:
    - Set clusterName, environment, splunkObservability.realm and splunkObservability.accessToken (${{SPLUNK_ACCESS_TOKEN}})
    - Enable logsCollection, metricsEnabled, tracesEnabled as appropriate
    - If mode is agent or sidecar, enable the agent daemonset
    - If mode is gateway, configure the gateway deployment
    - Enable Java/Python/Node auto-instrumentation via the operator if applicable for {args.language}
    - Set appropriate resource limits and requests for production
    - Add helpful comments

    Return ONLY the YAML content, no explanation, no markdown fences.
    """).strip()


def build_sdk_prompt(args) -> str:
    framework_note = f"using the {args.framework} framework" if args.framework != "generic" else ""
    return textwrap.dedent(f"""
    You are an OpenTelemetry expert specializing in Splunk Observability Cloud.

    Generate production-ready OpenTelemetry SDK initialization code for:

    - Language: {args.language} {framework_note}
    - Service name: {args.service_name}
    - Environment: {args.environment}
    - Splunk realm: {args.realm}
    - Infrastructure: Kubernetes (collector runs as agent on localhost)

    Requirements:
    - Use the official OpenTelemetry SDK for {args.language}
    - Export traces via OTLP gRPC to http://localhost:4317 (the collector agent)
    - Set resource attributes: service.name, deployment.environment, service.version (${{SERVICE_VERSION}})
    - Enable automatic instrumentation for {args.framework} if available
    - Include the exact pip install / npm install / maven dependency needed
    - Add error handling for missing env vars
    - Add comments explaining each configuration choice

    Return ONLY the code, no explanation, no markdown fences.
    """).strip()


def build_readme_prompt(args) -> str:
    return textwrap.dedent(f"""
    You are a technical writer specializing in observability and OpenTelemetry.

    Write a concise README.md for an OpenTelemetry configuration package with these files:
    - collector.yaml      — OTel Collector configuration
    - helm-values.yaml    — Splunk OTel Collector Helm chart values
    - sdk-init.{SDK_EXTENSION[args.language]}          — SDK initialization code for {args.language}

    Context:
    - Service: {args.service_name}
    - Language: {args.language} / {args.framework}
    - Infra: Kubernetes
    - Splunk realm: {args.realm}
    - Environment: {args.environment}
    - Collector mode: {args.mode}

    The README should include:
    1. Prerequisites (what needs to be installed/configured)
    2. Quick start — exact commands to apply each file (helm install, kubectl apply, etc.)
    3. Environment variables required (SPLUNK_ACCESS_TOKEN, SERVICE_VERSION)
    4. How to verify it's working (what to look for in Splunk Observability Cloud)
    5. A brief "next steps" section pointing to Splunk docs

    Keep it practical and concise. Return ONLY the markdown content.
    """).strip()


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate(args):
    out_dir = Path("otel-config") / args.service_name
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        ("collector.yaml",                          build_collector_prompt(args), False),
        ("helm-values.yaml",                        build_helm_prompt(args),      False),
        (f"sdk-init.{SDK_EXTENSION[args.language]}", build_sdk_prompt(args),      False),
        ("README.md",                               build_readme_prompt(args),    True),
    ]

    for filename, prompt, is_markdown in tasks:
        print(f"  Generating {filename}...", end=" ", flush=True)
        content = call_claude(prompt)

        # Validate YAML files
        if filename.endswith(".yaml"):
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                print(f"WARN: YAML validation failed — {e}")

        filepath = out_dir / filename
        filepath.write_text(content + "\n")
        print("done")

    print(f"\nOutput written to: {out_dir}/")
    print("\nFiles generated:")
    for f in sorted(out_dir.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name:<30} {size:>6} bytes")


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def prompt_input(label, options=None, default=None):
    if options:
        display = ", ".join(options)
        suffix = f" [{display}]" + (f" (default: {default})" if default else "") + ": "
    else:
        suffix = (f" (default: {default})" if default else "") + ": "
    while True:
        val = input(f"  {label}{suffix}").strip()
        if not val and default:
            return default
        if options and val not in options:
            print(f"    Please choose one of: {', '.join(options)}")
            continue
        if val:
            return val


def interactive_mode():
    print("\nOpenTelemetry Auto-Config Generator — Interactive Mode\n")
    args = argparse.Namespace()
    args.service_name = prompt_input("Service name")
    args.language     = prompt_input("Language", SUPPORTED_LANGUAGES)
    frameworks        = SUPPORTED_FRAMEWORKS[args.language]
    args.framework    = prompt_input("Framework", frameworks, default="generic")
    args.environment  = prompt_input("Environment", default="production")
    args.realm        = prompt_input("Splunk realm", SUPPORTED_REALMS, default="us1")
    args.mode         = prompt_input("Collector mode", ["agent", "gateway", "sidecar"], default="agent")
    return args


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate OTel configs for Splunk Observability Cloud"
    )
    parser.add_argument("--service-name", help="Service name (e.g. checkout-service)")
    parser.add_argument("--language",     choices=SUPPORTED_LANGUAGES, help="Service language")
    parser.add_argument("--framework",    help="Framework (e.g. spring-boot, fastapi, express)")
    parser.add_argument("--environment",  default="production", help="Deployment environment")
    parser.add_argument("--realm",        default="us1", choices=SUPPORTED_REALMS, help="Splunk realm")
    parser.add_argument("--mode",         default="agent", choices=["agent", "gateway", "sidecar"],
                        help="Collector deployment mode")
    parser.add_argument("--interactive",  action="store_true", help="Interactive prompt mode")

    args = parser.parse_args()

    if args.interactive or not args.service_name or not args.language:
        args = interactive_mode()
    else:
        # Default framework to generic if not provided
        if not args.framework:
            args.framework = "generic"
        # Validate framework for language
        valid = SUPPORTED_FRAMEWORKS.get(args.language, [])
        if args.framework not in valid and args.framework != "generic":
            print(f"Warning: '{args.framework}' is not a known framework for {args.language}. Proceeding anyway.")

    print(f"\nGenerating OTel config for '{args.service_name}' ({args.language}/{args.framework}, k8s/{args.mode}, {args.realm})...\n")
    generate(args)
    print("\nDone. See README.md in the output directory for next steps.")


if __name__ == "__main__":
    main()
