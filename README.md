    version: "2.3"
    services:
      ntfy:
        image: binwiederhier/ntfy
        container_name: ntfy
        command:
          - serve
        environment:
            NTFY_AUTH_FILE: "/userdb/user.db"
            NTFY_AUTH_DEFAULT_ACCESS: "deny-all"
        volumes:
          - /opt/ntfy/cache/ntfy:/var/cache/ntfy
          - /opt/ntfy/etc/ntfy:/etc/ntfy
          - /opt/ntfy/userdb/:/userdb/
        ports:
          - 4001:80
        healthcheck: # optional: remember to adapt the host:port to your environment
            test: ["CMD-SHELL", "wget -q --tries=1 http://localhost:80/v1/health -O - | grep -Eo '\"healthy\"\\s*:\\s*true' || exit 1"]
            interval: 60s
            timeout: 10s
            retries: 3
            start_period: 40s
        restart: unless-stopped
      ntfy-api:
        image: harbor-registry.atlantishq.de/ntfy-api
        depends_on:
            - ntfy
        environment:
            ACCESS_TOKEN: secret_here
            NTFY_AUTH_FILE: "/userdb/user.db"
        volumes:
          - /opt/ntfy/userdb/:/userdb/
