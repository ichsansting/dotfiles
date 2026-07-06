# Resolves the machine profile: committed preset + local overrides.
#
# Machine state is read from a STRING path (getEnv-derived) so Nix never
# copies it to the store — it lives outside the repo and is written only by
# the TUI:
#
#   ~/.local/state/dotfiles/profile.json
#   { "preset": "work", "overrides": { "modules": {...}, "settings": {...} } }
#
# Presets are flake-relative (in-store): presets/<name>.json. The merge is
# lib.recursiveUpdate (same semantics as the Python side), then sanitized
# against the discovered module set so unknown JSON keys are ignored instead
# of tripping option checks.
{ lib }:
let
  discovered = import ./modules.nix { inherit lib; };

  home = builtins.getEnv "HOME";
  statePath = home + "/.local/state/dotfiles/profile.json"; # string, not ./-relative
  state =
    if home != "" && builtins.pathExists statePath then
      builtins.fromJSON (builtins.readFile statePath)
    else
      { };

  # default.json is the base; other presets carry only their diff and are
  # layered over it (mirrors load_preset on the Python side).
  presetName = state.preset or "default";
  defaultPreset = lib.importJSON ../presets/default.json;
  namedPreset = lib.importJSON (../presets + "/${presetName}.json");
  preset =
    if presetName == "default" then defaultPreset else lib.recursiveUpdate defaultPreset namedPreset;
  merged = lib.recursiveUpdate preset (state.overrides or { });

  moduleConfig = lib.mapAttrs (
    mod: meta:
    let
      raw = (merged.modules or { }).${mod} or { };
      children = raw.children or { };
    in
    {
      enable = raw.enable or false;
    }
    // lib.mapAttrs (child: _: {
      enable = children.${child} or true;
    }) (meta.children or { })
  ) discovered.meta;
in
{
  preset = presetName;
  modules = moduleConfig; # shaped exactly like the dotfiles.* option tree
  settings = merged.settings or { };
}
