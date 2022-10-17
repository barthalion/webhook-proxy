import hashlib
import hmac
import json

import psycopg2
from fastapi import FastAPI, Request, Response
from pydantic import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/flathub_webhook_proxy"
    github_secret: str = "secret"


settings = Settings()
postgres = psycopg2.connect(settings.database_url)
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)


@app.on_event("startup")
def initialize():
    init_table = """
        CREATE TABLE IF NOT EXISTS events (
            id BIGSERIAL NOT NULL,
            timestamp TIMESTAMP DEFAULT NOW(),
            source TEXT NOT NULL,
            payload TEXT NOT NULL,
            headers TEXT NOT NULL,
            ipaddress INET DEFAULT NULL,
            status TEXT DEFAULT 'pending',
            status_timestamp TIMESTAMP DEFAULT NOW()
        )
    """

    with postgres.cursor() as cur:
        cur.execute(init_table)
        postgres.commit()


def convert_headers_to_json(request: Request):
    ret = {}
    for key in request.headers.keys():
        ret[key] = request.headers.get(key)
    return json.dumps(ret)


@app.post("/github")
async def github_handler(request: Request):
    if settings.github_secret:
        if signature := request.headers.get("X-Hub-Signature-256"):
            secret = settings.github_secret.encode()
            mac = hmac.new(secret, msg=request.body, digestmod=hashlib.sha256)  # type: ignore

            if not hmac.compare_digest("sha256=" + mac.hexdigest(), signature):
                return Response(status_code=403)

    with postgres.cursor() as cur:
        body = await request.json()
        headers = convert_headers_to_json(request)
        ipaddress = None

        if x_forwarded_for := request.headers.get("X-Forwarded-For"):
            ipaddress = x_forwarded_for.split(",")[0]
        else:
            if client := request.client:
                ipaddress = client.host

        cur.execute(
            "INSERT INTO events (source, payload, headers, ipaddress) VALUES (%s, %s, %s, %s)",
            ("github", json.dumps(body), headers, ipaddress),
        )
        postgres.commit()

    return "OK"
