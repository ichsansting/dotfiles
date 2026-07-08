# Wires tracked-file deployment into home-manager activation as a single
# entry: activate.py deploy-all deploys every enabled module's files, then
# prunes files recorded in ~/.local/state/dotfiles/deployed.json that fell
# out of the desired set (module/child disabled, file untracked, module
# deleted) — undeploy is declarative. Files with local edits are kept and
# warned about, never deleted.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  discovered = import ./modules.nix { inherit lib; };
  helper = ../pkg; # copied to the store; activate.py bootstraps sys.path itself

  enabled = builtins.filter (n: config.dotfiles.${n}.enable) discovered.names;
  enableFlags = lib.concatMapStrings (n: " --enable \"${n}\"") enabled;

  # Children toggled off skip their files (files.json entries with a
  # matching "child") via --disable-child module:child.
  disabledChildren = lib.concatMap (
    n:
    let
      children = builtins.attrNames (discovered.meta.${n}.children or { });
    in
    map (c: "${n}:${c}") (builtins.filter (c: !config.dotfiles.${n}.${c}.enable) children)
  ) enabled;
  childFlags = lib.concatMapStrings (dc: " --disable-child \"${dc}\"") disabledChildren;
in
{
  # No mkIf: this must run even with every module disabled so prune can
  # clean up what earlier generations deployed.
  home.activation.dotfilesFiles = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    ${pkgs.python3}/bin/python3 "${helper}/dotfiles/activate.py" deploy-all \
      --modules-root "${../modules}" \
      --sops-bin "${pkgs.sops}/bin/sops"${enableFlags}${childFlags}
  '';
}
