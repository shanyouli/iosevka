{
  description = "Custom iosevka font builds";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
  };

  outputs = inputs @ {flake-parts, ...}:
    flake-parts.lib.mkFlake {inherit inputs;} ({self, ...}: let
      inherit (inputs.nixpkgs) lib;
      isTermFont = f: let
        attrs = builtins.fromTOML (builtins.readFile f);
        pname = builtins.head (builtins.attrNames attrs.buildPlans);
      in ("term" == attrs.buildPlans.${pname}.spacing);
      mapTomls = dir: let
        isTomlFile = n: v: v == "regular" && (lib.hasSuffix ".toml" n);
        getPname = f:
          builtins.head (builtins.attrNames (builtins.fromTOML (builtins.readFile f)).buildPlans);
      in (lib.filterAttrs (n: v: v != null)
        (lib.mapAttrs' (n: v: (
            if (isTomlFile n v)
            then
              (let
                f = dir + "/${n}";
                pname = getPname f;
              in
                lib.nameValuePair pname f)
            else lib.nameValuePair "" null
          ))
          (builtins.readDir dir)));
    in {
      imports = [
        # To import a flake module
        # 1. Add foo to inputs
        # 2. Add foo as a parameter to the outputs function
        # 3. Add here: foo.flakeModule
      ];
      systems = ["x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin"];
      perSystem = {
        config,
        self',
        inputs',
        pkgs,
        system,
        ...
      }: {
        # Per-system attributes can be defined here. The self' and inputs'
        # module parameters provide easy access to attributes of the same
        # system.

        # Equivalent to  inputs'.nixpkgs.legacyPackages.hello;
        # packages.default = pkgs.hello;
        legacyPackages = inputs.nixpkgs.legacyPackages.${system}.extend self.overlays.default;
        # packages =
        #   (inputs.nixpkgs.legacyPackages.${system}.extend self.overlays.default)
        #   // {
        #     default = pkgs.hello;
        #   };
        apps = {
          ci = {
            type = "app";
            program = pkgs.writeTextFile rec {
              name = "ci";
              executable = true;
              destination = "/bin/${name}";
              text = let
                attrs = mapTomls ./src;
                nerdfonts =
                  lib.filterAttrs (_: v: v == true)
                  (lib.mapAttrs' (
                      n: v:
                        lib.nameValuePair n (isTermFont v)
                    )
                    attrs);
              in ''
                #!${pkgs.nushell}/bin/nu
                let packageName = "${lib.escape ["\"" "\\"] (builtins.toJSON (builtins.attrNames attrs))}" | from json
                let DIST = $env.PWD | path join "dist"
                mkdir $DIST
                for $i in $packageName {
                  print $"::group:::(ansi green_underline)build ($i) font..."
                  nix build $".#($i).base" -L
                  cd ./result
                  ^zip -9 -r $"($DIST)/($i).zip" */*
                  cd ..
                  print "::endgroup::"
                }
                let nerdnames = "${lib.escape ["\"" "\\"] (builtins.toJSON (builtins.attrNames nerdfonts))}" | from json
                for $i in $nerdnames {
                  print $"::group:::(ansi green_underline)build ($i) font..."
                  nix build $".#($i).nerd"  -L
                  cd ./result
                  ^zip -9 -r $"($DIST)/($i)-nerd.zip" */*
                  cd ..
                  print "::endgroup::"
                }
              '';
              checkPhase = ''${pkgs.nushell}/bin/nu --commands "nu-check --debug '$target'"'';
            };
          };
          upnvfetcher = {
            type = "app";
            program = pkgs.writeTextFile rec {
              name = "upnvfether";
              executable = true;
              destination = "/bin/${name}";
              text = ''
                #!${pkgs.nushell}/bin/nu
                let key_args = [ "-r" "10" "-j" "3" "--commit-changes"]
                let nvfetcher_config = $env.HOME | path join ".config" "nvfetcher.toml"
                if ($nvfetcher_config | path exists) {
                  let key_args = $key_args | append "-k"
                  let key_args = $key_args | append $nvfetcher_config
                } else if (($env.PWD | path join "secrets.toml") | path exists) {
                  let key_args = $key_args | append "-k"
                  let key_args = $key_args | append ($env.PWD | path join "secrets.toml")
                }
                with-env { NIX_PATH: "nixpkgs=${inputs.nixpkgs}" } {
                  print $"::group::(ansi green_underline)Update source by nvfetcher(ansi reset)..."
                  ${pkgs.nvfetcher}/bin/nvfetcher ...$key_args
                  print $"::endgroup::"
                }
              '';
              checkPhase = ''${pkgs.nushell}/bin/nu --commands "nu-check --debug '$target'"'';
            };
          };
        };
      };
      flake = {
        # The usual flake attributes can be defined here, including system-
        # agnostic ones like nixosModule and system-enumerating ones, although
        # those are more easily expressed in perSystem.
        overlays.default = final: prev: let
          buildFn = n: v:
            lib.nameValuePair n (lib.makeScope final.newScope (self: (let
              base = self.callPackage ./src/base.nix {
                pname = n;
                private-build-plans = v;
              };
            in
              lib.mkMerge [
                {
                  inherit base;
                  ttf = final.runCommand "${n}-ttf" {} ''
                    dest=$out/share/fonts/truetype
                    mkdir -p $dest
                    cp -avL ${base}/TTF/*.ttf $dest
                  '';
                }
                (
                  lib.mkIf (isTermFont v)
                  rec {
                    nerd = final.stdenvNoCC.mkDerivation {
                      pname = "${n}-nerd";
                      version = base.version;
                      src = base;
                      nativeBuildInputs = [prev.nerd-font-patcher];
                      buildPhase = ''
                        set -x
                        trap 'set +x' ERR
                        mkdir -p $out
                        for file in ./TTF/*.ttf ; do
                          nerd-font-patcher \
                            --mono \
                            --careful \
                            --complete \
                            --no-progressbars \
                            --outputdir $out $file &>/dev/null
                        done
                        set +x
                      '';
                      dontInstall = true;
                    };
                    ttf-nerd = final.runCommand "${n}-ttf-nerd" {} ''
                      dest=$out/share/fonts/truetype
                      mkdir -p $dest
                      cp -avL ${nerd}/*.ttf $dest
                    '';
                  }
                )
              ])));
        in
          lib.mapAttrs' buildFn (mapTomls ./src);
      };
    });
}
