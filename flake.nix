{
  description = "Ephemeral personal-shell launcher — flake package assembly";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      # Bundle package membership is data, not Nix code: each bundle's
      # existing files.json (the same manifest the core materialize module
      # reads for its file list — see pkg/dotfiles/core/materialize.py) may
      # carry a "packages" array of nixpkgs attribute names. This lets
      # bundles/<name>/ stay the single place a bundle's contents are
      # defined; adding a bundle never requires touching this file.
      bundleNames =
        if builtins.pathExists ./bundles then builtins.attrNames (builtins.readDir ./bundles) else [ ];

      bundlePackageNames =
        bundle:
        let
          manifest = ./bundles + "/${bundle}/files.json";
        in
        if builtins.pathExists manifest then
          (builtins.fromJSON (builtins.readFile manifest)).packages or [ ]
        else
          [ ];
    in
    {
      # packages.<system>.<bundle-name> — one buildEnv per bundle, addressable
      # as flake installables (e.g. `nix shell .#vcs`). `nix shell` merges
      # multiple installables' PATHs itself, so a resolved bundle list needs
      # no separate join step beyond passing each bundle as its own arg.
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        nixpkgs.lib.genAttrs bundleNames (
          bundle:
          pkgs.buildEnv {
            name = "dotfiles-bundle-${bundle}";
            paths = map (n: pkgs.${n}) (bundlePackageNames bundle);
          }
        )
      );

      # apps.<system>.default — `nix run` with no args: the flake's default
      # app (ticket 15). An interactive fzf preset picker (bin/launch) that
      # wires together isolation (bin/isolate), secrets bootstrap +
      # materialize (bin/launch-inner, calling pkg/dotfiles/core), and package
      # assembly (bin/assemble). fzf/age/sops/python3 are this app's own
      # runtime inputs, distinct from the per-bundle packages above.
      apps = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          launch = pkgs.writeShellApplication {
            name = "launch";
            runtimeInputs = [
              pkgs.fzf
              pkgs.age
              pkgs.sops
              pkgs.python3
            ];
            text = ''exec "${self}/bin/launch"'';
          };
        in
        {
          default = {
            type = "app";
            program = "${launch}/bin/launch";
          };
        }
      );
    };
}
