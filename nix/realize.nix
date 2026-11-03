{
  root,
  lockFile,
  nativeLockFile,
  sdk,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  scope = import ./scope.nix {
    inherit pkgs nixpkgsSrc;
    purifierSrc = /. + "@purifier@";
  };
  lock = import ./read-lock.nix { inherit (pkgs) lib; } {
    src = /. + root;
    lockFile = /. + lockFile;
    nativeLockFile = /. + nativeLockFile;
  };
  environment = scope.callPackage ./environment.nix { } { inherit lock; };
in
pkgs.writeText "elpaca-environment-profile.json" (
  builtins.toJSON {
    output = environment.output;
    sdk = builtins.storePath sdk;
  }
)
