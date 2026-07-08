{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.dotfiles.vcs;
  on = child: cfg.enable && cfg.${child}.enable;
in
{
  options.dotfiles.vcs =
    (import ../../lib/module-options.nix { inherit lib; } ./module.json)
    // {
      user = {
        name = lib.mkOption {
          type = lib.types.str;
          default = "";
          description = "git user.name (fed from the preset's settings.git)";
        };
        email = lib.mkOption {
          type = lib.types.str;
          default = "";
          description = "git user.email (fed from the preset's settings.git)";
        };
      };
    };

  config = lib.mkMerge [
    {
      assertions = [
        {
          assertion = !(on "git") || (cfg.user.name != "" && cfg.user.email != "");
          message = "dotfiles.vcs: settings.git.{name,email} must be set in the active preset";
        }
      ];
    }

    (lib.mkIf (on "git") {
      programs.git = {
        enable = true;

        signing = {
          format = "ssh";
          key = "~/.ssh/id_ed25519";
          signByDefault = true;
        };

        settings = {
          user = {
            name = cfg.user.name;
            email = cfg.user.email;
          };
          pull.rebase = true;
          init.defaultBranch = "main";
          "gpg \"ssh\"" = {
            allowedSignersFile = "~/.ssh/allowed_signers";
          };
        };

        ignores = [
          ".DS_Store"
          ".direnv/"
          "*.local"
          ".mise.local.toml"
        ];
      };
    })

    (lib.mkIf (on "delta") {
      programs.delta = {
        enable = true;
        enableGitIntegration = true;
        options = {
          features = "side-by-side line-numbers";
          syntax-theme = "Catppuccin Mocha";
        };
      };
    })

    (lib.mkIf (on "gh") {
      programs.gh = {
        enable = true;
        settings = {
          git_protocol = "ssh";
          editor = "hx";
        };
      };
    })

    (lib.mkIf (on "ssh") {
      programs.ssh = {
        enable = true;
        enableDefaultConfig = false;

        settings."github.com" = {
          User = "git";
          IdentityFile = "~/.ssh/id_ed25519";
          AddKeysToAgent = "yes";
        };
      };

      # Runs after the shared files activation (lib/files-activation.nix)
      # decrypted ~/.ssh/id_ed25519, deriving the pubkey + allowed_signers.
      home.activation.setupSshPublicKey =
        lib.hm.dag.entryAfter [ "dotfilesFiles" ] ''
          ${pkgs.python3}/bin/python3 "${../../pkg}/dotfiles/activate.py" pubkey \
            --ssh-keygen "${pkgs.openssh}/bin/ssh-keygen" \
            --email "${cfg.user.email}"
        '';
    })
  ];
}
