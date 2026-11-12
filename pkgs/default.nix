{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.emacs-nox;
  # Release-table entry from upstream c16559abef25f0210b36dc1c789d2632d1b39d7f.
  originalCore = ((pkgs.emacsPackagesFor scope.original).elpaca).overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ../native/emacs31-date.patch ];
  });
  core = pkgs.runCommand "elpaca-manager" { } ''
    mkdir -p "$out"
    for directory in ${scope.originalCore}/share/emacs/site-lisp/elpa/*; do
      cp -r "$directory"/. "$out/"
    done
  '';
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      emacs = toString scope.original.src;
      elpaca = toString scope.originalCore.src;
      managerPatch = builtins.hashFile "sha256" ../native/emacs31-date.patch;
      builder = builtins.hashFile "sha256" ../lisp/build.el;
      integration = builtins.hashFile "sha256" ../lisp/activate.el;
    }
  );
  cli = scope.callPackage ./cli/default.nix { inherit nixpkgsSrc purifierSrc; };
  buildElpacaProject = scope.callPackage ./build-elpaca-project/default.nix { };
})
