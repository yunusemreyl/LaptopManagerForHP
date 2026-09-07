{
  description = "Omen Space: HP Laptop manager for Linux";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        packages = {
          omen-space = pkgs.rustPlatform.buildRustPackage {
            pname = "omen-space";
            version = "2.0.1";

            src = ./.;

            cargoLock = {
              lockFile = ./Cargo.lock;
            };

            nativeBuildInputs = with pkgs; [
              pkg-config
            ];

            buildInputs = with pkgs; [
              dbus
              glib
              gtk4
              libadwaita
            ];

            buildPhase = ''
              for crate in omen-space-daemon omen-cli omen-tray omen-gui; do
                cargo build --release --manifest-path src/$crate/Cargo.toml
              done
            '';

            installPhase = ''
              mkdir -p $out/libexec/omen-space
              mkdir -p $out/bin
              mkdir -p $out/lib/systemd/system
              mkdir -p $out/lib/sysusers.d
              mkdir -p $out/lib/udev/rules.d
              mkdir -p $out/share/dbus-1/system.d
              mkdir -p $out/share/dbus-1/services
              mkdir -p $out/share/applications
              mkdir -p $out/share/pixmaps
              mkdir -p $out/share/omen-space/assets

              cp src/omen-space-daemon/target/release/omen-space-daemon $out/libexec/omen-space/omen-space-daemon
              cp src/omen-cli/target/release/omen-cli $out/bin/
              cp src/omen-tray/target/release/omen-tray $out/bin/
              cp src/omen-gui/target/release/omen-gui $out/bin/

              cp data/omen-space-daemon.service $out/lib/systemd/system/
              cp data/sysusers.d/omen-space.conf $out/lib/sysusers.d/
              cp data/99-omen-space.rules $out/lib/udev/rules.d/
              cp data/org.hp.omen.conf $out/share/dbus-1/system.d/
              cp data/org.hp.OmenSpace.desktop $out/share/applications/
              cp data/org.hp.OmenSpace.service $out/share/dbus-1/services/
              cp src/omen-gui/assets/omenspace.png $out/share/pixmaps/
              cp -r src/omen-gui/assets/* $out/share/omen-space/assets/

              # Fix systemd paths
              find $out/lib/systemd/system -type f -exec sed -i "s|/usr/libexec|$out/libexec|g" {} +
            '';
          };

          default = self.packages.${system}.omen-space;
        };
      }) // {
      nixosModules.default = { config, lib, pkgs, ... }:
        with lib;
        let
          cfg = config.programs.omen-space;
        in {
          options.programs.omen-space = {
            enable = lib.mkEnableOption "Omen Space: HP Laptop manager for Linux";
          };

          config = mkIf cfg.enable {
            environment.systemPackages = [ self.packages.${pkgs.system}.omen-space ];
            services.dbus.packages = [ self.packages.${pkgs.system}.omen-space ];
            systemd.packages = [ self.packages.${pkgs.system}.omen-space ];
            
            systemd.services.omen-space-daemon.wantedBy = [ "multi-user.target" ];
            
            users.groups.omen-hw = {};

            boot.kernelModules = [ "hp-wmi" "hp-omen-extra" ];

            boot.extraModulePackages = [
              (pkgs.linuxPackages.callPackage ({ stdenv, kernel }: stdenv.mkDerivation {
                pname = "omen-space-driver";
                version = "2.0.1";
                src = "${self.packages.${pkgs.system}.omen-space.src}/driver";
                nativeBuildInputs = kernel.moduleBuildDependencies;
                makeFlags = [
                  "KERNELRELEASE=${kernel.modDirVersion}"
                  "KDIR=${kernel.dev}/lib/modules/${kernel.modDirVersion}/build"
                  "INSTALL_MOD_PATH=$(out)"
                ];
                installPhase = ''
                  make -C ${kernel.dev}/lib/modules/${kernel.modDirVersion}/build M=$(pwd) INSTALL_MOD_PATH=$out modules_install
                '';
              }) { kernel = config.boot.kernelPackages.kernel; })
            ];
          };
        };
    };
}
