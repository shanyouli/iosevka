# copy nixos-iosevka package;
{
  stdenv,
  lib,
  buildNpmPackage,
  cctools,
  ttfautohint-nox,
  private-build-plans ? ./private-build-plans.toml,
  pname,
  callPackages,
  importNpmLock,
}: let
  nv = (callPackages ../_sources/generated.nix {}).iosevka;
in
  buildNpmPackage rec {
    inherit pname;
    inherit (nv) src version;
    npmDeps = importNpmLock {
      npmRoot = nv.src; # ifd
    };

    npmConfigHook = importNpmLock.npmConfigHook;

    nativeBuildInputs =
      [
        ttfautohint-nox
      ]
      ++ lib.optionals stdenv.hostPlatform.isDarwin [
        # libtool
        cctools
      ];
    configurePhase = ''
      runHook preConfigure
      cp -v ${private-build-plans} private-build-plans.toml
      runHook postConfigure
    '';

    buildPhase = ''
      export HOME=$TMPDIR
      runHook preBuild
      npm run build --no-update-notifier --targets ttf::$pname -- --jCmd=$NIX_BUILD_CORES --verbose=9
      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall
      mkdir -p $out
      cp -avL dist/${pname}/* $out
      runHook postInstall
    '';

    enableParallelBuilding = true;

    meta = with lib; {
      homepage = "https://typeof.net/Iosevka/";
      downloadPage = "https://github.com/be5invis/Iosevka/releases";
      description = "Versatile typeface for code, from code";
      longDescription = ''
        Iosevka is an open-source, sans-serif + slab-serif, monospace +
        quasi‑proportional typeface family, designed for writing code, using in
        terminals, and preparing technical documents.
      '';
      license = licenses.ofl;
      platforms = platforms.all;
    };
  }
