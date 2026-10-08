#!/bin/sh
set -e

# Bind mount this file to /entrypoint2.sh then override entrypoint in the compose

# allow docker-gen to see Docker API
export DOCKER_HOST=unix:///var/run/docker.sock

entrypoint_log() {
  if [ -z "${NGINX_ENTRYPOINT_QUIET_LOGS:-}" ]; then
    echo "$@"
  fi
}

if /usr/bin/find "/docker-entrypoint.d/" -mindepth 1 -maxdepth 1 -type f -print -quit 2>/dev/null | read v; then
  entrypoint_log "$0: /docker-entrypoint.d/ is not empty, will attempt to perform configuration"

  entrypoint_log "$0: Looking for shell scripts in /docker-entrypoint.d/"
  find "/docker-entrypoint.d/" -follow -type f -print | sort -V | while read -r f; do
    case "$f" in
      *.envsh)
        if [ -x "$f" ]; then
          entrypoint_log "$0: Sourcing $f";
          . "$f"
        else
          # warn on shell scripts without exec bit
          entrypoint_log "$0: Ignoring $f, not executable";
        fi
        ;;
      *.sh)
        if [ -x "$f" ]; then
          entrypoint_log "$0: Launching $f";
          "$f"
        else
          # warn on shell scripts without exec bit
          entrypoint_log "$0: Ignoring $f, not executable";
        fi
        ;;
      *) entrypoint_log "$0: Ignoring $f";;
    esac
  done

  entrypoint_log "$0: Configuration complete; ready for start up"
else
  entrypoint_log "$0: No files found in /docker-entrypoint.d/, skipping configuration"
fi

# kick off docker-gen: template → swagger‐initializer.js; keep watching
docker-gen \
  -watch \
  /etc/docker-gen/templates/swagger.tmpl \
  /usr/share/nginx/html/swagger-initializer.js &

# finally, start swagger-ui's nginx
exec nginx -g 'daemon off;'
