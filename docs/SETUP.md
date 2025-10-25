# Dendrite Setup Guide

Complete setup instructions for running Dendrite locally.

## Prerequisites

- Docker Engine 20.10+ 
- Docker Compose 2.0+
- At least 8GB RAM recommended for 8B models
- (Optional) NVIDIA GPU with nvidia-docker for GPU acceleration

## Quick Start

### 1. Clone and Configure

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration if needed
nano .env
```

### 2. Start the System

```bash
# Start everything with Docker Compose
docker-compose up -d

# Or use the setup script
./setup-ollama.sh
```

This will:
- Start the Ollama container
- Wait for it to be healthy
- Pull the default model (llama3.1:8b)
- Make the API available at `http://localhost:11434`

### 3. Configure Strava API (Optional)

If you want to use Strava integration:

## Strava API Authentication Setup

The agent requires **BOTH authentication methods** for full functionality:

1. **API Token** (`.strava_token`) - For official API v3 endpoints
   - Required for: `getMyActivities` (fetch your own activities with detailed stats)
   - Uses: Bearer token authentication

2. **Session Cookies** (`.strava_cookies`) - For web frontend endpoints  
   - Required for: `getDashboardFeed` (friends' feed), `getActivityKudos` (kudos details), `updateActivity`
   - Uses: Cookie-based authentication with CSRF tokens

**Important:** Most queries need BOTH files! For example, "Get my activities and who gave kudos" requires the token (to fetch activities) AND cookies (to fetch kudos per activity).

### Getting Your API Token (Required for getMyActivities)

The API token is required for fetching your own activities with detailed stats.

#### Quick Method (Testing/Personal Use):

1. **Get your access token from Strava's API settings:**
   - Go to https://www.strava.com/settings/api
   - Create an app (if you haven't)
   - Note your `Client ID` and `Client Secret`

2. **Manual token generation:**
   - Visit: `https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all,profile:read_all`
   - Authorize the app
   - You'll be redirected to `http://localhost?code=AUTHORIZATION_CODE`
   - Copy the authorization code

3. **Exchange for token:**
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=YOUR_CLIENT_ID \
     -d client_secret=YOUR_CLIENT_SECRET \
     -d code=AUTHORIZATION_CODE \
     -d grant_type=authorization_code
   ```

4. **Save token:**
   ```bash
   echo '{
     "access_token": "your_access_token",
     "refresh_token": "your_refresh_token",
     "expires_at": timestamp
   }' > .strava_token
   ```

#### Automated Method:

Use the provided script:
```bash
./scripts/get_strava_token.sh
```

### Getting Your Session Cookies (Required for kudos, dashboard, updates)

Session cookies are required for web frontend endpoints (kudos details, friends' feed, activity updates).

#### Method 1: Browser DevTools (Easiest)

1. **Log into Strava** in your browser
2. **Open DevTools**: F12 or Right-click → Inspect
3. **Go to Network tab**
4. **Reload** the page (Ctrl+R / Cmd+R)
5. **Click any request** to strava.com
6. **Find "Cookie" header** in Request Headers
7. **Copy the entire cookie string**

Example cookie string:
```
_strava4_session=abc123...; CloudFront-Key-Pair-Id=xyz...
```

8. **Save to file:**

**Option A: Raw String Format** (simpler):
```bash
echo "_strava4_session=abc123...; CloudFront-Key-Pair-Id=xyz..." > .strava_cookies
```

**Option B: JSON Format** (more structured):
```bash
cat > .strava_cookies << 'EOF'
[
  {"name": "_strava4_session", "value": "abc123...", "domain": ".strava.com"},
  {"name": "CloudFront-Key-Pair-Id", "value": "xyz...", "domain": ".strava.com"}
]
EOF
```

**Both formats work!** The code automatically detects which format you use.

#### Method 2: Browser Extension

Use a cookie export extension (e.g., "EditThisCookie", "Cookie-Editor"):
1. Export Strava cookies as JSON
2. Save to `.strava_cookies`

**Important:** Cookies expire when you log out of Strava. If tools stop working, re-export cookies.

### Token Refresh

API tokens expire after 6 hours. The agent automatically refreshes them when needed.

Manual refresh:
```bash
./scripts/refresh_token.sh
```

### Quick Test

Test if authentication is working:
```bash
# Test API token
./start-agent.sh --goal "How many activities this month?"

# Test cookies
./start-agent.sh --goal "Who gave me kudos today?"
```

## Model Selection

### Recommended Models (8B Parameter Range)

- **llama3.1:8b** - Meta's Llama 3.1 (Recommended, balanced performance)
- **llama3.2:3b** - Smaller, faster variant
- **mistral:7b-instruct-v0.3** - Excellent instruction following
- **gemma2:9b** - Google's Gemma 2

### Auto-detect Best Model

The system can automatically detect and select the best model for your hardware:

```bash
./manage-models.sh auto
```

This will:
- Detect available RAM/VRAM
- Check for GPU support
- Select appropriate model size
- Pull the model automatically

### Manual Model Selection

Edit `.env`:
```bash
DEFAULT_MODEL=llama3.1:8b
```

Then pull the model:
```bash
./scripts/manage-models.sh pull llama3.1:8b
```

## GPU Support

### Linux with NVIDIA GPU

1. Install NVIDIA drivers and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. Configure `.env`:
   ```bash
   USE_GPU=auto   # or true/false
   ```

3. Run setup:
   ```bash
   ./setup-ollama.sh
   ```

### WSL (Windows Subsystem for Linux)

#### Docker Desktop Method (Recommended):

1. Install latest NVIDIA Windows driver
2. In Docker Desktop (Windows): Settings → Resources → WSL Integration
   - Enable your distro
   - Ensure GPU support is enabled
3. Restart Docker Desktop and WSL: `wsl --shutdown`

#### Native dockerd in WSL:

```bash
# In WSL
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo service docker restart
```

Verify GPU support:
```bash
docker info | grep -i runtimes    # should include nvidia
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

## Running Your First Goal

```bash
# Start the agent with a natural language goal
./start-agent.sh --goal "How many running activities did I have this month?"

# Or use a predefined instruction
./start-agent.sh --once --instruction test_count_runs
```

## Troubleshooting

### Container won't start
```bash
# Check Docker daemon
docker info

# Check container logs
docker logs ollama

# Remove and recreate
./stop-ollama.sh --remove
./setup-ollama.sh
```

### API not responding
```bash
# Check if container is running
docker ps | grep ollama

# Check API health
curl http://localhost:11434/api/tags

# Restart container
docker restart ollama
```

### Model download stuck
```bash
# Check container logs
docker logs -f ollama

# Free up space if needed
docker system prune -a

# Try smaller model
# Edit .env and set: DEFAULT_MODEL=llama3.2:3b
```

### Port already in use
Edit `.env` and change:
```bash
OLLAMA_PORT=11435  # or any other available port
```

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand how Dendrite works
- Check [USAGE.md](USAGE.md) for advanced usage patterns
- Explore example instructions in `instructions/`
