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
          stdenv.cc.cc.lib
          zlib
          openssl
          c-ares
          dapr-cli
          bash
          zsh
          podman
          podman-compose
          docker-compose
          slirp4netns
          fuse-overlayfs
          netavark
          aardvark-dns
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

            ${pkgs.lib.optionalString (!isDarwin) ''
              # Expose Podman's Docker-compatible socket so tools like Dapr can connect
              if [ -z "$XDG_RUNTIME_DIR" ]; then
                export XDG_RUNTIME_DIR="/run/user/$(id -u)"
              fi
              export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
              if [ ! -S "$XDG_RUNTIME_DIR/podman/podman.sock" ]; then
                mkdir -p "$XDG_RUNTIME_DIR/podman"
                echo "Starting Podman API service for Docker compatibility..."
                if ! pgrep -u "$UID" -f "podman system service" >/dev/null 2>&1; then
                  (nohup ${pkgs.podman}/bin/podman system service --time=0 >/dev/null 2>&1 & disown) || true
                  # Wait briefly for the socket to appear
                  for i in $(seq 1 50); do
                    [ -S "$XDG_RUNTIME_DIR/podman/podman.sock" ] && break
                    sleep 0.1
                  done
                fi
              fi
            ''}

            # API keys
            export OPENAI_API_KEY="$(op item get OpenAI --fields key --reveal)"

            # Ensure /bin/bash exists and points to the devshell bash
            if [ ! -e /bin/bash ] || [ "$(readlink -f /bin/bash)" != "$(command -v bash)" ]; then
              sudo ln -sf "$(command -v bash)" /bin/bash 2>/dev/null || true
            fi

            # Make docker-compose available and compatible with Podman
            if ! command -v docker-compose >/dev/null 2>&1; then
              if command -v podman-compose >/dev/null 2>&1; then
                ln -sf "$(command -v podman-compose)" "$HOME/.local/bin/docker-compose" 2>/dev/null || true
                export PATH="$HOME/.local/bin:$PATH"
              fi
            fi

            # hand off to an interactive login zsh
            exec ${pkgs.zsh}/bin/zsh -i -l
          '';
        };
      }
    );
}
