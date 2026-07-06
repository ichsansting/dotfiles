# Generates a module's option tree from its module.json:
#
#   dotfiles.<name>.enable            (default false)
#   dotfiles.<name>.<child>.enable    (default true — parent alone turns
#                                      everything on; children opt OUT)
#
# Usage in modules/<name>/default.nix:
#   options.dotfiles.<name> =
#     import ../../lib/module-options.nix { inherit lib; } ./module.json;
{ lib }:
metaPath:
let
  meta = lib.importJSON metaPath;
in
{
  enable = lib.mkEnableOption meta.description;
}
// lib.mapAttrs (child: desc: {
  enable = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = desc;
  };
}) (meta.children or { })
