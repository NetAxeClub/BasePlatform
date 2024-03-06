
#!/bin/bash
docker-compose build --no-cache  base-web && docker-compose push base-web
docker-compose build base-backend && docker-compose push base-backend