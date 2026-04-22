FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# Copy bundled package
COPY --from=workspace bundle-arm /app

# Reject bundles built with wrong-platform native extensions
RUN if find /app -name '*darwin*.so' | grep -q .; then \
      echo "ERROR: macOS .so files in bundle. Clear Nx cache and rebuild: pnpm nx reset && pnpm nx run wealth_management_portal.client_search:bundle-arm" >&2; \
      exit 1; \
    fi

EXPOSE 8080

ENV PYTHONPATH=/app

# Auto-instrument with AWS Distro for OpenTelemetry
# https://aws-otel.github.io/docs/getting-started/python-sdk/auto-instr
CMD ["python", "bin/opentelemetry-instrument", "python", "-m", "wealth_management_portal_client_search.client_search_agent.main"]
