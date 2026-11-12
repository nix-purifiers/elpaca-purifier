{
  lib,
  runCommand,
  fetchurl,
  fetchgit,
  writeText,
  python3,
  purifier,
  sdkVersion,
  original,
  core,
  git,
  texinfo,
  ...
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  fetched = purifier.tree (
    {
      name = "elpaca-git-sources";
      inherit
        runCommand
        fetchurl
        fetchgit
        writeText
        python3
        ;
      entries = checked.entries;
    }
    // fetchers
  );
  tree = runCommand "elpaca-native-repositories" { nativeBuildInputs = [ git ]; } ''
    mkdir -p "$out"
    ${lib.concatMapStringsSep "\n" (entry: ''
      mkdir -p "$out"/${lib.escapeShellArg entry.path}
      cp -r ${fetched}/${lib.escapeShellArg entry.path}/. "$out"/${lib.escapeShellArg entry.path}/
      chmod -R u+w "$out"/${lib.escapeShellArg entry.path}
      git -C "$out"/${lib.escapeShellArg entry.path} remote add origin ${lib.escapeShellArg entry.git.url}
    '') checked.entries}
  '';
  native = writeText "elpaca-lock.el" lock.data.native;
  selection = writeText "elpaca-recipes.json" (builtins.toJSON lock.data.recipes);
  builds =
    runCommand "elpaca-native-builds"
      {
        nativeBuildInputs = [
          original
          git
          texinfo
        ];
      }
      ''
          export HOME="$TMPDIR/home" ELPACA_PURIFIER_STATE="$TMPDIR/state"
          export ELPACA_PURIFIER_LOCK=${native} ELPACA_PURIFIER_SELECTION=${selection}
          export ELPACA_PURIFIER_BUILDS="$out"
        mkdir -p "$HOME" "$ELPACA_PURIFIER_STATE/elpaca/repos" "$ELPACA_PURIFIER_STATE/elpaca/builds"
          cp -rL ${tree}/. "$ELPACA_PURIFIER_STATE/elpaca/repos/"
          chmod -R u+w "$ELPACA_PURIFIER_STATE"
          ln -s ${core} "$ELPACA_PURIFIER_STATE/elpaca/repos/elpaca"
          ${original}/bin/emacs -Q --batch -L ${core} -l ${../../lisp/build.el}
      '';
  output =
    (writeText "elpaca-environment.json" (
      builtins.toJSON {
        inherit
          tree
          builds
          core
          native
          selection
          ;
        sdk = lock.data.sdk;
      }
    )).overrideAttrs
      (_: {
        passthru = { inherit builds tree; };
      });
in
assert lib.assertMsg (
  lock.data.sdk == sdkVersion
) "Elpaca SDK changed; run elpaca-purifier lock --update";
{
  inherit output tree builds;
}
