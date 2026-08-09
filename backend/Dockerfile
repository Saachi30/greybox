FROM python:3.12-slim-bookworm

# WeasyPrint needs these system libs for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev \
    libcairo2 shared-mime-info curl \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI (client binary only, not the full engine/daemon - we don't need
# a daemon in here, just something that can talk through the already
# mounted /var/run/docker.sock to the HOST's daemon). This was missing
# entirely before: the socket being mounted in docker-compose.yml only
# gives access to the daemon - core/tools.py's subprocess.run(["docker",
# "exec", ...]) also needs the actual `docker` executable to exist inside
# this container, which it never did. Every docker-routed tool call
# (nmap/whatweb/subdomain_enum/nikto - anything except the two API-kind
# tools, hunter_email/crtsh) was failing instantly with
# "[Errno 2] No such file or directory: 'docker'", silently caught and
# turned into an "error running X: ..." finding rather than a request
# failure - which is why it looked like things were running when they
# weren't (fast because nothing was actually happening).
ARG TARGETARCH
RUN case "${TARGETARCH}" in \
        amd64) DOCKER_ARCH=x86_64 ;; \
        arm64) DOCKER_ARCH=aarch64 ;; \
        *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL "https://download.docker.com/linux/static/stable/${DOCKER_ARCH}/docker-29.6.1.tgz" -o /tmp/docker.tgz && \
    tar -xzf /tmp/docker.tgz -C /tmp && \
    mv /tmp/docker/docker /usr/local/bin/docker && \
    chmod +x /usr/local/bin/docker && \
    rm -rf /tmp/docker /tmp/docker.tgz

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ /app/core/
COPY report/ /app/report/
COPY backend/app/ /app/app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]