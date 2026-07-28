FROM python:3.12-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    TERM=dumb \
    HOME=/workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        ripgrep \
        coreutils \
        procps \
        tini \
    && rm -rf /var/lib/apt/lists/*

# uv: fast Python package installer (install directly to /usr/local/bin
# via UV_INSTALL_DIR to avoid relying on $HOME at build time).
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

RUN mkdir -p /workspace
WORKDIR /workspace

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# tini reaps zombies; container stays alive via tail -f /dev/null,
# all real work goes through `docker exec`.
ENTRYPOINT ["tini", "--", "/usr/local/bin/entrypoint.sh"]
