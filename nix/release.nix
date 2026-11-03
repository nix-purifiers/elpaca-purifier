{
  root,
  lockFile,
  nativeLockFile,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  scope = import ./scope.nix {
    inherit pkgs nixpkgsSrc;
    purifierSrc = /. + "@purifier@";
  };
in
(scope.buildElpacaProject {
  src = /. + root;
  lockFile = /. + lockFile;
  nativeLockFile = /. + nativeLockFile;
}).release
