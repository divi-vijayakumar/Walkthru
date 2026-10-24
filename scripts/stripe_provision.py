import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

base = os.environ["INTEGRATION_PROXY_URL"]
job_id = "85238fad-b9a7-47f2-86a4-687ef19b67f3"
key = "sk-emergent-8B27bBaE0E9B2889c6"
req = urllib.request.Request(
    base + "/stripe/sandboxes",
    data=json.dumps({"job_id": job_id}).encode(),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req) as r:
        sandbox = json.load(r)
except urllib.error.HTTPError as e:
    print(f"PROVISIONING FAILED {e.code}: {e.read().decode()}")
    sys.exit(1)

import stripe  # noqa: E402

stripe.api_key = sandbox["sandbox_secret_key"]
acct = stripe.Account.retrieve()
tax = stripe.tax.Settings.retrieve()
print(json.dumps({
    "keys": {k: sandbox.get(k) for k in ("sandbox_secret_key", "sandbox_publishable_key", "sandbox_account_id", "preview_webhook_secret")},
    "onboarding_url": sandbox.get("onboarding_url"),
    "country": acct["country"],
    "tax_status": tax.status,
    "head_office": bool(tax.head_office),
}))
