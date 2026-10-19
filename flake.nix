{
  description = "Custom iosevka font builds — Nix 只提供构建环境，不获取任何依赖";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05"; # 固定 stable 分支
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } (
      { self, ... }:
      {
        systems = [
          "x86_64-linux"
          "aarch64-linux"
          "aarch64-darwin"
          "x86_64-darwin"
        ];

        perSystem =
          { pkgs, ... }:
          {
            # 只提供工具链：node / ttfautohint / fontTools / gftools / fontforge / 打包工具
            # Iosevka 源码、nerd-font-patcher、LXGW 字体全部由 sources.json + scripts/fetch_sources.py 获取
            # 注意：font-patcher 依赖 python 的 fontforge 模块（nixpkgs 中也是 propagatedBuildInputs）
            devShells.default = pkgs.mkShell {
              packages = [
                pkgs.nodejs_22
                pkgs.ttfautohint-nox
                (pkgs.python3.withPackages (ps: [
                  ps.fonttools
                  ps.fontforge # font-patcher 必需
                  ps.gftools # update-nameids
                ]))
                pkgs.zip
                pkgs.unzip
                pkgs.p7zip
                pkgs.jq
                pkgs.curl
                pkgs.wget
                pkgs.git
                pkgs.cacert
                pkgs.just
              ];
              shellHook = ''
                echo "Iosevka build env ready（Nix 不提供源码 / 字体补丁器）"
                [ -f vendor/iosevka/package.json ] || \
                  echo "⚠️  vendor/iosevka 为空，先运行 python3 scripts/fetch_sources.py" >&2
                [ -f vendor/FontPatcher/font-patcher ] || \
                  echo "⚠️  vendor/FontPatcher 为空，先运行 python3 scripts/fetch_sources.py" >&2
              '';
            };
          };
      }
    );
}
