FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

COPY --from=workspace bundle-arm /app

RUN if find /app -name '*darwin*.so' | grep -q .; then \
      echo "ERROR: macOS .so files in bundle" >&2; exit 1; \
    fi

EXPOSE 8080

ENV PYTHONPATH=/app

CMD ["python", "-m", "wealth_management_portal_advisor_chat.database_agent.main"]
