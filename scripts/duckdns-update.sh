#!/usr/bin/env bash
# Actiavte domain
curl -fsS "https://www.duckdns.org/update?domains=${DUCK_DOMAIN}&token=${DUCK_TOKEN}&ip=" \
  || echo "DuckDNS update failed"

# Print Domain Name
printf "Domain: http://${DUCK_DOMAIN}.duckdns.org"