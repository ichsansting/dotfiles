# ponytail: dotfiles-old's "done" plugin (desktop notification when a long
# command finishes) isn't ported — it needs a plugin manager (fisher) or
# home-manager's vendor_conf.d wiring to install; add back with fisher if
# the notification is missed.

abbr -a ls 'eza --icons'
abbr -a ll 'eza --icons -la'
abbr -a lt 'eza --icons --tree'
abbr -a cat bat
abbr -a grep rg
abbr -a find fd
abbr -a top btop
abbr -a htop btop
abbr -a du dust
abbr -a df duf
abbr -a diff delta
abbr -a fm yazi

abbr -a claude 'BUN_JSC_useJIT=0 claude'

abbr -a gst 'git status'
abbr -a glg 'git log --oneline --graph --decorate --all'
abbr -a gco 'git checkout'
abbr -a gbr 'git branch'
abbr -a gunstage 'git reset HEAD --'
abbr -a glast 'git log -1 HEAD'
