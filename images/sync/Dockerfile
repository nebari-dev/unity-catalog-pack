FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml ./
COPY uc_keycloak_sync ./uc_keycloak_sync
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
COPY --from=build /install /usr/local
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin ucsync
USER 1000
ENTRYPOINT ["uc-keycloak-sync"]
