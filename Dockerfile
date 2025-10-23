FROM docker:24-cli

# Install bash, curl, and other utilities
RUN apk add --no-cache \
    bash \
    curl \
    jq \
    grep \
    coreutils

# Set working directory
WORKDIR /app

# Copy scripts
COPY setup-ollama.sh /app/
COPY .env /app/
RUN chmod +x /app/setup-ollama.sh

# Set bash as the default shell
SHELL ["/bin/bash", "-c"]

# Default command
ENTRYPOINT ["/app/setup-ollama.sh"]
