{
  description = "Advanced HP Omen/Victus laptop manager for Linux with RGB, Fan, and MUX control";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: import nixpkgs { inherit system; };
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = pkgsFor system;
          pythonEnv = pkgs.python3.withPackages (ps: with ps; [
            pygobject3
            pydbus
            pycairo
            pystray
            pillow
          ]);
        in
        {
          omenctl = pkgs.stdenv.mkDerivation {
            pname = "omenctl";
            version = "1.6.6";

            src = ./.;

            nativeBuildInputs = with pkgs; [
              wrapGAppsHook4
              gobject-introspection
            ];

            buildInputs = with pkgs; [
              pythonEnv
              gtk4
              libadwaita
            ];

            installPhase = ''
              runHook preInstall

              mkdir -p $out/share/hp-manager/gui
              mkdir -p $out/share/hp-manager/images
              mkdir -p $out/libexec/hp-manager
              mkdir -p $out/share/dbus-1/system.d
              mkdir -p $out/lib/systemd/system
              mkdir -p $out/share/applications
              mkdir -p $out/bin
              mkdir -p $out/share/icons/hicolor/48x48/apps

              # Daemon files
              cp -r src/daemon/* $out/libexec/hp-manager/

              # GUI files
              cp -r src/gui/* $out/share/hp-manager/gui/
              if [ -d images ] && [ "$(ls -A images)" ]; then
                cp -r images/* $out/share/hp-manager/images/
                if [ -f images/omenctl.png ]; then
                  cp images/omenctl.png $out/share/icons/hicolor/48x48/apps/omenctl.png
                fi
              fi

              # CLI files
              if [ -f src/omen-cli.py ]; then
                cp src/omen-cli.py $out/libexec/hp-manager/
                chmod +x $out/libexec/hp-manager/omen-cli.py
                sed -i "1s|.*|#!${pythonEnv}/bin/python|" $out/libexec/hp-manager/omen-cli.py
                ln -sf $out/libexec/hp-manager/omen-cli.py $out/bin/omen
              fi
              if [ -f src/omen-tray.py ]; then
                cp src/omen-tray.py $out/libexec/hp-manager/
                chmod +x $out/libexec/hp-manager/omen-tray.py
                sed -i "1s|.*|#!${pythonEnv}/bin/python|" $out/libexec/hp-manager/omen-tray.py
                ln -sf $out/libexec/hp-manager/omen-tray.py $out/bin/omen-tray
              fi

              # System files
              for svc in fan rgb power mux platform; do
                  if [ -f "data/com.yyl.hpmanager.''${svc}.conf" ]; then
                      cp "data/com.yyl.hpmanager.''${svc}.conf" $out/share/dbus-1/system.d/
                  fi
                  if [ -f "data/hpm-''${svc}.service" ]; then
                      cp "data/hpm-''${svc}.service" $out/lib/systemd/system/
                  fi
              done
              if [ -f data/com.yyl.hpmanager.desktop ]; then
                cp data/com.yyl.hpmanager.desktop $out/share/applications/
              fi

              # Binary launcher
              cat > $out/bin/hp-manager << EOF
              #!/bin/sh
              cd $out/share/hp-manager/gui
              exec ${pythonEnv}/bin/python $out/share/hp-manager/gui/main_window.py "\$@"
              EOF
              chmod +x $out/bin/hp-manager
              ln -sf hp-manager $out/bin/omenctl

              # Patch paths
              find $out/share/dbus-1/system.d $out/lib/systemd/system $out/share/applications $out/share/hp-manager $out/libexec/hp-manager -type f -exec sed -i "s|/usr/|$out/|g" {} +
              find $out/lib/systemd/system -type f -exec sed -i "s|$out/bin/python3|${pythonEnv}/bin/python|g" {} +
              
              # Fix NixOS specific issues (mutable state in /etc and /bin/sleep)
              find $out -type f -exec sed -i "s|/etc/hp-manager|/var/lib/hp-manager|g" {} +
              find $out/lib/systemd/system -type f -exec sed -i "s|/bin/sleep|${pkgs.coreutils}/bin/sleep|g" {} +
              
              runHook postInstall
            '';
          };
          default = self.packages.${system}.omenctl;
        }
      );

      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.programs.omenctl;
        in {
          options.programs.omenctl = {
            enable = lib.mkEnableOption "OmenCtl: HP Laptop manager for Linux";
            loadCustomDriver = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Load the custom out-of-tree hp-wmi and hp-rgb-lighting kernel modules.";
            };
          };

          config = lib.mkIf cfg.enable {
            environment.systemPackages = [ self.packages.${pkgs.system}.omenctl ];
            
            services.dbus.packages = [ self.packages.${pkgs.system}.omenctl ];
            systemd.packages = [ self.packages.${pkgs.system}.omenctl ];
            
            systemd.services.hpm-fan.wantedBy = [ "multi-user.target" ];
            systemd.services.hpm-rgb.wantedBy = [ "multi-user.target" ];
            systemd.services.hpm-power.wantedBy = [ "multi-user.target" ];
            systemd.services.hpm-mux.wantedBy = [ "multi-user.target" ];
            systemd.services.hpm-platform.wantedBy = [ "multi-user.target" ];

            boot.extraModulePackages = lib.mkIf cfg.loadCustomDriver [
              (config.boot.kernelPackages.kernel.stdenv.mkDerivation {
                pname = "omenctl-driver";
                version = "1.6.6";
                src = "${self.packages.${pkgs.system}.omenctl.src}/driver";
                
                nativeBuildInputs = config.boot.kernelPackages.kernel.moduleBuildDependencies;
                
                makeFlags = [
                  "KDIR=${config.boot.kernelPackages.kernel.dev}/lib/modules/${config.boot.kernelPackages.kernel.modDirVersion}/build"
                ];

                installPhase = ''
                  mkdir -p $out/lib/modules/${config.boot.kernelPackages.kernel.modDirVersion}/extra
                  cp *.ko $out/lib/modules/${config.boot.kernelPackages.kernel.modDirVersion}/extra/
                '';
              })
            ];
            boot.kernelModules = lib.mkIf cfg.loadCustomDriver [ "hp-wmi" "hp-rgb-lighting" ];

            systemd.tmpfiles.rules = [
              "d /var/lib/hp-manager 0755 root root -"
            ];
          };
        };
    };
}
