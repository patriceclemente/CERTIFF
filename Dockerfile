FROM python:3.12-slim

# Dépendances système :
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    libimage-exiftool-perl \
    default-jre-headless \
    fonts-liberation \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Debian fournit ImageMagick 6 (commande "convert"), pas "magick" (IM7).
# Le code du projet appelle explicitement "magick" -> on crée un alias compatible.
RUN printf '#!/bin/sh\ncase "$1" in\n  identify|mogrify|composite|montage|compare|conjure|stream|display|animate)\n    cmd="$1"; shift; exec "$cmd" "$@"\n    ;;\n  *)\n    exec convert "$@"\n    ;;\nesac\n' > /usr/local/bin/magick \
    && chmod +x /usr/local/bin/magick
WORKDIR /app

# Installation des dépendances Python d'abord (meilleur cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN find /etc/ImageMagick* -name policy.xml -exec \
    sed -i 's#<policy domain="path" rights="none" pattern="@\*"/>#<!-- <policy domain="path" rights="none" pattern="@*"/> -->#' {} \;

# Copie du reste du projet
COPY . .

EXPOSE 5001

CMD ["python", "app.py"]
