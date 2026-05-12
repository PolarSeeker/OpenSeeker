#!/bin/bash
# OpenSeeker Environment Variable Configuration Script
# Usage: source setup_env.sh or . setup_env.sh

# ============================================
# LLM API Configuration (for generate_answer.py and llm_tool_openseeker.py)
# ============================================
# OpenSeeker base URL (can be a single URL or multiple comma-separated URLs)
# Example: http://127.0.0.1:30018/v1/completions
export OPENSEEKER_BASE_URL="${OPENSEEKER_BASE_URL:-YOUR_OPENSEEKER_BASE_URL}"
# Example: OpenSeeker-30b
export OPENSEEKER_MODEL="${OPENSEEKER_MODEL:-YOUR_MODEL_NAME}"

# ============================================
# Scorer API Configuration (for eval.py)
# ============================================
# Scorer model name
# Example: oss
export SCORER_MODEL_NAME="${SCORER_MODEL_NAME:-YOUR_SCORER_MODEL_NAME}"
# Scorer URL (can be a single URL or multiple comma-separated URLs)
# Example: http://127.0.0.1:8890/v1
export SCORER_URLS="${SCORER_URLS:-YOUR_SCORER_URL}"
# Scorer API key (use "EMPTY" if no key required)
# Example: EMPTY
export SCORER_API_KEY="${SCORER_API_KEY:-YOUR_API_KEY}"

# ============================================
# Summary API Configuration (for visit.py)
# ============================================
# Configuration 1 (required)
# Example: oss
export SUMMARY_MODEL_NAME="${SUMMARY_MODEL_NAME:-YOUR_SUMMARY_MODEL_NAME}"
# Example: http://127.0.0.1:8890/v1
export SUMMARY_API_URL="${SUMMARY_API_URL:-YOUR_SUMMARY_API_URL}"
# Example: EMPTY (use "EMPTY" if no key required)
export SUMMARY_API_KEY="${SUMMARY_API_KEY:-YOUR_SUMMARY_API_KEY}"

# ============================================
# Jina API Configuration (for visit.py)
# ============================================
# Get your API key from https://jina.ai/
export JINA_API_KEYS="${JINA_API_KEYS:-YOUR_JINA_API_KEY}"

# ============================================
# Serper API Configuration (for search.py)
# ============================================
# Get your API key from https://serper.dev/
export SERPER_KEY_ID="${SERPER_KEY_ID:-YOUR_SERPER_API_KEY}"

# If you want to use Tavily for search, you can configure the following parameters. Use Serper by default.
# ============================================
# Tavily API Configuration (for search.py)
# ============================================
# Get your API key from https://app.tavily.com/
export TAVILY_API_KEY="${TAVILY_API_KEY:-YOUR_TAVILY_API_KEY}"
# Search provider: 'serper' (default) or 'tavily'
export SEARCH_PROVIDER="${SEARCH_PROVIDER:-serper}"
# ============================================
# E2B Sandbox Configuration (for llm_tool_openseeker_v2.py). 
# ============================================
# Get your API key from https://e2b.dev/. Used to create/connect remote Linux
# sandboxes for create_sandbox, run_command, run_python_code, upload, download.
export E2B_API_KEY="${E2B_API_KEY:-YOUR_E2B_API_KEY}"

# ============================================
# Other Configuration
# ============================================
# Visit tool configuration
export VISIT_SERVER_TIMEOUT="200"
export VISIT_SERVER_MAX_RETRIES="1"
export WEBCONTENT_MAXLENGTH="150000"
# Tool log configuration
export TOOL_LOG_MAX_CHARS="800"

mask_secret() {
    if [ -z "$1" ]; then
        echo "<unset>"
    elif [[ "$1" == YOUR_* ]]; then
        echo "<placeholder>"
    else
        echo "<set>"
    fi
}

echo "============================================"
echo "OpenSeeker Environment Variables Set"
echo "============================================"
echo "OPENSEEKER_BASE_URL: $OPENSEEKER_BASE_URL"
echo "OPENSEEKER_MODEL: $OPENSEEKER_MODEL"
echo "SCORER_URLS: $SCORER_URLS"
echo "SCORER_API_KEY: $(mask_secret "$SCORER_API_KEY")"
echo "SUMMARY_MODEL_NAME: $SUMMARY_MODEL_NAME"
echo "SUMMARY_API_URL: $SUMMARY_API_URL"
echo "SUMMARY_API_KEY: $(mask_secret "$SUMMARY_API_KEY")"
echo "JINA_API_KEYS: $(mask_secret "$JINA_API_KEYS")"
echo "SERPER_KEY_ID: $(mask_secret "$SERPER_KEY_ID")"
echo "TAVILY_API_KEY: $(mask_secret "$TAVILY_API_KEY")"
echo "SEARCH_PROVIDER: $SEARCH_PROVIDER"
echo "E2B_API_KEY: $(mask_secret "$E2B_API_KEY")"
echo "============================================"
