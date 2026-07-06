{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.devenv;
  on = child: cfg.enable && cfg.${child}.enable;
in
{
  options.dotfiles.devenv = import ../../lib/module-options.nix { inherit lib; } ./module.json;

  # The ai child's tracked files (.claude skills) are deployed by the shared
  # files activation — see lib/files-activation.nix.
  config = lib.mkMerge [
    (lib.mkIf (on "mise") {
      programs.mise = {
        enable = true;
        enableFishIntegration = true;

        globalConfig = {
          settings = {
            idiomatic_version_file_enable_tools = [
              "python"
              "terraform"
            ];
            auto_install = true;
            python.uv_venv_auto = "source";
            pipx.uvx = true;
          };

          env = {
            UV_PYTHON = {
              value = "{{ tools.python.path }}";
              tools = true;
            };
          };

          tools = {
            # aube: a fast Node.js package manager (Rust-based, recommended over npm/pnpm).
            aube = "latest";
            # rust-analyzer is installed alongside the toolchain so versions stay in sync.
            rust = "stable";
            uv = "latest";
            bun = "latest";
            node = "latest";
            python = "3.13";
            "claude-code" = "latest";
            "github:iii-hq/iii" = "latest";
            "cargo:elio" = "latest";
          };
        };
      };
    })

    (lib.mkIf (on "direnv") {
      programs.direnv = {
        enable = true;
        enableFishIntegration = true;
        enableBashIntegration = true;
        nix-direnv.enable = true;
        config.global.load_dotenv = true;
      };
    })

    # ai: claude-code is installed via mise; the child owns the tracked
    # .claude files (tagged "child": "ai" in files.json), which the shared
    # files activation skips when the toggle is off.
  ];
}
