# Palm Logistics EC2 Deployment and CI/CD Guide

## 1. Deployment decision

Palm Logistics should not expose SSH or SQL Server to the internet for normal deployment.

The recommended path is:

```text
Developer -> GitHub main branch -> GitHub Actions
                                  -> GitHub OIDC
                                  -> temporary AWS credentials
                                  -> AWS Systems Manager Run Command
                                  -> EC2 application server
                                  -> systemd restarts Streamlit

User -> HTTPS -> Application Load Balancer -> Streamlit on EC2:8501

Streamlit EC2 -> private VPC connection -> SQL Server EC2:1433
Streamlit EC2 -> HTTPS:443 -> OpenRouter, Pinecone, Open-Meteo
```

This design has no inbound port `22`, no permanent AWS access keys in GitHub, and no SSM tunnel that management must start. The development SSM tunnel to `127.0.0.1:1433` is only for a developer workstation. The deployed application connects directly to the SQL Server's private address inside the VPC.

This is a hardened **single-instance deployment**. It is suitable for a controlled demonstration or small internal service after the mandatory security controls in this guide are complete. It is not a highly available or horizontally scalable platform.

The EC2 server may use an outbound GitHub connection to fetch code. For a private repository, that connection can use a read-only GitHub deploy key. This is different from allowing inbound SSH access to EC2.

## 2. Files used by this deployment

- `.github/workflows/deploy.yml`: validates the project and asks Systems Manager to deploy an exact commit.
- `infrastructure/ssm/palm-logistics-deploy-document.yaml`: custom SSM document that accepts only a validated commit SHA.
- `scripts/deploy_app.sh`: root-owned deployment runner that fetches the commit, synchronizes dependencies, restarts the service, performs health checks, and rolls back after a failed deployment.
- `scripts/deployment_smoke_test.py`: verifies application imports, SQL, OpenRouter embeddings, and Pinecone after deployment.
- `uv.lock`: locks the Python dependencies.
- `.python-version`: selects Python `3.12.13`.
- `/etc/palm-logistics/palm-logistics.env`: production configuration on EC2. This file is not part of Git.
- `/etc/systemd/system/palm-logistics.service`: keeps Streamlit running after logout or reboot.

Do not create a second `requirements.txt` for the server. This project already uses `pyproject.toml` and `uv.lock`.

## 3. Required AWS resources

Before starting, record these values:

```text
AWS account ID:        <AWS_ACCOUNT_ID>
AWS region:            eu-north-1
Application instance:  <APP_INSTANCE_ID>
Application SG:        <APP_SECURITY_GROUP_ID>
Database SG:           <DATABASE_SECURITY_GROUP_ID>
GitHub repository:     farazahmad-ai/palm-logistics-ai-assistant
GitHub environment:    palm-production
Database private host: <DATABASE_PRIVATE_IP_OR_DNS>
```

Use an Ubuntu 24.04 EC2 instance in the same VPC as the SQL Server. A private subnet is preferred. If the instance is private, it needs a NAT gateway or another controlled egress path because the application calls OpenRouter, Pinecone, Open-Meteo, GitHub, and package repositories over HTTPS.

For this dependency set, start with at least 4 GiB RAM and a 30 GiB encrypted gp3 volume. The AI models are remote, so a GPU is not required. Monitor memory and disk usage before reducing the instance size.

Attach an EC2 instance profile containing `AmazonSSMManagedInstanceCore`. The instance must appear as **Online** in AWS Systems Manager > Fleet Manager before continuing.

### 3.1 Connect the local repository to GitHub

This repository uses the public GitHub repository shown below. The local `origin`
remote is already configured; verify it before the first push:

```bash
git remote -v
```

Expected destination:

```text
https://github.com/farazahmad-ai/palm-logistics-ai-assistant.git
```

Because the repository is public, the application instance can clone it over
HTTPS without a deploy key:

```bash
sudo -u palmapp git clone \
  https://github.com/farazahmad-ai/palm-logistics-ai-assistant.git \
  /opt/palm-logistics/repository
```

## 4. Security groups

Use security-group references instead of copying changing private IP addresses into rules.

