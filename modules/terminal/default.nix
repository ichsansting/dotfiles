{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.terminal;
  on = child: cfg.enable && cfg.${child}.enable;
in
{
  options.dotfiles.terminal = import ../../lib/module-options.nix { inherit lib; } ./module.json;

  config = lib.mkMerge [
    (lib.mkIf (on "fish") {
      programs.fish = {
        enable = true;
        plugins = [
          {
            name = "done";
            src = pkgs.fishPlugins.done.src;
          }
        ];

        shellAbbrs = {
          ls = "eza --icons";
          ll = "eza --icons -la";
          lt = "eza --icons --tree";
          cat = "bat";
          grep = "rg";
          find = "fd";
          top = "btop";
          htop = "btop";
          du = "dust";
          df = "duf";
          diff = "delta";
          fm = "yazi";

          claude = "BUN_JSC_useJIT=0 claude";

          gst = "git status";
          glg = "git log --oneline --graph --decorate --all";
          gco = "git checkout";
          gbr = "git branch";
          gunstage = "git reset HEAD --";
          glast = "git log -1 HEAD";
        };
      };
    })

    (lib.mkIf (on "starship") {
      programs.starship = {
        enable = true;

        settings = {
          palette = "catppuccin_mocha";
          format = lib.concatStrings [
            "$username"
            "$hostname"
            "$directory"
            "$git_branch"
            "$git_status"
            "$nix_shell"
            "$rust"
            "$python"
            "$nodejs"
            "$cmd_duration"
            "$line_break"
            "$character"
          ];

          directory = {
            style = "bold lavender";
            truncation_length = 4;
            truncate_to_repo = false;
          };

          git_branch = {
            symbol = " ";
            style = "bold mauve";
          };

          git_status = {
            style = "bold red";
            ahead = "⇡\${count}";
            behind = "⇣\${count}";
            diverged = "⇕⇡\${ahead_count}⇣\${behind_count}";
            modified = "!";
            untracked = "?";
            staged = "+";
            deleted = "✘";
          };

          nix_shell = {
            symbol = " ";
            style = "bold blue";
            format = "[$symbol$state]($style) ";
          };

          rust = {
            symbol = " ";
            style = "bold peach";
            detect_files = [ "Cargo.toml" ];
          };

          python = {
            symbol = " ";
            style = "bold yellow";
            detect_files = [
              "pyproject.toml"
              "requirements.txt"
              ".python-version"
            ];
          };

          nodejs = {
            symbol = " ";
            style = "bold green";
            detect_files = [
              "package.json"
              ".nvmrc"
              ".node-version"
            ];
          };

          character = {
            success_symbol = "[❯](bold green)";
            error_symbol = "[❯](bold red)";
          };

          cmd_duration = {
            min_time = 2000;
            style = "bold yellow";
          };

          palettes.catppuccin_mocha = {
            rosewater = "#f5e0dc";
            flamingo = "#f2cdcd";
            pink = "#f5c2e7";
            mauve = "#cba6f7";
            red = "#f38ba8";
            maroon = "#eba0ac";
            peach = "#fab387";
            yellow = "#f9e2af";
            green = "#a6e3a1";
            teal = "#94e2d5";
            sky = "#89dceb";
            sapphire = "#74c7ec";
            blue = "#89b4fa";
            lavender = "#b4befe";
            text = "#cdd6f4";
            subtext1 = "#bac2de";
            subtext0 = "#a6adc8";
            overlay2 = "#9399b2";
            overlay1 = "#7f849c";
            overlay0 = "#6c7086";
            surface2 = "#585b70";
            surface1 = "#45475a";
            surface0 = "#313244";
            base = "#1e1e2e";
            mantle = "#181825";
            crust = "#11111b";
          };
        };
      };
    })

    (lib.mkIf (on "atuin") {
      programs.atuin = {
        enable = true;
        enableFishIntegration = true;
        flags = [ "--disable-up-arrow" ];

        settings = {
          auto_sync = true;
          sync_frequency = "5m";
          search_mode = "fuzzy";
        };
      };
    })

    (lib.mkIf (on "zoxide") {
      programs.zoxide = {
        enable = true;
        enableFishIntegration = true;
      };
    })

    (lib.mkIf (on "zellij") {
      programs.zellij = {
        enable = true;
        enableFishIntegration = true;

        settings = {
          default_shell = "fish";
          mouse_mode = true;
          theme = "catppuccin-mocha";
          keybinds = {
            _children = [
              {
                shared_except = {
                  _args = [ "locked" ];
                  # Unbind Alt+Right in all non-locked modes.
                  # "Alt f" covers macOS Alacritty (and similar terminals) that encode
                  # Alt+Right as ESC+f (readline forward-word). "Alt Right" covers
                  # terminals that send proper CSI sequences (Linux, kitty, wezterm).
                  # See: https://github.com/zellij-org/zellij/issues/3850
                  unbind = [
                    "Alt f"
                    "Alt Right"
                  ];
                };
              }
            ];
          };
        };
      };
    })
  ];
}
