FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/SahilMore06/Fluxora" \
      org.opencontainers.image.url="https://github.com/SahilMore06/Fluxora" \
      org.opencontainers.image.documentation="https://github.com/SahilMore06/Fluxora#command-line-interface" \
      org.opencontainers.image.title="Fluxora CLI" \
      org.opencontainers.image.description="Fluxora – Intelligent File Conversion & Productivity Suite headless CLI (266 offline format pairs)" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/tmp \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    pandoc \
    poppler-utils \
    ghostscript \
    p7zip-full \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/fluxora
COPY pyproject.toml ./

# Install only headless CLI dependencies first so code edits reuse the cached wheel layer
RUN python -c "import tomllib, subprocess, sys; deps=[d for d in tomllib.load(open('pyproject.toml','rb'))['project']['dependencies'] if not d.startswith(('PySide6','pyobjc-'))]; subprocess.check_call([sys.executable,'-m','pip','install','--no-cache-dir',*deps])"

COPY LICENSE README.md ./
COPY filetool ./filetool

RUN pip install --no-cache-dir --no-deps . \
    && fluxora --help >/dev/null \
    && python -c "import filetool.cli, filetool.core; assert len(filetool.core.registry.registry.all_supported_pairs()) >= 260"

WORKDIR /work
ENTRYPOINT ["fluxora"]
CMD ["--help"]
