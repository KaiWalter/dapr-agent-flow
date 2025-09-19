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
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = import nixpkgs {inherit system;};
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
          redis
          curl
          python313Packages.virtualenv
        ];
        darwinPackages = with pkgs; [
          python
          dapr-cli
          zsh
          sqlite
          redis
          curl
          python313Packages.virtualenv
        ];
      in {
        devShells.default = pkgs.mkShell {
          packages =
            if isDarwin
            then darwinPackages
            else linuxPackages;

          shellHook = ''
            export LD_LIBRARY_PATH=${libPath}:$LD_LIBRARY_PATH

            VENV_DIR=".venv"
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creating Python virtualenv (with pip) at $VENV_DIR"
              ${pkgs.python313Packages.virtualenv}/bin/virtualenv --python=${python}/bin/python "$VENV_DIR"
            fi

            # shellcheck disable=SC1091
            source "$VENV_DIR/bin/activate"

            if [ ! -x "$VENV_DIR/bin/pip" ]; then
              echo "pip missing inside venv – attempting fallback bootstrap via get-pip.py"
              TMP_GET_PIP=$(mktemp)
              if curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$TMP_GET_PIP"; then
                "$VENV_DIR/bin/python" "$TMP_GET_PIP" --upgrade || echo "Fallback pip bootstrap failed" >&2
              else
                echo "Could not download get-pip.py (offline?)" >&2
              fi
              rm -f "$TMP_GET_PIP"
            fi

            if [ -x "$VENV_DIR/bin/pip" ]; then
              pip install --upgrade --quiet pip wheel setuptools >/dev/null 2>&1 || true
            fi

            exec ${pkgs.zsh}/bin/zsh -i -l
          '';
        };
      }
    );
}