| Security group | Direction | Protocol/port | Source or destination | Purpose |
|---|---|---:|---|---|
| ALB SG | Inbound | TCP 443 | Approved corporate CIDR, VPN CIDR, or internet if intentionally public | User HTTPS access |
| ALB SG | Outbound | TCP 8501 | App SG | Forward requests to Streamlit |
| App SG | Inbound | TCP 8501 | ALB SG | Accept only load-balancer traffic |
| App SG | Inbound | TCP 22 | None | SSH is not required |
| App SG | Outbound | TCP 1433 | Database SG | SQL Server access |
| App SG | Outbound | TCP 443 | Approved egress/NAT path | AWS APIs and external AI/data APIs |
| Database SG | Inbound | TCP 1433 | App SG | Allow only the application server |
| Database SG | Inbound | TCP 1433 | Internet | Never allow |

For a short demonstration without an ALB, allow TCP `8501` on the App SG only from your current public IP. That exposes plain HTTP and is not the final production setup. Put an ALB with an ACM certificate in front of the app before giving access to management.

Do not allow internet-wide access until HTTPS and authentication are active. A public Streamlit page can expose operational data and consume paid API credits.

Systems Manager requires outbound HTTPS but no inbound rule. Do not open port `22` merely for GitHub Actions.

## 5. One-time EC2 bootstrap

Open AWS Systems Manager > Session Manager, start a session to the application instance, and run the following sections. Session Manager normally opens a root shell; keep `sudo` in the commands so they are also safe from an Ubuntu administrator shell.

### 5.1 Install operating-system packages

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git gnupg jq

ubuntu_version="$(. /etc/os-release && echo "${VERSION_ID}")"
curl -sSLO "https://packages.microsoft.com/config/ubuntu/${ubuntu_version}/packages-microsoft-prod.deb"
sudo dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb

sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

Confirm the SQL driver:

```bash
odbcinst -q -d
```

The output must include `ODBC Driver 18 for SQL Server`.

### 5.2 Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh
uv --version
```

`uv` will install the Python version specified by the repository when it synchronizes the project.

### 5.3 Create a dedicated service account

```bash
sudo useradd \
  --system \
  --create-home \
  --home-dir /var/lib/palm-logistics \
  --shell /usr/sbin/nologin \
  palmapp

sudo install -d -o palmapp -g palmapp -m 0750 /opt/palm-logistics
sudo install -d -o root -g palmapp -m 0750 /etc/palm-logistics
```

Do not run the web application as `root` or as the interactive `ubuntu` administrator account.

### 5.4 Clone the repository

For a public repository:

```bash
sudo -u palmapp git clone \
  https://github.com/farazahmad-ai/palm-logistics-ai-assistant.git \
  /opt/palm-logistics/repository
```

For a private repository, create a read-only GitHub deploy key for the `palmapp` account:

```bash
sudo -u palmapp install -d -m 0700 /var/lib/palm-logistics/.ssh
sudo -u palmapp ssh-keygen \
  -t ed25519 \
  -C "palm-logistics-ec2-read-only" \
  -f /var/lib/palm-logistics/.ssh/github_deploy_key \
  -N ""
sudo cat /var/lib/palm-logistics/.ssh/github_deploy_key.pub
```

Add the displayed public key in GitHub under **Repository > Settings > Deploy keys**. Leave **Allow write access** unchecked. Verify GitHub's published SSH host fingerprint, then add GitHub to `known_hosts`:

```bash
sudo -u palmapp ssh-keyscan github.com | \
  sudo -u palmapp tee /var/lib/palm-logistics/.ssh/known_hosts >/dev/null

sudo -u palmapp tee /var/lib/palm-logistics/.ssh/config >/dev/null <<'EOF'
Host github.com
    IdentityFile /var/lib/palm-logistics/.ssh/github_deploy_key
    IdentitiesOnly yes
EOF

sudo chmod 0600 /var/lib/palm-logistics/.ssh/config
sudo chown -R palmapp:palmapp /var/lib/palm-logistics/.ssh

sudo -u palmapp git clone \
  git@github.com:<GITHUB_OWNER>/<GITHUB_REPOSITORY>.git \
  /opt/palm-logistics/repository
```

The private deploy key stays on EC2. It does not go into the repository or GitHub Actions secrets.

### 5.5 Create the production environment file

Create the file through the Session Manager shell:

```bash
sudo install -o root -g palmapp -m 0640 /dev/null \
  /etc/palm-logistics/palm-logistics.env
sudo nano /etc/palm-logistics/palm-logistics.env
```

Add the following values:

```dotenv
OPENROUTER_API_KEY=<OPENROUTER_API_KEY>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
AGENT_MODEL=deepseek/deepseek-v4-pro
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_DIMENSION=1536

