# Offline Setup Guide

This guide explains how to use Forgetful in environments without internet access or where HuggingFace is blocked (corporate firewalls, air-gapped systems, etc.).

## Model Cache Location

Forgetful caches FastEmbed models in a persistent directory:

- **Linux**: `~/.local/share/forgetful/models/fastembed/`
- **macOS**: `~/Library/Application Support/forgetful/models/fastembed/`
- **Windows**: `%LOCALAPPDATA%\forgetful\models\fastembed\`

You can override this location with the `FASTEMBED_CACHE_DIR` environment variable.

## Required Models

Forgetful requires two models (total ~193MB):

1. **Embedding Model**: `BAAI/bge-small-en-v1.5` (~65MB)
   - Used for generating vector embeddings from text

2. **Reranking Model**: `Xenova/ms-marco-MiniLM-L-12-v2` (~129MB)
   - Used for reranking search results by relevance

## Option 1: Download from GitHub (Recommended for Offline)

Pre-packaged models are available on GitHub:

```bash
# Download models from GitHub releases
wget https://github.com/scottrbk/forgetful-models/releases/download/v1.0.0/fastembed-models.tar.gz

# Extract to cache directory (Linux/macOS)
mkdir -p ~/.local/share/forgetful/models/
tar -xzf fastembed-models.tar.gz -C ~/.local/share/forgetful/models/

# Windows (PowerShell)
# mkdir $env:LOCALAPPDATA\forgetful\models
# tar -xzf fastembed-models.tar.gz -C $env:LOCALAPPDATA\forgetful\models\
```

After extraction, verify the directory structure:
```
~/.local/share/forgetful/models/fastembed/
├── models--Xenova--ms-marco-MiniLM-L-12-v2/
│   └── snapshots/
│       └── [hash]/
│           ├── config.json
│           ├── model.onnx
│           └── tokenizer files...
└── models--qdrant--bge-small-en-v1.5-onnx-q/
    └── snapshots/
        └── [hash]/
            ├── config.json
            ├── model_optimized.onnx
            └── tokenizer files...
```

## Option 2: Auto-Download (Requires Internet)

If you have internet access, Forgetful will automatically download models on first run:

```bash
uvx forgetful-ai
# First run: Downloading embedding models (~180MB). This may take a minute...
```

Models are cached for future use.

## Option 3: Transfer from Another Machine

If you have the models cached on another machine:

```bash
# On source machine (with models)
cd ~/.local/share/forgetful/models/
tar -czf fastembed-models.tar.gz fastembed/

# Transfer fastembed-models.tar.gz to target machine (USB, network, etc.)

# On target machine (offline)
mkdir -p ~/.local/share/forgetful/models/
tar -xzf fastembed-models.tar.gz -C ~/.local/share/forgetful/models/
```

## Custom Cache Directory

To use a different cache location:

```bash
# Set environment variable
export FASTEMBED_CACHE_DIR=/opt/models/fastembed

# Run Forgetful
uvx forgetful-ai
```

Or create a `.env` file:
```bash
# .env
FASTEMBED_CACHE_DIR=/opt/models/fastembed
```

## Verification

To verify models are cached correctly, check for the presence of `.onnx` files:

```bash
# Linux/macOS
find ~/.local/share/forgetful/models/fastembed -name "*.onnx"

# Should show:
# ~/.local/share/forgetful/models/fastembed/models--qdrant--bge-small-en-v1.5-onnx-q/snapshots/[hash]/model_optimized.onnx
# ~/.local/share/forgetful/models/fastembed/models--Xenova--ms-marco-MiniLM-L-12-v2/snapshots/[hash]/model.onnx
```

## Troubleshooting

### Models not found
If Forgetful can't find the models:
1. Verify the cache directory exists
2. Check file permissions (should be readable by your user)
3. Ensure the directory structure matches the expected format (see above)

### Still downloading despite cached models
- Check that `FASTEMBED_CACHE_DIR` points to the correct location
- Verify models are in the correct subdirectory structure
- Check logs for cache directory being used

### Custom models
To use different embedding models, set:
```bash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RERANKING_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

Note: Custom models will auto-download if not cached (requires internet).

## Corporate Environment Workflow

For completely air-gapped corporate environments:

1. **On internet-connected machine**:
   ```bash
   # Download models from GitHub
   wget https://github.com/ScottRBK/forgetful/releases/download/models-v1.0.0/fastembed-models-v1.0.0.tar.gz
   ```

2. **Transfer file** via approved method (USB, internal network, etc.)

3. **On air-gapped machine**:
   ```bash
   # Install forgetful
   pip install forgetful-ai

   # Extract models
   mkdir -p ~/.local/share/forgetful/models/
   tar -xzf fastembed-models.tar.gz -C ~/.local/share/forgetful/models/

   # Run
   uvx forgetful-ai
   ```

## Docker Deployments

For Docker, you can pre-cache models in the image:

```dockerfile
FROM python:3.12-slim

# Install forgetful-ai
RUN pip install forgetful-ai

# Copy pre-downloaded models
COPY fastembed-models.tar.gz /tmp/
RUN mkdir -p /root/.local/share/forgetful/models/ && \
    tar -xzf /tmp/fastembed-models.tar.gz -C /root/.local/share/forgetful/models/ && \
    rm /tmp/fastembed-models.tar.gz

# Set cache directory (optional if using default)
ENV FASTEMBED_CACHE_DIR=/root/.local/share/forgetful/models/fastembed

CMD ["forgetful-ai"]
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/scottrbk/forgetful/issues
- Model Downloads: https://github.com/scottrbk/forgetful-models/releases
