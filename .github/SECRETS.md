# Secrets Required for DNS Setup

To enable the automated DNS setup pipeline, add the following secrets to your GitHub repository:

## GitHub Repository Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Description |
|-------------|-------------|
| `DNSEMADEASY_API_KEY` | Your dnsmadeeasy API key |
| `DNSEMADEASY_API_SECRET` | Your dnsmadeeasy API secret |

## Getting Your dnsmadeeasy API Credentials

1. Log into your dnsmadeeasy account at https://www.dnsmadeeasy.com/
2. Navigate to **API Access** or **Settings → API Keys**
3. Generate a new API key if you don't have one
4. Copy the **API Key** and **API Secret**

## Running the Pipeline

### Manual Trigger

1. Go to **Actions → Setup DNS for Custom Domain**
2. Click **Run workflow**
2. Select environment (staging/production)
3. Click **Run workflow**

### Automatic Trigger

The pipeline will also run automatically on push to `main` branch.

## What the Pipeline Does:

1. Connects to dnsmadeeasy API using your credentials
2. Fetches domain ID for `violincelloacademy.com.au`
3. Creates/updates DNS records:
   - 4 A records pointing to GitHub Pages IPs (185.199.108/109/110/111.153)
   - 1 CNAME record for www → damianmiller.github.io
4. Reports success/failure status

## Troubleshooting

- **Authentication Error**: Check that API credentials are correct and have proper permissions
- **Domain Not Found**: Ensure the domain is managed in your dnsmadeeasy account
- **Permission Denied**: Verify API key has permission to modify DNS records