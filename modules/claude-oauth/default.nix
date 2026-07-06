{
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.claude-oauth;
in
{
  options.dotfiles.claude-oauth = import ../../lib/module-options.nix { inherit lib; } ./module.json;

  config = lib.mkIf cfg.enable { };
}
