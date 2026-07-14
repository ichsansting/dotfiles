set -gx EDITOR hx
set -gx VISUAL hx
set -gx PAGER bat
set -gx MANPAGER "bat -l man -p"

set -gx XDG_CONFIG_HOME $HOME/.config
set -gx XDG_DATA_HOME $HOME/.local/share
set -gx XDG_CACHE_HOME $HOME/.cache
set -gx XDG_STATE_HOME $HOME/.local/state

# isolate's unshare --map-root-user maps only the calling uid, so files owned
# by the real host root (e.g. /etc/ssh/ssh_config.d/*) show up as nobody
# inside the namespace, tripping ssh's strict ownership check on Include'd
# system config. -F skips /etc/ssh/ssh_config entirely and reads only ours.
set -gx GIT_SSH_COMMAND "ssh -F $HOME/.ssh/config"
