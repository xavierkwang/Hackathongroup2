#!/usr/bin/env bash
# Deploy the whole stack, build the web app against it, upload it, and seed the directory.
#
#   ./scripts/deploy.sh                    # uses samconfig.toml (run `sam deploy --guided` once first)
#   SEED_USERS=1 ./scripts/deploy.sh       # also create Cognito demo users
set -euo pipefail
cd "$(dirname "$0")/.."

STACK="${STACK:-wow-beacon}"

echo "▶ sam build + deploy ($STACK)"
sam build
sam deploy --stack-name "$STACK"

out() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

API_URL=$(out ApiUrl)
WEB_URL=$(out WebUrl)
BUCKET=$(out WebBucketName)
DIST=$(out DistributionId)
CLIENT_ID=$(out UserPoolClientId)
DOMAIN=$(out CognitoDomain)

echo "▶ building web app"
cat > frontend/.env.production <<EOF
VITE_AUTH_MODE=cognito
VITE_API_BASE=$API_URL
VITE_COGNITO_DOMAIN=$DOMAIN
VITE_COGNITO_CLIENT_ID=$CLIENT_ID
VITE_SLACK_TEAM_ID=${SLACK_TEAM_ID:-}
EOF
(cd frontend && npm ci && npm run build)

echo "▶ uploading to s3://$BUCKET"
aws s3 sync frontend/dist "s3://$BUCKET" --delete \
  --cache-control "public,max-age=31536000,immutable" --exclude index.html --exclude floors.json
aws s3 cp frontend/dist/index.html "s3://$BUCKET/index.html" --cache-control "no-cache"
aws s3 cp frontend/dist/floors.json "s3://$BUCKET/floors.json" --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/index.html" "/floors.json" >/dev/null

echo "▶ seeding directory"
if [[ "${SEED_USERS:-0}" == "1" ]]; then
  python3 scripts/seed.py --stack "$STACK" --cognito-users
else
  python3 scripts/seed.py --stack "$STACK"
fi

echo
echo "✅ WOW Beacon is live: $WEB_URL"
echo "   API health:        $API_URL/api/health"
