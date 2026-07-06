{ lib, ... }:

let
  # Standalone home-manager reads the target user from the environment
  # (flake eval runs with --impure); fail early with a clear message instead
  # of producing empty username/homeDirectory in minimal shells.
  requireEnv =
    name:
    let
      v = builtins.getEnv name;
    in
    if v == "" then throw ("dotfiles: $" + name + " must be set (run with --impure)") else v;

  # Module set is auto-discovered from modules/*/module.json — no list to
  # maintain here. Profile = committed preset + local overrides; see
  # lib/profile.nix.
  discovered = import ./lib/modules.nix { inherit lib; };
  profile = import ./lib/profile.nix { inherit lib; };
in
{
  imports = discovered.imports ++ [ ./lib/files-activation.nix ];

  # Feed the resolved profile straight into the dotfiles.* option tree.
  # Git identity comes from the preset's settings, not from hardcoded values.
  dotfiles = profile.modules // {
    vcs = profile.modules.vcs // {
      user = {
        name = profile.settings.git.name or "";
        email = profile.settings.git.email or "";
      };
    };
  };

  home.username = requireEnv "USER";
  home.homeDirectory = requireEnv "HOME";
  home.stateVersion = "24.11";

  programs.home-manager.enable = true;
}
