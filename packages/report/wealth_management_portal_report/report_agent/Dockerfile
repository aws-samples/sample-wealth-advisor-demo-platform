FROM python:3.12-slim

# WeasyPrint system dependencies for PDF generation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0t64 libpango-1.0-0 libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 libcairo2 libffi-dev libharfbuzz-subset0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy bundled package
COPY --from=workspace bundle-arm /app

# Reject bundles built with wrong-platform native extensions
RUN if find /app -name '*darwin*.so' | grep -q .; then \
      echo "ERROR: macOS .so files in bundle. Clear Nx cache and rebuild: pnpm nx reset && pnpm nx run wealth_management_portal.report:bundle-arm" >&2; \
      exit 1; \
    fi

EXPOSE 8080

ENV PYTHONPATH=/app

CMD ["python", "-m", "wealth_management_portal_report.report_agent.main"]
