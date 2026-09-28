{
  description = "Screen share in the browser for ReMarkable tablets";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f:
        nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs: rec {
        pipes-and-paper-enhanced = pkgs.callPackage ./package.nix { };
        default = pipes-and-paper-enhanced;
      });

      apps = forAllSystems (pkgs: rec {
        pipes-and-paper-enhanced = {
          type = "app";
          program = "${self.packages.${pkgs.system}.pipes-and-paper-enhanced}/bin/pipes-and-paper-enhanced";
        };
        default = pipes-and-paper-enhanced;
      });

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps: [ ps.websockets ]))
            pkgs.openssh
          ];
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixpkgs-fmt);
    };
}
