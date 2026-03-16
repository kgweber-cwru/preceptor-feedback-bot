# Google OAuth Setup Guide

## Step 1: Create OAuth 2.0 Credentials in Google Cloud Console

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/apis/credentials
   - Select your project: `meded-gcp-sandbox`

2. **Enable Google+ API** (if not already enabled)
   - Go to: https://console.cloud.google.com/apis/library
   - Search for "Google+ API"
   - Click "Enable"

3. **Create OAuth 2.0 Client ID**
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: **Web application**
   - Name: `Preceptor Feedback Bot - Local Development`

4. **Add Authorized Redirect URIs**
   - Click "Add URI" under "Authorized redirect URIs"
   - Add: `http://localhost:8080/auth/callback`
   - Click "Create"

5. **Save Your Credentials**
   - Copy the **Client ID** (looks like: `123456789-abcdefg.apps.googleusercontent.com`)
   - Copy the **Client secret** (looks like: `GOCSPX-abc123...`)

## Step 2: Configure Environment Variables

Create or update `.env` file in your project root:

```bash
# Copy .env.example to .env if you haven't already
cp .env.example .env
```

Add these lines to your `.env` file:

```bash
# OAuth Settings
OAUTH_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=your-client-secret-here
OAUTH_REDIRECT_URI=http://localhost:8080/auth/callback

# Domain Restriction (optional - set to false for testing)
OAUTH_DOMAIN_RESTRICTION=false
# OAUTH_ALLOWED_DOMAINS=case.edu,uhhospitals.org

# Debug Mode
DEBUG=true
```

## Step 3: Start the Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Start FastAPI server
export DEBUG=true
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Step 4: Test OAuth Flow

1. **Open browser**: http://localhost:8080
2. **Click "Sign in with Google"**
3. **Select your Google account**
4. **Grant permissions** (email, profile)
5. **You should be redirected to** http://localhost:8080/dashboard
6. **See your user info** displayed on the dashboard

## Troubleshooting

### Error: "Invalid redirect URI"
- Make sure `http://localhost:8080/auth/callback` is in the OAuth consent screen's authorized redirect URIs
- Ensure the redirect URI in `.env` matches exactly (no trailing slash)

### Error: "Access denied - domain not authorized"
- Set `OAUTH_DOMAIN_RESTRICTION=false` in `.env` for testing
- Or add your email domain to `OAUTH_ALLOWED_DOMAINS`

### Error: "Invalid client ID"
- Double-check your `OAUTH_CLIENT_ID` in `.env`
- Ensure there are no extra spaces or quotes

### Error: "Missing email-validator"
- Already installed, but if you see this: `pip install email-validator`

## Testing with Domain Restriction

Once basic OAuth works, test domain restriction:

```bash
# In .env
OAUTH_DOMAIN_RESTRICTION=true
OAUTH_ALLOWED_DOMAINS=case.edu,uhhospitals.org
```

- Emails from `@case.edu` or `@uhhospitals.org` will be allowed
- Other domains will see "Access Denied" page

## Next Steps

After OAuth works:
- Test logout functionality
- Try accessing `/auth/verify` endpoint
- Check that `/dashboard` requires authentication
- Test accessing dashboard when not logged in (should redirect to login)
