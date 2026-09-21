FROM eclipse-temurin:21-jre-jammy

ARG METABASE_VERSION=0.63.18
ARG METABASE_DUCKDB_DRIVER_VERSION=1.5.5.0

ARG DUCKDB_DRIVER_URL=https://github.com/motherduckdb/metabase_duckdb_driver/releases/download/${METABASE_DUCKDB_DRIVER_VERSION}/duckdb.metabase-driver.jar

ENV MB_PLUGINS_DIR=/home/metabase/plugins/

RUN groupadd --system metabase \
    && useradd --system --gid metabase metabase \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p \
        /home/metabase/plugins \
        /home/metabase/data \
        /home/metabase/state \
    && chown -R metabase:metabase /home/metabase

WORKDIR /home/metabase

ADD --chown=metabase:metabase \
    https://downloads.metabase.com/v${METABASE_VERSION}/metabase.jar \
    /home/metabase/metabase.jar

ADD --chown=metabase:metabase \
    ${DUCKDB_DRIVER_URL} \
    /home/metabase/plugins/duckdb.metabase-driver.jar

USER metabase

EXPOSE 3000

CMD ["java", "-jar", "/home/metabase/metabase.jar"]