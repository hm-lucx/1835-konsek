FROM python:3.12-slim as runtime

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy project files
COPY pyproject.toml pyproject.toml
COPY . .

# Install runtime dependencies
RUN uv pip install -e .

EXPOSE 8000

# Development stage includes dev dependencies
FROM runtime as development

# Install dev dependencies
RUN uv pip install -e ".[dev]"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Default to runtime stage
FROM development
