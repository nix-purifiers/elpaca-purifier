{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  texinfo,
  cacert,
  nix-prefetch-git,
  original,
  core,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "elpaca-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/elpaca-purifier"
    cp -r elpaca_purifier pkgs lib-overlays lisp native "$out/lib/elpaca-purifier/"
    install -m755 bin/elpaca-purifier "$out/bin/elpaca-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/elpaca-purifier/pkgs/build-elpaca-project/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/elpaca-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
          texinfo
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default ELPACA_PURIFIER_GH ${gh}/bin/gh \
      --set ELPACA_PURIFIER_EMACS ${original}/bin/emacs \
      --set ELPACA_PURIFIER_CORE ${core} \
      --set ELPACA_PURIFIER_PREFETCH_GIT ${nix-prefetch-git}/bin/nix-prefetch-git \
      --set ELPACA_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set ELPACA_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/elpaca-purifier" "$out/bin/emacs" --add-flags '--native'
  '';
  meta = {
    description = "Emacs and Elpaca with locked Nix-resolved packages";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "elpaca-purifier";
  };
}
