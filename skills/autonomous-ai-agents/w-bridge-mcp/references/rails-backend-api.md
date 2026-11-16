# w-bridge → Rails backend bridge (verified 2026-09-07)

The w-bridge MCP server is NOT the data store — it proxies to a Rails "space" API.
This file records the exact discovery path used when a bare user_name/room_name had
to be resolved into a project, so future sessions can reproduce it in one pass.

## Where the bridge config lives
- `space/api/_client.py` builds the httpx client from helpers.environment:
  - `OUTPUT_BASE_URL` (default http://localhost:3000) — the Rails app
  - `OUTPUT_EVENTS_TOKEN` (default "your-token" in dev) — Bearer token
  - path prefix `/api`, header `Authorization: Bearer <token>`
- All `space/api/*.py` modules are thin wrappers over `request("GET|POST|...", "/projects...")`.

## Reading the live server's env (no restart, no asking)
The MCP server is launched under VS Code debugpy; its env holds the real values:
    ps aux | grep 'W-bridge/main.py'          # find PID (e.g. 2262965)
    tr '\0' '\n' < /proc/<PID>/environ | grep -E 'OUTPUT|BASE_URL|PORT'
Observed: OUTPUT_BASE_URL=http://localhost:3000, OUTPUT_EVENTS_TOKEN=your-token,
PORT=8031, ROOM_BASE_URL=http://localhost:3000.

## Resolution recipe (send-as-named-user without knowing the project)
1. List projects:
       curl -s -H "Authorization: Bearer your-token" http://localhost:3000/api/projects
   → [{"id":1,"name":"project 1","slug":"project-1", ...}]
2. Find which project owns the target room:
       curl -s -H "Authorization: Bearer your-token" http://localhost:3000/api/projects/1/rooms
   → [{"id":2,"name":"project-1"},{"id":3,"name":"specifications"},{"id":4,"name":"releases"}]
   (room 4 = "releases" lives in project 1)
3. Confirm the user in that project (fuzzy match source for username lookup):
       curl -s -H "Authorization: Bearer your-token" http://localhost:3000/api/projects/1/users
   → {"count":1,"page":1,"per_page":40,"project_users":[{"id":1,"name":"siavash mohammady",
      "display_name":"siavash mohammady","email_address":"sia.mohammady66@gmail.com",...}]}
   (fuzzy "siavash" → id 1; helper: mcp/helpers.py username_fuzzy_match, threshold 0.4)
4. Now call the MCP tool WITH project context:
   add_message(project_id=1, room_id=4, user_name="siavash", body="...")
   → creator_id 1 (NOT the id-2 user used without name resolution)

## Why project context is required for names
mcp/tools.py `_resolve_user_id`: if user_name given and project_id is None →
`ValueError("user_name resolution requires project_id or project_name.")`.
Same for `_resolve_room_id` (room_name) and `_resolve_bot_id` (bot_name).
Numeric ids bypass resolution entirely and work project-less.

## Observed message payload shapes (Rails JSON, from MCP text)
Normal message:
    {"id":7,"room_id":4,"creator_id":1,"creator_type":"User","system":false,
     "system_type":null,"created_at":"2026-09-07T06:23:29.956Z","updated_at":"...",
     "body":"Hello from siavash — example message via w-bridge MCP (room 4, project 1)",
     "has_attachment":false,"attachment_filename":null,...}
Loading message: same shape, body auto-prefixed ":spin: <text>".
Delete result: plain "Success" (no JSON).

## Useful endpoints seen in space/api
- GET /api/projects, GET /api/projects/{id}
- GET /api/projects/{id}/rooms, GET /api/projects/{id}/rooms/{room_id},
  GET /api/projects/{id}/rooms/search?q=, GET .../rooms/{room_id}/threads
- GET /api/projects/{id}/users, GET /api/projects/{id}/users/{user_id}
