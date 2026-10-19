import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=10)
alice = c.post("/api/auth/login", json={"email": "alice@example.com", "password": "password123"}).json()
bob = c.post("/api/auth/login", json={"email": "bob@example.com", "password": "password123"}).json()
ah = {"Authorization": f"Bearer {alice['access_token']}"}
bh = {"Authorization": f"Bearer {bob['access_token']}"}
gid = c.get("/api/groups", headers=ah).json()[0]["id"]
bal = c.get(f"/api/groups/{gid}/balances", headers=ah).json()
t = bal["suggested_transfers"][0]
print("transfer", t)
from_headers = bh if bob["user"]["id"] == t["from_user_id"] else ah
s = c.post(
    f"/api/groups/{gid}/settlements",
    headers=from_headers,
    json={
        "from_user_id": t["from_user_id"],
        "to_user_id": t["to_user_id"],
        "amount_cents": t["amount_cents"],
    },
).json()
print("pending", s["status"], s["id"])
rh = ah if alice["user"]["id"] == t["to_user_id"] else bh
conf = c.post(f"/api/settlements/{s['id']}/action", headers=rh, json={"action": "confirm"}).json()
print("confirmed", conf["status"])
bal2 = c.get(f"/api/groups/{gid}/balances", headers=ah).json()
print("sum", bal2["sum_check"], "transfers_left", len(bal2["suggested_transfers"]))
