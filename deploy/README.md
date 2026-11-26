# Deploying JadwAI on one free server

The public demo runs on an Oracle Cloud Always Free virtual machine (Ampere A1, 4 OCPU, 24 GB memory, Ubuntu 24.04 ARM). Everything runs on that one machine:

- PostgreSQL, the API, the worker and Caddy run in Docker (`compose.yaml`).
- Ollama runs on the host with the fine-tuned `jai-candidate-v4` model.
- Caddy gets an HTTPS certificate automatically for `<ip-with-dashes>.sslip.io`, so no domain is needed.

The model runs on the CPU, so a model reply takes several minutes. Everything else is instant: forms, the built-in parser and JAI's built-in answers.

## First deployment

1. Create the instance. In the cloud console's security list, allow TCP 80 and 443. Add the public key `~/.ssh/jadwai_oracle.pub` when creating it.
2. From the Mac, copy the code, a cleaned copy of the demo database and the 150 MB v4 adapter:
   `bash deploy/push.sh <ip> --data`
   This also tries to start the site. On a fresh server it stops early, because Docker is not installed yet; that is expected.
3. On the server (`ssh -i ~/.ssh/jadwai_oracle ubuntu@<ip>`):
   - `bash ~/jadwai/deploy/server-setup.sh`: installs Docker and Ollama and opens the firewall. Log out and back in afterwards.
   - `bash ~/jadwai/deploy/build-model.sh`: downloads the base model and merges the adapter into `jai-candidate-v4`, exactly as on the Mac. This takes about 30 to 60 minutes.
   - `bash ~/jadwai/deploy/server-up.sh <ip>`: builds the images, restores the demo database, migrates, creates the restricted database roles and starts the site.

## Updates

`bash deploy/push.sh <ip>` copies the current code and rebuilds. The database on the server is kept.

## What stays private

- `deploy/.env`, `runtime.env`, `api.env` and `worker.env` hold the generated database passwords. They exist only on the server.
- `deploy/data/` holds the database copy. It is git-ignored.
- The API and worker connect with least-privilege roles. Only the one-off `migrate` and `provision` jobs use the owner role.
- Ollama listens only to the Docker networks; the firewall blocks it from the internet.
