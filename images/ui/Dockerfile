# Unity Catalog UI, built from upstream at UC_VERSION with the pack's Keycloak
# login patch, served by nginx with /api proxied to the UC server.
ARG UC_VERSION=v0.6.0

FROM node:18-bookworm AS build
ARG UC_VERSION
WORKDIR /src
RUN git clone --depth 1 --branch "${UC_VERSION}" https://github.com/unitycatalog/unitycatalog.git . \
    && rm -rf .git
COPY patches/ /patches/
RUN cd ui && for p in /patches/*.patch; do echo "applying $p"; patch -p1 < "$p"; done
WORKDIR /src/ui
RUN yarn install --network-timeout 1000000 && yarn build

FROM nginxinc/nginx-unprivileged:1.27-alpine
ENV UI_PORT=3000 \
    UC_SERVER_URL=http://localhost:8080
COPY --from=build /src/ui/build /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.d/40-uc-config.sh /docker-entrypoint.d/40-uc-config.sh
USER root
RUN chmod +x /docker-entrypoint.d/40-uc-config.sh && chown -R 101:101 /usr/share/nginx/html
USER 101
EXPOSE 3000
