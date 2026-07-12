set -gx ANTHROPIC_BASE_URL https://litellm.tvlk.cloud
set -gx ANTHROPIC_DEFAULT_SONNET_MODEL claude-sonnet-5
set -gx ANTHROPIC_DEFAULT_HAIKU_MODEL claude-haiku-4.5
set -gx ANTHROPIC_DEFAULT_OPUS_MODEL claude-opus-4.8

set -gx SEARXNG_ENDPOINT http://172.17.0.1:8080
set -gx TF_PLUGIN_CACHE_DIR $HOME/.terraform.d/plugin-cache
set -gx NODE_TLS_REJECT_UNAUTHORIZED 0
