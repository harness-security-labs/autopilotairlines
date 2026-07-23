#!/bin/bash
# Refreshes AWS SSO credentials in .env.dev.
# Run this when session tokens expire (~12h).
# Usage: ./refresh-aws-creds.sh <profile-name>

PROFILE="${1:-$AWS_PROFILE}"

if [ -z "$PROFILE" ]; then
    echo "No AWS profile specified."
    echo "Usage: ./refresh-aws-creds.sh <profile-name>"
    echo "   or: AWS_PROFILE=<profile-name> ./refresh-aws-creds.sh"
    exit 1
fi

creds=$(aws configure export-credentials --profile "$PROFILE" --format env-no-export 2>&1)
if [ $? -ne 0 ]; then
    echo "Failed to export credentials. Run: aws sso login --profile $PROFILE"
    exit 1
fi

ACCESS_KEY=$(echo "$creds" | grep '^AWS_ACCESS_KEY_ID=' | cut -d= -f2-)
SECRET_KEY=$(echo "$creds" | grep '^AWS_SECRET_ACCESS_KEY=' | cut -d= -f2-)
SESSION_TOKEN=$(echo "$creds" | grep '^AWS_SESSION_TOKEN=' | cut -d= -f2-)

if [ -z "$ACCESS_KEY" ]; then
    echo "No credentials found. Run: aws sso login --profile $PROFILE"
    exit 1
fi

# sed -i '' is macOS (BSD) syntax; sed -i is Linux (GNU) syntax.
SED_INPLACE=(sed -i '')
if sed --version 2>/dev/null | grep -q GNU; then
    SED_INPLACE=(sed -i)
fi

"${SED_INPLACE[@]}" "s|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=$ACCESS_KEY|" .env.dev
"${SED_INPLACE[@]}" "s|^AWS_SECRET_ACCESS_KEY=.*|AWS_SECRET_ACCESS_KEY=$SECRET_KEY|" .env.dev
"${SED_INPLACE[@]}" "s|^AWS_SESSION_TOKEN=.*|AWS_SESSION_TOKEN=$SESSION_TOKEN|" .env.dev

echo "Updated .env.dev with fresh credentials from profile: $PROFILE"
echo "Restart backend: docker compose restart backend"
