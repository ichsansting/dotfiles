# Single source of truth for module enumeration.
#
# A module is a directory under modules/ containing BOTH default.nix and
# module.json. module.json (description + children) is also read by the
# Python side (dotfiles.core.modules), so Nix and the TUI can never disagree.
{ lib }:
let
  dir = ../modules;
  entries = builtins.readDir dir;
  names = builtins.filter (
    n:
    entries.${n} == "directory"
    && builtins.pathExists (dir + "/${n}/default.nix")
    && builtins.pathExists (dir + "/${n}/module.json")
  ) (builtins.attrNames entries);
in
{
  inherit names;
  imports = map (n: dir + "/${n}") names;
  meta = lib.genAttrs names (n: lib.importJSON (dir + "/${n}/module.json"));
}
