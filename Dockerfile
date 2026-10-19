# Serves the latest committed report. The snapshot is taken on a laptop with
# `hermes-triage fetch`; the server never needs a GitHub token.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY site/ /srv/site/
COPY reports/ /srv/site/reports/
EXPOSE 80
