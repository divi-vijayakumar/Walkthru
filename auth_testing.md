# Auth-Gated App Testing Playbook (Emergent Google Auth)

## Step 1: Create test user & session (email must be on OWNER_EMAILS allow-list)
```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.updateOne({email: 'divi@velvee.ai'}, {\$setOnInsert: {user_id: userId, email: 'divi@velvee.ai', name: 'Divi', picture: '', created_at: new Date()}}, {upsert: true});
var u = db.users.findOne({email: 'divi@velvee.ai'});
db.user_sessions.insertOne({user_id: u.user_id, session_token: sessionToken, expires_at: new Date(Date.now() + 7*24*60*60*1000), created_at: new Date()});
print('Session token: ' + sessionToken);
"
```
For a non-allow-listed check, create a user with another email + session: /api/auth/me must return 403.

## Step 2: Backend
```
curl -X GET "$API/api/auth/me" -H "Authorization: Bearer TOKEN"
curl -X GET "$API/api/dashboard" -H "Authorization: Bearer TOKEN"
curl -X GET "$API/api/dashboard"   # must be 401
```

## Step 3: Browser
```
await page.context.add_cookies([{"name": "session_token", "value": "TOKEN", "domain": "<host>", "path": "/", "httpOnly": True, "secure": True, "sameSite": "None"}])
await page.goto("https://<host>/")
```

## Cleanup
```
mongosh --eval "use('test_database'); db.user_sessions.deleteMany({session_token: /test_session/});"
```
