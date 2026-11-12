{
  lib,
  runCommand,
  writeText,
  python3,
  fetchurl,
  fetchgit,
  purifier,
  sdkVersion,
  original,
  core,
  git,
  texinfo,
  gnutar,
  gzip,
  ...
}@scope:
{
  src,
  lockFile ? src + "/elpaca-purifier.lock.json",
  nativeLockFile ? src + "/elpaca-lock.el",
  configFile ? "init.el",
  emacsArgs ? [ ],
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } {
      inherit src lockFile nativeLockFile;
    }
  );
  prepared = import ./environment.nix scope { inherit lock fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        "result"
        "__pycache__"
        "elpaca"
        "eln-cache"
      ]);
  };
  driver = lib.fileset.toSource {
    root = ../..;
    fileset = lib.fileset.unions [
      ../../elpaca_purifier/layout.py
      ../../lisp/activate.el
      ../../native/check.py
    ];
  };
  data = writeText "elpaca-lock-data.json" (builtins.toJSON lock.data);
  project =
    runCommand "elpaca-configuration"
      {
        nativeBuildInputs = [
          git
          texinfo
        ];
      }
      ''
        cp -r ${source} source
        chmod -R u+w source
        ${python3}/bin/python3 ${driver}/native/check.py "$PWD/source" "$TMPDIR/private" \
          ${prepared.output} ${data} ${original}/bin/emacs ${lib.escapeShellArg configFile} ${lib.escapeShellArgs emacsArgs}
        ${lib.optionalString doCheck checkCommand}
        mkdir -p "$out"
        cp -r ${source}/. "$out/"
      '';
  release =
    runCommand "elpaca-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
          test -d ${project}
          cp -r ${source} release-source
          chmod -R u+w release-source
          mkdir -p release-source/elpaca/repos/elpaca release-source/elpaca/builds/elpaca
          cp -rL ${prepared.tree}/. release-source/elpaca/repos/
          cp -r ${prepared.builds}/. release-source/elpaca/builds/
          cp -r ${core}/. release-source/elpaca/repos/elpaca/
          cp -r ${core}/. release-source/elpaca/builds/elpaca/
          cp ${writeText "elpaca-lock.el" lock.data.native} release-source/elpaca-lock.el
        chmod -R u+w release-source
          mkdir -p "$out"
          tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/emacs-config.tar.gz" -C release-source .
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
