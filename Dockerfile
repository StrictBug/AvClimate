FROM python:3.10-slim

# 1. Create a non-root user (Hugging Face security requirement)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# 2. Copy dependencies and install them
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 3. Copy the rest of your application code
COPY --chown=user . .

# 4. Hugging Face strictly routes incoming traffic to port 7860
EXPOSE 7860

# 5. Launch your app (Adjust 'main:app' if your entrypoint file is named differently)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]