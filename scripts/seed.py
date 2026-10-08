"""Load data/people.csv into DynamoDB, and optionally create Cognito demo users.

    python scripts/seed.py --stack wow-beacon                 # people table only
    python scripts/seed.py --stack wow-beacon --cognito-users # + users, groups from accessRole
    python scripts/seed.py --stack wow-beacon --csv my.csv --replace

Cognito users get a temporary password (printed once) and must change it on first sign-in.
In production, federate your SSO into the user pool instead and manage groups there.
"""
import argparse
import secrets
import string
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))
from beacon.store import parse_people_csv  # noqa: E402


def outputs(stack: str) -> dict:
    cfn = boto3.client("cloudformation")
    out = cfn.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in out}


def temp_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(14))
        if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", default="wow-beacon")
    ap.add_argument("--csv", default=str(ROOT / "data" / "people.csv"))
    ap.add_argument("--replace", action="store_true", help="delete people not in the CSV")
    ap.add_argument("--cognito-users", action="store_true", help="create a Cognito user per person")
    args = ap.parse_args()

    out = outputs(args.stack)
    people = parse_people_csv(Path(args.csv).read_text())
    table = boto3.resource("dynamodb").Table(out["PeopleTableName"])

    if args.replace:
        keep = {p["id"] for p in people}
        with table.batch_writer() as batch:
            for item in table.scan(ProjectionExpression="id").get("Items", []):
                if item["id"] not in keep:
                    batch.delete_item(Key={"id": item["id"]})
    with table.batch_writer() as batch:
        for p in people:
            batch.put_item(Item={k: v for k, v in p.items() if v not in ("", [])} | {"id": p["id"]})
    print(f"Loaded {len(people)} people into {out['PeopleTableName']}")

    if args.cognito_users:
        idp = boto3.client("cognito-idp")
        pool = out["UserPoolId"]
        for p in people:
            pw = temp_password()
            try:
                idp.admin_create_user(
                    UserPoolId=pool, Username=p["email"], TemporaryPassword=pw, MessageAction="SUPPRESS",
                    UserAttributes=[{"Name": "email", "Value": p["email"]}, {"Name": "email_verified", "Value": "true"}],
                )
                print(f"  {p['email']:32} temp password: {pw}")
            except idp.exceptions.UsernameExistsException:
                print(f"  {p['email']:32} (already exists)")
            if p.get("accessRole") in ("lead", "hr", "admin"):
                idp.admin_add_user_to_group(UserPoolId=pool, Username=p["email"], GroupName=p["accessRole"])
                print(f"  {'':32} → group {p['accessRole']}")


if __name__ == "__main__":
    main()
