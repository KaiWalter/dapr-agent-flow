{
  description = "Dev shell with Python 3.13 (venv), Dapr CLI (Podman for Linux, OrbStack for Darwin)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python313;
        isDarwin = pkgs.stdenv.isDarwin;
        libPath = pkgs.lib.makeLibraryPath [
          pkgs.stdenv.cc.cc.lib
          pkgs.zlib
          pkgs.openssl
          pkgs.c-ares
        ];
        linuxPackages = with pkgs; [
           python
          dapr-cli
          zsh
          sqlite
        ];
        darwinPackages = with pkgs; [
          python
          dapr-cli
          zsh
          sqlite
        ];
      in {
        devShells.default = pkgs.mkShell {
          packages = if isDarwin then darwinPackages else linuxPackages;

          shellHook = ''
            export LD_LIBRARY_PATH=${libPath}:$LD_LIBRARY_PATH

            VENV_DIR=".venv"
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating Python venv at $VENV_DIR"
              ${python}/bin/python -m venv "$VENV_DIR"
            fi

            # shellcheck disable=SC1091
            source "$VENV_DIR/bin/activate"

            # Ensure pip exists and is up to date inside the venv
            python -m ensurepip -U >/dev/null 2>&1 || true
            python -m pip install --upgrade pip wheel >/dev/null 2>&1 || true
          
            # Ensure /bin/bash exists and points to the devshell bash
            if [ ! -e /bin/bash ] || [ "$(readlink -f /bin/bash)" != "$(command -v bash)" ]; then
              sudo ln -sf "$(command -v bash)" /bin/bash 2>/dev/null || true
            fi

            # hand off to an interactive login zsh
            exec ${pkgs.zsh}/bin/zsh -i -l
          '';
        };
      }
    );
}
