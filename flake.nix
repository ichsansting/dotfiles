{
  description = "Personal home-manager dotfiles — Linux & macOS, standalone (no nix-darwin)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    home-manager = {
      url = "github:nix-community/home-manager/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    { nixpkgs, home-manager, ... }:
    let
      system = builtins.currentSystem; # requires --impure
      pkgs = nixpkgs.legacyPackages.${system};

      # Python env for the TUI (needs textual). Activation scripts use plain
      # pkgs.python3 (stdlib only) — kept separate to keep the activation
      # closure small.
      pyEnv = pkgs.python3.withPackages (ps: [ ps.textual ]);

      # The TUI app: wraps the Python package with all runtime deps in PATH
      # and sets env vars the Python code reads at runtime.
      tui = pkgs.writeShellApplication {
        name = "dotfiles-tui";
        runtimeInputs = [
          pyEnv
          pkgs.sops
          pkgs.age
          pkgs.openssh
          home-manager.packages.${system}.default
        ];
        text = ''
          export PYTHONPATH="${./pkg}"
          export DOTFILES_SOPS_BIN="${pkgs.sops}/bin/sops"
          export DOTFILES_AGE_BIN="${pkgs.age}/bin/age"
          export DOTFILES_AGE_KEYGEN_BIN="${pkgs.age}/bin/age-keygen"
          # Pass the repo root so the TUI can locate modules/, presets/ etc.
          DOTFILES_REPO="$(pwd)"
          export DOTFILES_REPO
          exec ${pyEnv}/bin/python3 -m dotfiles.tui "$@"
        '';
      };
    in
    {
      packages.${system} = {
        inherit tui;
        default = tui;
      };

      apps.${system} =
        let
          tuiApp = {
            type = "app";
            program = "${tui}/bin/dotfiles-tui";
          };
        in
        {
          tui = tuiApp;
          default = tuiApp;
        };

      devShells.${system}.default = pkgs.mkShell {
        packages = [
          (pkgs.python3.withPackages (ps: [
            ps.textual
            ps.pytest
            ps.pytest-asyncio
          ]))
          pkgs.ruff
          pkgs.sops
          pkgs.age
          pkgs.openssh
          pkgs.nixfmt
        ];
        shellHook = ''
          export PYTHONPATH="$PWD/pkg"
        '';
      };

      # Single home configuration. Module selection comes from the preset +
      # overrides in ~/.local/state/dotfiles/profile.json (read at eval time
      # under --impure); falls back to presets/default.json.
      homeConfigurations."default" = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        modules = [ ./home.nix ];
      };
    };
}
