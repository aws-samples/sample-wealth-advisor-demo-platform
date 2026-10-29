import os
import uuid
from collections.abc import Callable
from urllib.parse import urlparse

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from mangum import Mangum
from pydantic import BaseModel
from starlette.middleware.exceptions import ExceptionMiddleware

os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "PortfolioDDApi"
os.environ["POWERTOOLS_SERVICE_NAME"] = "PortfolioDDApi"

logger: Logger = Logger()
metrics: Metrics = Metrics()
tracer: Tracer = Tracer()


class InternalServerErrorDetails(BaseModel):
    detail: str


app = FastAPI(title="PortfolioDDApi", responses={500: {"model": InternalServerErrorDetails}})
lambda_handler = Mangum(app, lifespan="off")

lambda_handler.__name__ = "handler"
lambda_handler = tracer.capture_lambda_handler(lambda_handler)
lambda_handler = logger.inject_lambda_context(lambda_handler, clear_state=True)
lambda_handler = metrics.log_metrics(lambda_handler, capture_cold_start_metric=True)


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        origin = request.headers.get("origin")
        allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else []

        is_localhost = origin and urlparse(origin).hostname in ["localhost", "127.0.0.1"]
        is_allowed_origin = origin and origin in allowed_origins

        cors_origin = "*"
        if allowed_origins and not is_localhost:
            cors_origin = origin if is_allowed_origin else allowed_origins[0]

        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": cors_origin,
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    response = await call_next(request)

    origin = request.headers.get("origin")
    allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else []

    is_localhost = origin and urlparse(origin).hostname in ["localhost", "127.0.0.1"]
    is_allowed_origin = origin and origin in allowed_origins

    cors_origin = "*"
    if allowed_origins and not is_localhost:
        cors_origin = origin if is_allowed_origin else allowed_origins[0]

    response.headers["Access-Control-Allow-Origin"] = cors_origin
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"

    return response


app.add_middleware(ExceptionMiddleware, handlers=app.exception_handlers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, err):
    logger.exception("Unhandled exception")
    metrics.add_metric(name="Failure", unit=MetricUnit.Count, value=1)
    return JSONResponse(
        status_code=500, content=InternalServerErrorDetails(detail="Internal Server Error").model_dump()
    )


@app.middleware("http")
async def metrics_handler(request: Request, call_next):
    metrics.add_dimension("route", f"{request.method} {request.url.path}")
    metrics.add_metric(name="RequestCount", unit=MetricUnit.Count, value=1)

    response = await call_next(request)

    if response.status_code == 200:
        metrics.add_metric(name="Success", unit=MetricUnit.Count, value=1)

    return response


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    corr_id = request.headers.get("x-correlation-id")
    if not corr_id and "aws.context" in request.scope:
        corr_id = request.scope["aws.context"].aws_request_id
    elif not corr_id:
        corr_id = uuid.uuid4().hex

    logger.set_correlation_id(corr_id)

    response = await call_next(request)
    response.headers["X-Correlation-Id"] = corr_id
    return response


class LoggerRouteHandler(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            ctx = {
                "path": request.url.path,
                "route": self.path,
                "method": request.method,
            }
            logger.append_keys(fastapi=ctx)
            logger.info("Received request")

            return await original_route_handler(request)

        return route_handler


app.router.route_class = LoggerRouteHandler
