# Image unique du backend. Elle est lancee en plusieurs conteneurs, chacun avec
# une commande differente : migrate, api, collector, etl. Voir docker-compose.yml.
#
# Construite depuis la racine du depot, parce qu elle installe packages/features.
# Ubuntu LTS fournit les correctifs Perl absents de Debian stable et conserve
# glibc pour les wheels scientifiques precompilees (ARM64 inclus).
FROM ubuntu:24.04

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends python3.12-venv ca-certificates \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' perl-base)" ge 5.38.2-3.2ubuntu0.4 \
    && rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY packages/features /opt/features
RUN pip install --no-cache-dir /opt/features

COPY services/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/backend .

EXPOSE 8080

CMD ["./scripts/start.sh"]
