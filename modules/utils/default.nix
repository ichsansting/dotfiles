{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.utils;
  on = child: cfg.enable && cfg.${child}.enable;
in
{
  options.dotfiles.utils = import ../../lib/module-options.nix { inherit lib; } ./module.json;

  config = lib.mkMerge [
    (lib.mkIf (on "search") {
      programs.fzf = {
        enable = true;
        enableFishIntegration = true;
      };

      home.packages = with pkgs; [
        ripgrep
        fd
      ];
    })

    (lib.mkIf (on "files") {
      home.packages = with pkgs; [
        eza
        yazi
        dust
        duf
      ];
    })

    (lib.mkIf (on "view") {
      programs.bat = {
        enable = true;
        config.theme = "Catppuccin Mocha";
      };

      home.packages = with pkgs; [ jq ];
    })

    (lib.mkIf (on "monitor") {
      home.packages = with pkgs; [ btop ];
    })

    (lib.mkIf (on "nix-tools") {
      home.packages = with pkgs; [
        nvd
        nix-tree
        comma
      ];
    })
  ];
}
