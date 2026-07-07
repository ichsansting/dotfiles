{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.work;
  on = child: cfg.enable && cfg.${child}.enable;
in
{
  options.dotfiles.work = import ../../lib/module-options.nix { inherit lib; } ./module.json;

  # Tracked work files (plain .aws/config etc. + encrypted fish secrets) are
  # deployed by the shared files activation — see lib/files-activation.nix.
  config = lib.mkMerge [
    (lib.mkIf (on "aws-tools") {
      home.packages = [
        pkgs.awscli2
        pkgs.docker
        pkgs.ast-grep
      ];
    })

    (lib.mkIf (on "granted") {
      programs.granted = {
        enable = true;
        enableFishIntegration = true;
      };
    })

    (lib.mkIf (on "env") {
      home.sessionVariables = {
        ANTHROPIC_BASE_URL = "https://litellm.tvlk.cloud";
        ANTHROPIC_DEFAULT_SONNET_MODEL = "claude-sonnet-5";
        ANTHROPIC_DEFAULT_HAIKU_MODEL = "claude-haiku-4.5";
        ANTHROPIC_DEFAULT_OPUS_MODEL = "claude-opus-4.8";

        SEARXNG_ENDPOINT = "http://172.17.0.1:8080";
        TF_PLUGIN_CACHE_DIR = "${config.home.homeDirectory}/.terraform.d/plugin-cache";
        NODE_TLS_REJECT_UNAUTHORIZED = "0";
      };
    })
  ];
}
