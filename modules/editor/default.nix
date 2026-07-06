{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.editor;
  on = child: cfg.enable && cfg.${child}.enable;
in
{
  options.dotfiles.editor = import ../../lib/module-options.nix { inherit lib; } ./module.json;

  config = lib.mkMerge [
    (lib.mkIf (on "language-servers") {
      home.packages = with pkgs; [
        nixd
        bash-language-server
        fish-lsp
        markdown-oxide
        ty
        ruff
        typescript-language-server
        nixfmt
      ];
    })

    (lib.mkIf (on "helix") {
      programs.helix = {
        enable = true;
        defaultEditor = true;
        settings = {
          theme = "catppuccin_mocha";
          editor = {
            auto-pairs = true;
            line-number = "relative";
            file-picker.hidden = false;
            indent-guides.render = true;

            cursor-shape = {
              insert = "bar";
              normal = "block";
              select = "underline";
            };

            statusline = {
              left = [
                "mode"
                "spinner"
                "file-name"
                "file-modification-indicator"
              ];
              center = [ "version-control" ];
              right = [
                "diagnostics"
                "selections"
                "position"
                "file-encoding"
              ];
            };
          };
        };

        # Language servers are resolved from PATH, so helix degrades
        # gracefully when the language-servers child is toggled off.
        languages = {
          language-server = {
            nixd.command = "nixd";

            bash-language-server = {
              command = "bash-language-server";
              args = [ "start" ];
            };

            fish-lsp = {
              command = "fish-lsp";
              args = [ "start" ];
            };

            markdown-oxide = {
              command = "markdown-oxide";
              args = [ "server" ];
            };

            ty = {
              command = "ty";
              args = [ "server" ];
            };

            ruff-lsp = {
              command = "ruff";
              args = [
                "server"
                "--preview"
              ];
            };

            typescript-language-server = {
              command = "typescript-language-server";
              args = [ "--stdio" ];
            };

            # rust-analyzer is intentionally NOT installed via Nix here.
            # Install it through `mise` or `rustup component add rust-analyzer`
            # so it stays in sync with the active Rust toolchain version.
            rust-analyzer.command = "rust-analyzer";
          };

          language = [
            {
              name = "nix";
              language-servers = [ "nixd" ];
              formatter.command = "nixfmt";
              auto-format = true;
            }
            {
              name = "bash";
              language-servers = [ "bash-language-server" ];
            }
            {
              name = "fish";
              language-servers = [ "fish-lsp" ];
            }
            {
              name = "markdown";
              language-servers = [ "markdown-oxide" ];
            }
            {
              name = "python";
              language-servers = [
                "ty"
                "ruff-lsp"
              ];
              formatter = {
                command = "ruff";
                args = [
                  "format"
                  "-"
                ];
              };
              auto-format = true;
            }
            {
              name = "typescript";
              language-servers = [ "typescript-language-server" ];
            }
            {
              name = "javascript";
              language-servers = [ "typescript-language-server" ];
            }
            {
              name = "rust";
              language-servers = [ "rust-analyzer" ];
            }
          ];
        };
      };
    })
  ];
}