PINECONE_API_KEY=<PINECONE_API_KEY>
PINECONE_INDEX_NAME=palm-logistics-sop
PINECONE_NAMESPACE=policy

SQL_SERVER_HOST=<DATABASE_PRIVATE_IP_OR_DNS>
SQL_SERVER_PORT=1433
SQL_SERVER_DATABASE=PalmLogistics
SQL_READ_ONLY_USER=palm-logistics-reader
SQL_READ_ONLY_PASSWORD=<PALM_LOGISTICS_READER_PASSWORD>
SQL_RESULT_LIMIT=20

# Current legacy SQL Server settings. Move to yes/no after a trusted TLS
# certificate is configured on SQL Server.
SQL_ENCRYPT=no
SQL_TRUST_SERVER_CERTIFICATE=yes

STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

Important:

- Do not copy the local `.env` file into Git.
- `SQL_SERVER_HOST` is the SQL EC2 private IP or private DNS name, not `127.0.0.1`.
- Do not put the SQL `sa` password in this file. The deployed agent needs only the restricted `palm-logistics-reader` credential.
- A stronger follow-up is to store these values in AWS Secrets Manager and generate this root-owned file during bootstrap or startup.

Validate permissions without printing the contents:

```bash
sudo stat -c '%U %G %a %n' /etc/palm-logistics/palm-logistics.env
```

Expected result:

```text
root palmapp 640 /etc/palm-logistics/palm-logistics.env
```

### 5.6 Install the locked application dependencies

```bash
sudo -u palmapp env HOME=/var/lib/palm-logistics \
  uv sync --frozen --project /opt/palm-logistics/repository
```

`--frozen` makes the server use the committed `uv.lock` without silently changing dependency versions.

### 5.7 Install the systemd service

```bash
sudo tee /etc/systemd/system/palm-logistics.service >/dev/null <<'EOF'
[Unit]
Description=Palm Logistics Streamlit AI Assistant
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=palmapp
Group=palmapp
WorkingDirectory=/opt/palm-logistics/repository
EnvironmentFile=/etc/palm-logistics/palm-logistics.env
Environment=HOME=/var/lib/palm-logistics
ExecStart=/opt/palm-logistics/repository/.venv/bin/streamlit run src/ui.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/palm-logistics

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0755 \
  /opt/palm-logistics/repository/scripts/deploy_app.sh \
  /usr/local/sbin/deploy-palm-logistics

sudo systemctl daemon-reload
sudo systemctl enable --now palm-logistics
```

Check service and health:

```bash
sudo systemctl status palm-logistics --no-pager
curl --fail http://127.0.0.1:8501/_stcore/health
sudo journalctl -u palm-logistics -n 100 --no-pager
```

Expected health response:

```text
ok
```

Run the deeper production dependency check:

```bash
sudo -u palmapp env \
  HOME=/var/lib/palm-logistics \
  PALM_ENV_FILE=/etc/palm-logistics/palm-logistics.env \
  /usr/local/bin/uv run --frozen \
  --project /opt/palm-logistics/repository \
  python /opt/palm-logistics/repository/scripts/deployment_smoke_test.py
```

The expected final line confirms imports, SQL, embeddings, and Pinecone. This check makes a small OpenRouter embedding request.

The installed deployment runner is deliberately root-owned and does not update itself during an application deployment. When `scripts/deploy_app.sh` changes, review it separately and reinstall it through an authorized Session Manager session before relying on the new behavior:

```bash
sudo install -m 0755 \
  /opt/palm-logistics/repository/scripts/deploy_app.sh \
  /usr/local/sbin/deploy-palm-logistics
```

## 6. GitHub-to-AWS authentication with OIDC

GitHub Actions does not need `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `EC2_HOST`, or `EC2_SSH_KEY`.

### 6.1 Create the GitHub OIDC provider in AWS

In IAM > Identity providers, add:

```text
Provider URL: https://token.actions.githubusercontent.com
Audience:     sts.amazonaws.com
```

Skip this step if the provider already exists in the AWS account.

### 6.2 Create the restricted deployment document

From an authorized AWS administrator workstation or AWS CloudShell, create the custom SSM Command document from the repository:

```bash
aws ssm create-document \
  --region <AWS_REGION> \
  --name PalmLogistics-Deploy \
  --document-type Command \
  --document-format YAML \
  --content file://infrastructure/ssm/palm-logistics-deploy-document.yaml
