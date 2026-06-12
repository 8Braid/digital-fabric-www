#!/usr/bin/env bash
# Deploy df-ledger-cors-proxy: a read-only CORS proxy (Lambda Function URL) in
# front of the TrustDB ledger gateway, so the static explorer can read live.
# Idempotent: re-running updates the code. Teardown at the bottom.
set -euo pipefail

REGION="${REGION:-ca-central-1}"
FN="df-ledger-cors-proxy"
ROLE="df-ledger-cors-proxy-role"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE}"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "→ region=$REGION account=$ACCOUNT"

# 1. IAM role (logs only)
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --description "Read-only CORS proxy for the TrustDB ledger gateway" >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "→ created role $ROLE; waiting for propagation"; sleep 12
else
  echo "→ role exists"
fi

# 2. Package
( cd "$DIR" && zip -q -j /tmp/df-ledger-cors-proxy.zip lambda_function.py )

# 3. Create or update the function
if aws lambda get-function --function-name "$FN" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --region "$REGION" \
    --zip-file fileb:///tmp/df-ledger-cors-proxy.zip >/dev/null
  echo "→ updated function code"
else
  for i in 1 2 3 4 5; do
    if aws lambda create-function --function-name "$FN" --region "$REGION" \
        --runtime python3.13 --role "$ROLE_ARN" --handler lambda_function.handler \
        --timeout 25 --memory-size 128 \
        --zip-file fileb:///tmp/df-ledger-cors-proxy.zip >/dev/null 2>/tmp/lambda_err; then
      echo "→ created function"; break
    fi
    echo "  retry $i (role propagation)…"; sleep 8
  done
fi

# 4. Public Function URL with CORS
if ! aws lambda get-function-url-config --function-name "$FN" --region "$REGION" >/dev/null 2>&1; then
  aws lambda create-function-url-config --function-name "$FN" --region "$REGION" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["*"],"AllowMethods":["POST"],"AllowHeaders":["content-type"],"MaxAge":86400}' >/dev/null
  aws lambda add-permission --function-name "$FN" --region "$REGION" \
    --statement-id public-url --action lambda:InvokeFunctionUrl \
    --principal "*" --function-url-auth-type NONE >/dev/null
  echo "→ created public function URL"
fi

URL="$(aws lambda get-function-url-config --function-name "$FN" --region "$REGION" --query FunctionUrl --output text)"
echo "FUNCTION_URL=$URL"

# Teardown (manual):
#   aws lambda delete-function-url-config --function-name df-ledger-cors-proxy --region ca-central-1
#   aws lambda delete-function --function-name df-ledger-cors-proxy --region ca-central-1
#   aws iam detach-role-policy --role-name df-ledger-cors-proxy-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
#   aws iam delete-role --role-name df-ledger-cors-proxy-role
