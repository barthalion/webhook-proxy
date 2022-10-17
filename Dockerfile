FROM python:3.10 as builder

RUN curl -sSL https://install.python-poetry.org | /usr/local/bin/python - && \
    python -m venv /venv && \
    /venv/bin/python -m pip install -U pip

COPY pyproject.toml poetry.lock /

RUN $HOME/.local/bin/poetry export -o requirements.txt && \
    /venv/bin/pip install -r requirements.txt

FROM python:3.10-slim
ENV PATH="/venv/bin:$PATH"

EXPOSE 8000

COPY --from=builder /venv /venv
ADD . /app
WORKDIR /app

ENTRYPOINT ["/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
