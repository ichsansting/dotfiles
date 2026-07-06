# Auto-wires file deployment for every enabled module that has a files.json:
# one home.activation entry per module, calling activate.py deploy. Nothing
# to copy-paste inside individual modules.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  discovered = import ./modules.nix { inherit lib; };
  helper = ../pkg; # copied to the store; activate.py bootstraps sys.path itself
  withFiles = builtins.filter (
    n: builtins.pathExists (../modules + "/${n}/files.json")
  ) discovered.names;

  # Children that are toggled off skip their files (files.json entries with a
  # matching "child") via --disable-child.
  mkEntry =
    name:
    let
      children = builtins.attrNames (discovered.meta.${name}.children or { });
      disabled = builtins.filter (c: !config.dotfiles.${name}.${c}.enable) children;
      childFlags = lib.concatMapStrings (c: " --disable-child \"${c}\"") disabled;
    in
    lib.mkIf config.dotfiles.${name}.enable (
      lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        ${pkgs.python3}/bin/python3 "${helper}/dotfiles/activate.py" deploy \
          --module-dir "${../modules + "/${name}"}" \
          --sops-bin "${pkgs.sops}/bin/sops"${childFlags}
      ''
    );
in
{
  home.activation = lib.listToAttrs (
    map (n: lib.nameValuePair "dotfilesFiles_${n}" (mkEntry n)) withFiles
  );
}
