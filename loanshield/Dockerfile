# Use official slim python image as builder stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and sync dependencies
RUN uv venv .venv && uv pip install -r pyproject.toml

# Final runner stage
FROM python:3.12-slim AS runner

WORKDIR /app

# Copy virtual environment and installed packages from builder
COPY --from=builder /app/.venv /app/.venv
COPY app/ app/
COPY datasets/ datasets/

# Set up environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV GROQ_MODEL="llama-3.3-70b-versatile"

# Expose agent engine port
EXPOSE 8080

# Command to run local agent engine fastapi app
CMD ["python3", "-m", "app.agent_runtime_app"]
