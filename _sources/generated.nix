# This file was generated by nvfetcher, please do not modify it manually.
{ fetchgit, fetchurl, fetchFromGitHub, dockerTools }:
{
  iosevka = {
    pname = "iosevka";
    version = "v33.2.5";
    src = fetchFromGitHub {
      owner = "be5invis";
      repo = "Iosevka";
      rev = "v33.2.5";
      fetchSubmodules = false;
      sha256 = "sha256-2yIkANG5hnath2EHiRXSKEflFoler9syz4e3AU5jxgU=";
    };
  };
  nerd-font-patcher = {
    pname = "nerd-font-patcher";
    version = "v3.4.0";
    src = fetchurl {
      url = "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.4.0/FontPatcher.zip";
      sha256 = "sha256-qPEeUR7Xxp6WaAhYwGtQpkPqd1LibVzRPdXlzFOrF2A=";
    };
  };
}
