# Infrastructure source files

This directory contains only artifacts needed to recreate or operate the Palm
Logistics AWS deployment. One-off SSM diagnostics and completed repair payloads
are intentionally not retained here.

## IAM

- `palm-logistics-ec2-trust-policy.json`: trust policy for the EC2 runtime role.
- `palm-logistics-github-deploy-trust-policy.json`: restricts GitHub OIDC access to the production environment of this repository.
- `palm-logistics-github-deploy-permissions-policy.json`: permits deployment through one SSM document to one application instance.
- `palm-logistics-provisioner-trust-policy.json`: temporary MFA-protected setup role trust policy. Remove this file when the live provisioning role is retired.

## Systems Manager

- `palm-logistics-bootstrap-commands.json`: reproducible one-time bootstrap for a replacement application instance.
- `palm-logistics-deploy-document.yaml`: ongoing deployment document invoked by GitHub Actions.

## systemd

- `palm-logistics.service`: source definition for the application service installed on EC2.

Operational history belongs in the local deployment checklist or AWS command
history, not in permanent one-command JSON files.
