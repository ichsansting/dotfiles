{
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.env;
  hd = config.home.homeDirectory;
in
{
  options.dotfiles.env = import ../../lib/module-options.nix { inherit lib; } ./module.json;

  config = lib.mkIf cfg.enable {
    xdg.enable = true;
    xdg.userDirs.enable = true;
    xdg.userDirs.setSessionVariables = false;

    home.sessionVariables = {
      EDITOR = "hx";
      VISUAL = "hx";
      PAGER = "bat";
      MANPAGER = "bat -l man -p";

      XDG_CONFIG_HOME = "${hd}/.config";
      XDG_DATA_HOME = "${hd}/.local/share";
      XDG_CACHE_HOME = "${hd}/.cache";
      XDG_STATE_HOME = "${hd}/.local/state";
    };
  };
}