```

Confirm that its status is `Active`:

```bash
aws ssm describe-document \
  --region <AWS_REGION> \
  --name PalmLogistics-Deploy \
  --query 'Document.Status' \
  --output text
```

The document accepts only a 40-character lowercase hexadecimal commit SHA and invokes the fixed root-owned deployment runner. GitHub is not allowed to submit arbitrary shell commands.

### 6.3 Create the GitHub deployment role

Create a role named `PalmLogisticsGitHubDeployRole` with this trust policy. Replace all placeholders. Because the workflow uses a GitHub Environment, its OIDC subject contains `environment:palm-production`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:farazahmad-ai/palm-logistics-ai-assistant:environment:palm-production"
        }
      }
    }
  ]
}
```

If the GitHub organization uses immutable OIDC subject claims, inspect one token/failed trust event and add the organization and repository ID suffixes required by that organization's policy.

Attach this least-privilege permissions policy to the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RunDeploymentOnOneInstance",
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ssm:<AWS_REGION>:<AWS_ACCOUNT_ID>:document/PalmLogistics-Deploy",
        "arn:aws:ec2:<AWS_REGION>:<AWS_ACCOUNT_ID>:instance/<APP_INSTANCE_ID>"
      ]
    },
    {
      "Sid": "ReadDeploymentResult",
      "Effect": "Allow",
      "Action": [
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations",
        "ssm:CancelCommand"
      ],
      "Resource": "*"
    }
  ]
}
```

This role can invoke only the named SHA-only deployment document against the named instance, read the resulting command status, and cancel a timed-out deployment command. The document still executes the root-owned deployment runner, so repository protection and careful control of that runner remain security boundaries.

## 7. Configure the GitHub production environment

In GitHub, open **Repository > Settings > Environments** and create:

```text
palm-production
```

Mandatory protection:

- Allow deployments only from `main`.
- Protect `main` against direct unreviewed changes.
- Add a required reviewer for production when the GitHub plan supports it.
- Prevent administrators from bypassing the protection for routine releases.

The workflow itself rejects refs other than `main`, and the Environment restriction is a mandatory second control because `workflow_dispatch` otherwise permits selecting another branch whose workflow could deploy unreviewed code.

Add this environment secret:

```text
AWS_DEPLOY_ROLE_ARN=arn:aws:iam::<AWS_ACCOUNT_ID>:role/PalmLogisticsGitHubDeployRole
```

Add these environment variables:

```text
AWS_REGION=eu-north-1
EC2_INSTANCE_ID=<APP_INSTANCE_ID>
```

Application/API/SQL secrets remain on EC2; they are not GitHub deployment secrets.

## 8. How automatic deployment works

The workflow runs when code is pushed to `main`, and it can also be started manually from the Actions page.

1. GitHub checks out the commit.
2. `uv sync --frozen` verifies that the lock file can build the environment.
3. Python files and the deployment shell script receive syntax checks. These checks are not a substitute for a full automated test suite.
4. GitHub requests short-lived AWS credentials through OIDC.
5. GitHub sends the exact 40-character commit SHA through the restricted `PalmLogistics-Deploy` SSM document.
6. EC2 fetches that commit and synchronizes the locked dependencies.
7. systemd restarts Streamlit.
8. The deployment script checks `/_stcore/health`, imports the deployed agent, connects to SQL, creates an embedding, and checks the Pinecone namespace.
9. If validation fails, the script restores the previous commit and locked environment, restarts it, and verifies the rollback health.

The workflow is intentionally serialized with a concurrency group so two production deployments cannot modify the same checkout simultaneously.

## 9. First deployment and later deployments

Commit and push these files to the GitHub repository:

```text
.github/workflows/deploy.yml
infrastructure/ssm/palm-logistics-deploy-document.yaml
scripts/deploy_app.sh
scripts/deployment_smoke_test.py
docs/guide/Palm-Logistics-EC2-Deployment.md
```

The first push after the bootstrap starts the automatic workflow. To run it manually:

1. Open GitHub > Actions.
2. Select **Deploy Palm Logistics**.
3. Select **Run workflow** on `main`.
4. Approve the `palm-production` deployment if environment approval is enabled.

No one needs to log in to EC2 for normal releases.

## 10. Verification after deployment

From Session Manager:

```bash
sudo systemctl is-active palm-logistics
curl --fail http://127.0.0.1:8501/_stcore/health
sudo journalctl -u palm-logistics -n 100 --no-pager
sudo -u palmapp git -C /opt/palm-logistics/repository rev-parse HEAD
```

From AWS:

- Confirm the ALB target is healthy.
- Confirm the application SG has no inbound `22` rule.
- Confirm the database SG accepts `1433` only from the application SG and any separately approved administration path.
- Confirm Systems Manager reports the instance as Online.

From the application:

- Ask one telemetry question that invokes SQL.
- Ask one SOP question that invokes Pinecone/OpenRouter embeddings.
- Ask one corridor question that invokes Open-Meteo.
- Confirm a new `dbo.AgentAuditLog` row using the authorized audit-viewing account, not the application reader.

## 11. Operations and troubleshooting

### Service fails immediately

```bash
sudo systemctl status palm-logistics --no-pager
sudo journalctl -u palm-logistics -n 200 --no-pager
```

Common causes are a missing environment value, an invalid API key, or a missing ODBC driver.

### SQL connection fails

Check that:

- `SQL_SERVER_HOST` is the database private address, not `127.0.0.1`.
- Both instances are in routable VPC subnets.
- the database SG allows TCP `1433` from the App SG.
- SQL Server is listening on the private interface and port `1433`.
- the restricted reader login is enabled and its password matches the environment file.

Do not solve this by opening SQL Server to `0.0.0.0/0`.

### Systems Manager deployment does not start

Check:

- the application instance is Online in Fleet Manager;
- the instance profile includes `AmazonSSMManagedInstanceCore`;
- outbound HTTPS is available;
- `EC2_INSTANCE_ID` and `AWS_REGION` are correct GitHub environment variables;
- the GitHub OIDC trust policy exactly matches the repository and environment;
- the deployment role has `ssm:SendCommand` for both the document and instance ARNs.

### Git fetch fails

For a private repository, verify the read-only deploy key:

```bash
sudo -u palmapp ssh -T git@github.com
sudo -u palmapp git -C /opt/palm-logistics/repository fetch origin
```

The first command normally says authentication succeeded but GitHub does not provide shell access. That is expected.

### Manual rollback

Find a known-good commit in GitHub, copy its full 40-character SHA, then use Run Command or a Session Manager shell:

```bash
sudo /usr/local/sbin/deploy-palm-logistics <KNOWN_GOOD_40_CHARACTER_SHA>
```

This follows the same locked, health-checked deployment path as CI/CD.

## 12. Mandatory controls and production follow-ups

Complete these controls before sharing the application publicly:

- Put the application behind an HTTPS ALB with an ACM certificate.
- Add company authentication in front of Streamlit, such as an ALB OIDC integration or an identity-aware proxy.
- Store application secrets in AWS Secrets Manager and define a rotation process.
- Configure a trusted SQL Server TLS certificate, then set `SQL_ENCRYPT=yes` and `SQL_TRUST_SERVER_CERTIFICATE=no`.
- Restrict the GitHub Environment to protected `main` and use the custom `PalmLogistics-Deploy` SSM document.

Complete these reliability improvements before calling the system highly available or enterprise scale:

- Send service and deployment logs to CloudWatch Logs and create alarms for unhealthy targets and repeated restarts.
- Add automated tests beyond syntax validation before enabling unattended production deployment.
- Back up the SQL database and test restore procedures.
- Build immutable artifacts or container images in CI instead of resolving packages on the production server.
- Use ECS/Fargate or an Auto Scaling Group with multiple application instances.
- Externalize LangGraph checkpoints and session state; Streamlit/WebSocket traffic also needs an appropriate load-balancing strategy.

## 13. Why the instructor's SSH workflow is not used

An SSH action can work, but it requires public or routed access to port `22`, stores a long-lived EC2 private key in GitHub, and makes key rotation another operational responsibility. Systems Manager already provides an AWS-audited control channel and works with temporary GitHub OIDC credentials, so it is the better fit for this project.

If an emergency temporarily requires SSH, restrict port `22` to a known corporate/VPN IP, use a short-lived access method such as EC2 Instance Connect where available, record the change, and remove the rule afterward. Do not make SSH the normal CI/CD route.

## 14. Reference documentation

- [GitHub OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [GitHub deployment environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [AWS Systems Manager Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html)
- [AWS security-group rules](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html)
- [Application Load Balancer security groups](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-update-security-groups.html)
- [Microsoft ODBC Driver 18 for SQL Server on Linux](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
- [uv project synchronization](https://docs.astral.sh/uv/concepts/projects/sync/)
